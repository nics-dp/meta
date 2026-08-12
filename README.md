# meta

nics-dp 組織共用 mise tasks + reusable GitHub Actions workflows + 共用設定檔之 meta repo。本 repo 無可建置程式碼，純配置與 CI/CD 基礎設施。

## 內容總覽

| 目錄/檔案              | 說明                                                                                                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.github/workflows/`   | Reusable GitHub Actions workflows (`mise-task.yml` 為核心；release / sbom-image / codeql / utility 等)                                                                                       |
| `.mise/tasks/`         | 共用 mise atomic tasks (`ci/`, `iac/`, `go/`, `node/`, `py/`, `sbom/`, `gs/`, `dc/`, `meta/`, `lib/`)，consumer 透過 `git::` remote includes 引用                                             |
| `templates/facades/`   | 5 個 mise.toml facade templates (`mise.go-service.toml`, `mise.go-lib.toml`, `mise.frontend.toml`, `mise.python.toml`, `mise.image.toml`) — copy 後依需求加 repo-specific 即可使用 |
| `configs/`             | 共用設定檔 (`eslint.config.js`, `.prettierrc.json`, `.prettierignore`, `.oxfmtrc.json`, `lighthouserc.json`, `playwright.config.ts`)。`vitest.config.ts` / `knip.json` 改為 repo-local（各 consumer commit 自家 root 檔，工具自動發現）；`.golangci.yml` 亦非共享（見下方例外） |
| `renovate-preset.json` | Org-level Renovate preset (`extends` from consumer `renovate.json`)                                                                                                                        |

## Mise Tasks — Facade Pattern

Consumer repo 採 facade pattern：自家 `mise.toml` 暴露標準頂層 vocabulary，底層 `depends` 到本 repo atoms。`mise tasks ls` 只看到 facade，atoms 全 hidden。

```toml
[task_config]
includes = ["git::https://github.com/nics-dp/meta.git//.mise/tasks?ref=main"]
```

Facade templates 於 `templates/facades/`，包含 `[settings]` / `[tools]` / `[env]` / `[task_config]` / facade `[tasks.*]` 全套。Consumer 複製進自家 `mise.toml` 後依需求改 `[env]` 或加 repo-specific tasks 即可。

### Atomic API

所有 atoms 標 `#MISE hide=true`，consumer 透過 `depends` 呼叫。Atom 簽名一旦穩定（Phase E tag `v1`）視為 versioned API，breaking change 須協調升 ref。

| 類別      | Atoms                                                                                                                                                                                          | 用途                                                                                                                                                                                                                                                                                                                                                                                                |
| --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ci:*`    | semgrep, trivy-license, betterleaks, trufflehog                                                                                                                                                | 通用 CI 檢查（語言中立）。`ci:semgrep` 引擎已改為 OpenGrep（原生 single-binary semgrep fork，無 Python；CLI/registry packs drop-in 相容，task 名與簽名不變）。`ci:betterleaks`＝快速 secret 掃描 PR gate（Gitleaks fork，PR 上優先掃 base..HEAD，base ref fetch 失敗則 fallback 全歷史）；`ci:trufflehog`＝deep/release scan，只報經驗證的 live secrets                                                                                                                                            |
| `iac:*`   | trivy, img:hadolint, actionlint, shellcheck, zizmor                                                                                                                                             | IaC misconfig + Dockerfile lint + workflow/task definition lint；`shellcheck` 動態枚舉 Git index 中全部 tracked task/helper，僅接受 stage 0、mode 100644/100755、regular non-symlink，並以 Bash dialect + warning threshold 掃描；`zizmor` 以 offline、strict collection、regular persona、high threshold 掃本機 workflow/composite action，僅套用 `zizmor.yml` 精確行號 baseline                                                                                                                                                                                                                                                                                                                                                |
| `go:*`    | api-fix, audit, build, bench-compare, clean, dead-code, deptree, dev, generate, install, lib-local, lib-remote, lint-check, lint-fix, report, run, sast, test, update                               | Go 建置/測試/Lint/安全/模組。`go:test` 預設只跑 unit；flags：`--race`、`--coverage`、`--bench [--pattern X]`、`--full`；`go:report` 從 coverage.out 產 HTML+MD（自動讀 `go.mod` module path 解析 component）；`go:bench-compare` 跑 benchstat；`go:dead-code` 用 `cmd/deadcode`，預設只分析 production（root 為所有 main package，常見於 `cmd/*`），`--whole-program` 才把測試一併納入並 root（`-tags "$GO_TEST_TAGS" -test`，預設 `test`）；`go:deptree` 用 `go mod graph`；路徑/tags/coverpkg 由 `lib/go-env` auto-detect            |
| `node:*`  | install, build, bench-compare, bundle-size, clean, deptree, run, test, e2e, e2e-install, lint-check, lint-fix, oxlint, format-check, format-fix, oxfmt-check, oxfmt-fix, typecheck, typecheck-tsgo, sast, audit, update, knip, lighthouse      | JS/TS via bun。`lint`/`format`/`lighthouse` 拉 `configs/` shared；`test`/`knip` 用 repo-local config（各 repo 自家 root 檔，工具自動發現，缺檔即報錯）；e2e 用 Playwright；`node:clean [--deep]` 清 transient；`node:bench-compare` 跑 vitest bench × `--count` 後 merge JSON，無 flag 列對比 (mean ± rme + Welch t-test 完整 p-value)；`node:bundle-size` 偵 `.size-limit` config 用 size-limit，否則 fallback du+gzip。原生 binary 平行替代（opt-in，與既有 atom 並存）：`oxfmt-check`/`oxfmt-fix` ↔ prettier、`oxlint` ↔ eslint（script-only，不解析 .vue template）、`typecheck-tsgo` ↔ vue-tsc（.ts only，需 repo 自備 `*.vue` shim）；三者皆 bunx 無版本、版本由 consumer package.json devDep 控制 |
| `py:*`    | install, build, audit, bench-compare, clean, complexity, dead-code, deptree, format-check, format-fix, license-custom, lint-check, lint-fix, profile, report, run, safety-db, sast, sbom-custom, test, typecheck, update | Python via uv + ruff + pytest + bandit + pip-audit + ty。`py:sast` (bandit)；`py:typecheck` (ty Beta / `--pyrefly`)；`py:dead-code` (vulture)；`py:complexity` (radon/xenon)；`py:deptree` (uv tree)；`py:safety-db` (safety<3)；`py:license-custom` (pip-licenses)；`py:sbom-custom` (cyclonedx-py)；`py:profile` 預設 cProfile，flags：`--instrument`/`--spy`/`--mem`/`--scalene`；env override 由 `lib/py-env` |
| `sbom:*`  | source, enrich, trivy, grype                                                                                                                                                                   | Source SBOM 產生與漏洞掃描                                                                                                                                                                                                                                                                                                                                                                          |
| `gs:*`    | clone, update                                                                                                                                                                                  | Git submodules                                                                                                                                                                                                                                                                                                                                                                                      |
| `dc:*`    | up, down, pull, rec, clean                                                                                                                                                                      | Docker Compose 生命週期（本機 dev stack 起／停／拉取／重建／清除）                                                                                                                                                                                                                                                                                                                                  |
| `meta:*`  | bump                                                                                                                                                                                           | 清 mise tasks cache 強制重抓 atom includes                                                                                                                                                                                                                                                                                                                                                          |
| `mise:*`  | validate                                                                                                                                                                                       | 驗證 mise 目前載入的完整 task graph（循環、缺少 dependency、usage 等）                                                                                                                                                                                                                                                                                                                              |
| `lib/*`   | logs, go-env, go-version, py-env, ci-isolate                                                                                                                                                   | 內部 sourced helper library；`ci-isolate` 在 definition checks 啟動外部命令前隔離 Git config 並移除 GitHub/private-module token env                                                                                                                                                                                                                                                                                                                                                                         |

`mise tasks ls --hidden` 列出全部 atoms。

### Facade Vocabulary

| Facade   | 語意                                                                |
| -------- | ------------------------------------------------------------------- |
| `init`   | bootstrap deps, hooks, submodules                                   |
| `clean`  | wipe build artifacts / caches / transient state                     |
| `build`  | 產 binary / artifact                                                |
| `run`    | 本機跑 service                                                      |
| `test`   | unit / integration tests                                            |
| `bench`  | benchmarks                                                          |
| `ci`     | 全部 CI 檢查（lint + sast + audit + dead-code + deptree + semgrep + ...）|
| `sbom`   | 產 enriched SBOM + 掃描                                             |
| `update` | bump deps + refresh atom includes (`meta:bump`) + update submodules |
| `all`    | 便利組合：`init` → `build` → `test` → `ci`                          |

Repo-specific concepts (`stg:*`, `pgroll:*`, `benchmark:*`, `spec`, `example:*` 等) 留 repo 本地，不進 facade 層。

### Override 規則

Consumer 在自家 `mise.toml` 定義同名 task 即覆寫（mise 偏好近檔）。`update` facade 用 `meta:bump` 清 mise cache 強制下次 run 重抓 `main`；一旦 ref 改成 tag (`v1`)，`meta:bump` 變 no-op，須手動改 ref。

### Go atoms 之 env 覆寫

`go:test` / `go:report` 透過 `lib/go-env` 自動偵測：

| Env var          | Default                                                     | 用途                               |
| ---------------- | ----------------------------------------------------------- | ---------------------------------- |
| `GO_TEST_TAGS`   | `test`                                                      | `go:test`/`go:bench-compare` 的 `-tags=` build tags；`go:dead-code` 僅 `--whole-program` 時帶入 |
| `GO_TEST_PATHS`  | `./test/...`（如 `test/` 存在）/ `./...`                    | 測試目標 paths                     |
| `GO_TEST_MOD`    | `vendor`（如 `vendor/` 存在）/ `mod`                        | `-mod=` 模式                       |
| `GO_COVERPKG`    | `<go.mod module>/internal/...`（如 `internal/` 存在）/ empty | `-coverpkg=` 範圍                  |
| `CGO_ENABLED`    | `1`                                                         | race detector 須 cgo               |

`go:report` 額外自動讀 `go.mod` module path 解析 component（支援短 module 名與 hostname-style `github.com/<org>/<repo>` path）。

### Python / Node atoms env 覆寫

`py:*` 透過 `lib/py-env`：`PY_RUNNER` (default `uv run --group test`)、`PY_TEST_PATHS`、`PY_LINT_PATHS`、`PY_BANDIT_PATHS`、`PY_BANDIT_EXCLUDE`、`PY_COVERAGE_FILE`。

`node:bundle-size` 用 `BUNDLE_SIZE_DIR` 指定掃描目錄（default `dist`）。

### Transient 檔 — gitignore 建議

Atoms 跑完會在 repo 根產 transient 檔。`mise run go:clean` / `node:clean` / `py:clean` 可清，但建議直接列 `.gitignore`：

```gitignore
# Go
coverage.out
coverage.html
coverage.md
bench-*.txt
bin/

# Node
dist/
build/
.next/
.turbo/
.vite/
coverage/
playwright-report/
test-results/
.lighthouseci/
.eslintcache
bench-*.json

# Python
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
coverage.xml
htmlcov/
sbom.json
sbom-py.json
__pycache__/
.benchmarks/
dist/
build/
.venv/

# SBOM artifacts (all langs，sbom facade 產出)
enriched-source.cdx.json
sbom-source.cdx.json
```

Atoms 之 trap cleanup 結束時清 curl 下來的 shared config (`eslint.config.js`、`.prettierrc.json`、`playwright.config.ts`、`lighthouserc.json`)，但 atom 中斷時可能殘留 — 若 repo 不另放可一併 ignore。（`vitest.config.ts` / `knip.json` 已改 repo-local，不再 curl，故不在此清單。）

> **`.golangci.yml` 例外**：由 consumer repo **自家 commit**（非 curl），須含 `gofumpt.module-path: <repo-module>` 設定（v2.12.2 自動推導對無 `.` 模組名會誤判 stdlib，致 gci↔gofumpt import 互相 false positive）。範本直接 ref 既有 Go repo 之 `.golangci.yml`。

> **`go:lib-local` / `go:lib-remote` 注意事項：**
> 兩 atom 由 env 驅動：
> ```toml
> GO_LIB_LOCAL  = "github.com/nics-dp/libdcf=../libdcf github.com/nics-dp/ZenQuery=../ZenQuery"
> GO_LIB_REMOTE = "github.com/nics-dp/libdcf@dev github.com/nics-dp/ZenQuery@dev"
> ```
> `go:lib-local` 自動停用 repo 自家 `.golangci.yml` 中 `gomoddirectives` 規則並建立 `.semgrepignore` block 排除 vendored libs。`go:lib-remote` 還原。`.semgrepignore` 不應 commit（加入 `.gitignore`）。

---

## CI Workflows

### mise-task.yml — Reusable Mise Task Runner (核心)

封裝 `actions/checkout` + `jdx/mise-action` + 私模 git config + run + summary + enforce。Action 版本中央 pin 於此檔，下游無需各自 pin。

Consumer ci.yml 用 matrix 呼叫：

```yaml
jobs:
  checks:
    name: ${{ matrix.name }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - { name: "Go Lint",       task: "go:lint-check" }
          - { name: "Go SAST",       task: "go:sast" }
          - { name: "Go Audit",      task: "go:audit" }
          - { name: "Go Test",       task: "go:test --race --coverage" }
          - { name: "Semgrep",       task: "ci:semgrep golang" }
          - { name: "Trivy IaC",     task: "iac:trivy" }
          - { name: "Hadolint",      task: "iac:img:hadolint" }
          - { name: "Trivy License", task: "ci:trivy-license" }
    uses: nics-dp/meta/.github/workflows/mise-task.yml@main
    with:
      name: ${{ matrix.name }}
      task: ${{ matrix.task }}
      runs_on: '{"group":"releasers"}'
      private-modules: true
    secrets:
      ci_read_app_private_key: ${{ secrets.CI_READ_APP_PRIVATE_KEY }}
    # client-id is read from the CI_READ_APP_CLIENT_ID org variable (auto-available
    # in reusable workflows); no need to pass it as a secret.
```

| Input             | Type    | Default          | 用途                                                          |
| ----------------- | ------- | ---------------- | ------------------------------------------------------------- |
| `task`            | string  | required         | mise atom 名稱 (e.g., `go:lint-check`、`ci:semgrep golang`)   |
| `name`            | string  | task             | display name for GH job summary                               |
| `runs_on`         | string  | `'"ubuntu-latest"'` | runner（JSON 經 `fromJSON()` 解析；可傳 `'{"group":"X"}'`） |
| `fetch-depth`     | number  | `1`              | git fetch depth                                               |
| `private-modules` | boolean | `false`          | 啟用 ci-read App token git config for private modules         |

App 認證（nics-dp-ci-read，用於 `private-modules=true`）：client-id 由 org **變數** `CI_READ_APP_CLIENT_ID` 提供（reusable workflow 經 `vars` context 自動取得，毋須傳遞）；caller 僅需以 secret 傳 `ci_read_app_private_key`（org secret `CI_READ_APP_PRIVATE_KEY`）。legacy `ci_read_app_id` 輸入已移除（不再宣告,請勿再傳）。

每 job 結尾自動 emit `## <name>` block 至 GitHub Actions step summary，含 ✅/❌ 狀態；只有 task 實際執行時才附上 job-local output 的最後 300 行，skipped/cancelled 則明示未擷取輸出，不讀取runner殘留檔。

---

### Release & Build

| Workflow             | 用途                                                                                                                       |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `go-release.yml`     | Go binary 跨平台建置 + cosign 簽章 + 多平台 SBOM；3 jobs：`prepare` → `build` (matrix) → `release`                          |
| `image-release.yml`  | Docker image dual registry (DockerHub + GHCR) + BuildKit SBOM + SLSA provenance + Sigstore attestation + cosign 簽章；layer 壓縮 auto：snapshot→zstd、release→gzip（`compression` input 可覆寫） |
| `sbom-source.yml`    | Source 端 CycloneDX SBOM (anchore/sbom-action) + parlay 增強 + Trivy/Grype 漏洞掃描 → release-mode 上傳至 GitHub Release / snapshot-mode 留 workflow artifact |
| `sbom-image.yml`     | Container image CycloneDX 1.6 SBOM + parlay 增強 + Trivy/Grype 漏洞掃描 → GitHub Release + Security tab                    |

詳見各 workflow 內 `workflow_call` 之 `inputs` / `secrets` 宣告。

---

### CodeQL

| Workflow                | 用途                                                                                                       |
| ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| `codeql-reusable.yml`   | CodeQL Advanced 分析 reusable workflow。Inputs：`matrix-include` (JSON array of `{language, build-mode}` entries — 例 `[{"language":"actions","build-mode":"none"},{"language":"go","build-mode":"manual"}]`)、`go-cgo-enabled`、`use-private-go-modules`、`submodules` |
| `codeql.yml` (meta 自身) | meta repo 自家 CodeQL workflow，僅掃描 `actions` 語言（workflow YAML）                                     |

---

### Security & Supply Chain

Go 與 Node 的 dependency-submission 拆成兩支：`go.mod` GitHub 原生解析，`bun.lock` 則否。

| Workflow                          | 用途                                                                                                                                                  |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `security-sarif.yml`              | Gate-only scanners（gosec、govulncheck、semgrep、trivy config、hadolint），各自上傳獨立 code-scanning SARIF category；預設為 informational/non-blocking，可選擇讓 gosec fail closed |
| `dependency-review.yml`           | PR-time `dependency-review-action` 掃 GitHub dependency graph；引入帶已知漏洞（≥ `fail_on_severity`，default `high`）或禁用授權的相依時 **擋 PR**；須由 `pull_request` 觸發的 workflow 呼叫 |
| `scorecard.yml`                   | OpenSSF Scorecard（唯一變體，不 publish）；filter 掉 posture 噪音後將 SARIF 上傳至 code scanning（`category: scorecard`，non-blocking）；用 nics-dp-scorecard App 對私有 repo 評分；`publish_results: false` |
| `go-dependency-submission.yml`    | 送 Go 相依圖至 Dependency Submission API；用 ci-read App token 做 org-scoped 私模 git rewrite                                                          |
| `node-dependency-submission.yml`  | 送 bun 專案完整 transitive npm 圖（GitHub 不解析 `bun.lock`，故 `bun install` 後用 Syft catalog `node_modules`）；全公開 npm，免 token                  |

`security-sarif.yml` 的 `run_gosec` / `run_govulncheck` 會在 `run_go` 開啟時分別選擇 Go scanner，三者預設皆為 `true`；`run_go: false` 仍是總開關。`gosec_blocking` 預設為 `false`，只有 `run_go && run_gosec && gosec_blocking` 才會讓 gosec fail closed，涵蓋 vendor 準備、gosec finding 或執行失敗、本機 SARIF 結構預檢、私有 Go 狀態清理、SARIF upload action（包含 `wait-for-processing: true` 回報 terminal `failed`）及 artifact 清理。upload polling API error 或 timeout 只會 warning，處理狀態視為 unknown；govulncheck、semgrep、trivy config、hadolint 仍是 informational。caller 設定錯誤或安全檢查（例如不合法的 `scan_path`）仍可獨立讓 workflow 失敗，因此不可將整支 workflow 視為永不失敗。

本機 `go:sast` atom 維持 blocking，gosec 釘在 `v2.28.0`；meta repo 自家的 Renovate custom manager 會同步更新這個 pin 與 `security-sarif.yml` 內的 gosec pin。

詳見各 workflow 內 `workflow_call` 之 `inputs` / `secrets` 宣告。

---

### Utility

| Workflow                    | 用途                                                          |
| --------------------------- | ------------------------------------------------------------- |
| `artifacts-comment.yml`     | PR 留言列當前 run artifacts，含 [nightly.link](https://nightly.link) 下載連結 |
| `pr-issue-check.yml`        | PR-time 流程 gate：驗證 PR 有 linked issue（closing reference）且每個 linked issue 在 org Projects v2（default Project 3）已設 `version` 欄位；**擋 PR**（設計上搭配 org ruleset required status check）。只 enforce base=`dev` 的 PR（closing keyword 只在 default branch 生效），fork PR 與其他 base 一律綠燈帶 skip 說明。需 org 變數 `CI_READ_APP_CLIENT_ID` + caller 傳 `ci_read_app_private_key`（查 Projects 欄位；App 需 Organization Projects: Read + Issues: Read）。只驗證 GITHUB_TOKEN 可讀的 closing reference（實務上＝同 repo issue；跨 repo private issue 會顯式報錯/警告，不會靜默放行）。caller 的 `pull_request` types 建議含 `edited`（事後補 `Closes #N` 會自動重跑；補 Project 欄位不觸發 event，需手動 re-run） |

---

### Meta CI（meta 自我消費自家 reusables）

- `ci.yml` — meta repo 自家 CI。穩定 matrix check 為 `Actionlint`、`Mise Tasks`、`ShellCheck`；`mise run all` 仍會執行 `iac:zizmor`。ShellCheck 由 Git index 動態枚舉所有 tracked task/helper 與 scanner wrapper，只接受 stage 0、mode 100644/100755 的 regular non-symlink blobs，並以 Bash/warning threshold 檢查。Local Zizmor 1.29.0 使用 `--offline --strict-collection`、regular persona、high threshold，以及 `zizmor.yml` 內 24 個 exact line dispositions（20 個既有 App trust/cleanup boundary、4 個 protected `main` self-dogfood boundary）。
- `Zizmor Action` 是獨立 hosted early-development gate，使用 official action v0.6.2、Zizmor 1.29.0 對應的 reviewed image digest、空 token、`online-audits: false`、high threshold，且不啟用 Advanced Security、SARIF 或 annotations。這不是完整離線或 kernel-level network isolation：container 仍可能有 residual egress，raw CLI output 也會留在無 secrets、`contents: read` 的 job log；final PR CI 是 action/container runtime acceptance。它取代舊 matrix `Zizmor` check name，但不取代 local `iac:zizmor` gate。
- `Grype Path (high, fixed)` 使用 `anchore/scan-action` v7.4.0 與 Grype v0.110.0，nested exact-SHA checkout、trusted mode-0600 config、`only-fixed` High/Critical blocking policy、無 cache/SARIF/upload。DB/tool download 或掃描失敗 fail closed；summary 只保留 sanitized counts/metadata，config/index/JSON cleanup 失敗亦 blocking。Medium 與 unfixed findings 刻意不在此 gate。
- `GitHub Actions Scanner (experimental)` 固定 Snyk Labs signed commit `1a269c9c…` 與 lock digest，tokenless `npm ci --ignore-scripts` 後只跑 7 個 production rules。已知 exact base baseline 是 `UNSAFE_INPUT_ASSIGN=27`、其餘 6 rules 為 0；finding 與任何 network/rule/output failure 都是 informational，後者明確標成 `incomplete`，永不偽裝成 `clean`。Scanner identity 固定為 `${{ github.repository }}` + `${{ github.sha }}`；只有非 Dependabot 的 push/workflow_dispatch，或同 repo、非 Dependabot user 且 association 為 OWNER/MEMBER/COLLABORATOR 的 PR，才把 current-repo read token 限定給 Node scanner child。Fork、Dependabot、其他 association/event 一律 tokenless `incomplete`，不 fallback。Raw scanner output/token 不會進 summary；source/cache/results cleanup 失敗 blocking。此 unsupported research scanner 的 commit 只允許 manual source/support/lock/baseline review，不由 Renovate 更新。
- Scanner-only rollback 會移除 3 個 hosted scanner jobs、scanner wrapper、scanner Renovate/docs，並恢復 matrix `Zizmor` check；local E2 atoms、`zizmor.yml` 與 `mise run all` gate 保留。若 required-check policy 仍引用舊 `Zizmor`，必須先協調改為 `Zizmor Action`，不可直接發布。
- `self-supply-chain.yml` — meta 消費自家 `scorecard.yml`（`publish: false`，改走 filtered 路徑）；無 dependency-submission job（meta 無編譯語言 manifest，純配置）。
- `self-dependency-review.yml` — meta 的 PR-time dependency review，透過 `dependency-review.yml` reusable。

---

## 共用設定檔 (`configs/`)

Atoms 跑時用 `curl` 抓 raw GitHub 設定，跑完 trap cleanup 清除暫存檔。

| 檔案                        | 用途                                       | 由哪些 atom 拉取                          |
| --------------------------- | ------------------------------------------ | ----------------------------------------- |
| `eslint.config.js`          | ESLint flat config + security plugin       | `node:lint-check`, `node:lint-fix`        |
| `.prettierrc.json` + `.prettierignore` | Prettier shared                  | `node:format-check`, `node:format-fix`    |
| `.oxfmtrc.json`             | Oxfmt (Oxc formatter) shared               | `node:oxfmt-check`, `node:oxfmt-fix`      |
| `lighthouserc.json`         | Lighthouse CI shared                       | `node:lighthouse`                         |
| `playwright.config.ts`      | Playwright base (env-driven `PW_*`)        | `node:e2e`, `node:e2e-install`            |

Consumer 可透過 `META_CONFIG_BASE` env 覆寫 raw URL 來源（forking nics-dp/meta 時用）。

**`.golangci.yml` 例外**：不在 `configs/` 共享。各 Go consumer repo **自家 commit** `.golangci.yml`（含 `gofumpt.module-path: <module>` 顯式設定，繞過 golangci-lint v2.12.2 之 gci↔gofumpt false positive）。`go:lint-check` / `go:lint-fix` atom **不再 curl**，直接讀 repo 自家檔。

**`vitest.config.ts` / `knip.json` 例外**：entries/ignores、setup files 等本質 repo-specific，不在 `configs/` 共享。各 web consumer repo **自家 commit** root `vitest.config.ts` / `knip.json`，工具自動發現。`node:test` / `node:knip` / `node:bench-compare` **不再 curl**，並於缺檔時明確報錯（非靜默 fallback 預設行為）。

---

## Renovate

Consumer repo 之 `renovate.json` 引用 org preset：

```json
{
  "extends": ["github>nics-dp/meta:renovate-preset"]
}
```

`renovate-preset.json` 以 native managers（`github-actions`、`gomod`、`dockerfile`、`mise` 等）為主，另加三個 regex customManagers 處理 native manager 辨識不到的釘版（清單以 `renovate-preset.json` 為準）：
- `air-verse/air` — dev compose（`compose.ya?ml` / `deploy/compose.*.ya?ml` 內 `go install github.com/air-verse/air@vX`）
- `.mise/tasks/*` 任務 header 內 `"aqua:<pkg>"="<ver>"` / `"github:<pkg>"="<ver>"` 釘版（generic，只配對數字開頭版本，`="latest"` 掃描器不動）
- `.mise/tasks/*` 任務 header 內 `bun="<ver>"`（映射 oven-sh/bun）

> workflow（`.github/workflows/**`）內以 `go install …@vX` 釘版的工具（quill、parlay、gosec、govulncheck）與 `mise-task.yml` 的 `jdx/mise-action` `version:` pin **不在「org preset」customManager 覆蓋範圍**（preset 只含上列三個，供 consumer extend），而是由 meta repo 自家 `renovate.json` 的 self customManagers 追蹤。Self managers 也同步抽取 ShellCheck atom pin、Zizmor atom + official-action CLI input，以及 Grype workflow input；package rules 將 Zizmor action+CLI 與 Anchore action+Grype 各自分組且禁止 automerge，因 image `support/versions` digest 或 scanner policy 必須人工覆核。Snyk Labs scanner commit 刻意沒有 manager，只能手動驗 signed source、support/lock diff 與完整 baseline。consumer repo 無此類 workflow/self-validation 工具釘版，故 preset 不需涵蓋。

---

## Consumer Repo 設置步驟

1. 從 `templates/facades/mise.<archetype>.toml` (`go-service`/`go-lib`/`frontend`/`python`/`image`) 複製為 repo 自家 `mise.toml`
2. 確認 `[task_config].includes = ["git::https://github.com/nics-dp/meta.git//.mise/tasks?ref=main"]`
3. 加 repo-specific tasks/tools/env at end
4. 寫 `.github/workflows/ci.yml`，用 matrix 呼叫 `nics-dp/meta/.github/workflows/mise-task.yml@main`
5. 設 org 變數 + secrets:
   - org **變數** `CI_READ_APP_CLIENT_ID`（nics-dp-ci-read App 的 client-id；reusable 經 `vars` 自動取得）
   - org **secret** `CI_READ_APP_PRIVATE_KEY`（caller 以 `secrets:` 顯式傳 `ci_read_app_private_key`：Go 私模 + CodeQL private repo + release/snapshot）
   - `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` (Docker image repos)

驗證：`mise tasks ls` 應顯示 ~10 facade 名 + repo-specific extras（atoms hidden）；`mise run --dry-run ci test sbom` resolve 無誤。

---

## 相關文件

- [GitHub: Reusing Workflows](https://docs.github.com/en/actions/learn-github-actions/reusing-workflows)
- [mise: Tasks](https://mise.jdx.dev/tasks/)
