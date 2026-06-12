# meta

nics-dp 組織共用 mise tasks + reusable GitHub Actions workflows + 共用設定檔之 meta repo。本 repo 無可建置程式碼，純配置與 CI/CD 基礎設施。

## 內容總覽

| 目錄/檔案              | 說明                                                                                                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.github/workflows/`   | Reusable GitHub Actions workflows (`mise-task.yml` 為核心；release / sbom-image / codeql / utility 等)                                                                                       |
| `.mise/tasks/`         | 共用 mise atomic tasks (`ci/`, `iac/`, `go/`, `node/`, `py/`, `sbom/`, `gs/`, `meta/`, `lib/`)，consumer 透過 `git::` remote includes 引用                                                   |
| `templates/facades/`   | 5 個 mise.toml facade templates (`mise.go-service.toml`, `mise.go-lib.toml`, `mise.frontend.toml`, `mise.python.toml`, `mise.image.toml`) — copy 後依需求加 repo-specific 即可使用 |
| `configs/`             | 共用設定檔 (`eslint.config.js`, `.prettierrc.json`, `.prettierignore`, `lighthouserc.json`, `playwright.config.ts`)。`vitest.config.ts` / `knip.json` 改為 repo-local（各 consumer commit 自家 root 檔，工具自動發現）；`.golangci.yml` 亦非共享（見下方例外） |
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
| `ci:*`    | semgrep, trivy-license                                                                                                                                                                         | 通用 CI 檢查（語言中立）                                                                                                                                                                                                                                                                                                                                                                            |
| `iac:*`   | trivy, img:hadolint, actionlint                                                                                                                                                                | IaC misconfig + Dockerfile lint + workflow YAML lint                                                                                                                                                                                                                                                                                                                                                |
| `go:*`    | api-fix, audit, build, bench-compare, clean, dead-code, deptree, generate, install, lib-local, lib-remote, lint-check, lint-fix, report, run, sast, test, update                               | Go 建置/測試/Lint/安全/模組。`go:test` 預設只跑 unit；flags：`--race`、`--coverage`、`--bench [--pattern X]`、`--full`；`go:report` 從 coverage.out 產 HTML+MD（自動讀 `go.mod` module path 解析 component）；`go:bench-compare` 跑 benchstat；`go:dead-code` 用 `cmd/deadcode` whole-program；`go:deptree` 用 `go mod graph`；路徑/tags/coverpkg 由 `lib/go-env` auto-detect            |
| `node:*`  | install, build, bench-compare, bundle-size, clean, deptree, run, test, e2e, e2e-install, lint-check, lint-fix, format-check, format-fix, typecheck, sast, audit, update, knip, lighthouse      | JS/TS via bun。`lint`/`format`/`lighthouse` 拉 `configs/` shared；`test`/`knip` 用 repo-local config（各 repo 自家 root 檔，工具自動發現，缺檔即報錯）；e2e 用 Playwright；`node:clean [--deep]` 清 transient；`node:bench-compare` 跑 vitest bench × `--count` 後 merge JSON，無 flag 列對比 (mean ± rme + Welch t-test 完整 p-value)；`node:bundle-size` 偵 `.size-limit` config 用 size-limit，否則 fallback du+gzip |
| `py:*`    | install, build, audit, bench-compare, clean, complexity, dead-code, deptree, format-check, format-fix, license-custom, lint-check, lint-fix, profile, report, run, safety-db, sast, sbom-custom, test, typecheck, update | Python via uv + ruff + pytest + bandit + pip-audit + ty。`py:sast` (bandit)；`py:typecheck` (ty Beta / `--pyrefly`)；`py:dead-code` (vulture)；`py:complexity` (radon/xenon)；`py:deptree` (uv tree)；`py:safety-db` (safety<3)；`py:license-custom` (pip-licenses)；`py:sbom-custom` (cyclonedx-py)；`py:profile` 預設 cProfile，flags：`--instrument`/`--spy`/`--mem`/`--scalene`；env override 由 `lib/py-env` |
| `sbom:*`  | source, enrich, trivy, grype                                                                                                                                                                   | Source SBOM 產生與漏洞掃描                                                                                                                                                                                                                                                                                                                                                                          |
| `gs:*`    | clone, update                                                                                                                                                                                  | Git submodules                                                                                                                                                                                                                                                                                                                                                                                      |
| `meta:*`  | bump                                                                                                                                                                                           | 清 mise tasks cache 強制重抓 atom includes                                                                                                                                                                                                                                                                                                                                                          |
| `lib/*`   | logs, go-env, py-env                                                                                                                                                                           | 內部 sourced helper library                                                                                                                                                                                                                                                                                                                                                                         |
| `ruler`   | —                                                                                                                                                                                              | 編譯 ruler 至 AGENTS.md / CLAUDE.md                                                                                                                                                                                                                                                                                                                                                                 |

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
| `GO_TEST_TAGS`   | `test`                                                      | `-tags=` build tags（空字串則略過）|
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

> **`.golangci.yml` 例外**：由 consumer repo **自家 commit**（非 curl），須含 `gofumpt.module-path: <repo-module>` 設定（v2.12.2 自動推導對無 `.` 模組名會誤判 stdlib，致 gci↔gofumpt import 互相 false positive）。範本見 `templates/facades/.golangci.yml.template`（如有）或直接 ref 既有 Go repo 範本。

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
      gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}
```

| Input             | Type    | Default          | 用途                                                          |
| ----------------- | ------- | ---------------- | ------------------------------------------------------------- |
| `task`            | string  | required         | mise atom 名稱 (e.g., `go:lint-check`、`ci:semgrep golang`)   |
| `name`            | string  | task             | display name for GH job summary                               |
| `runs_on`         | string  | `'"ubuntu-latest"'` | runner（JSON 經 `fromJSON()` 解析；可傳 `'{"group":"X"}'`） |
| `fetch-depth`     | number  | `1`              | git fetch depth                                               |
| `private-modules` | boolean | `false`          | 啟用 GH PAT git config for private modules                    |

Secret `gh_pat`：required when `private-modules=true`。

每 job 結尾自動 emit `## <name>` block 至 GitHub Actions step summary，含 ✅/❌ 狀態 + `<details>` 包 tail 300 行 stdout/stderr。

---

### Release & Build

| Workflow             | 用途                                                                                                                       |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `go-release.yml`     | Go binary 跨平台建置 + cosign 簽章 + 多平台 SBOM；3 jobs：`prepare` → `build` (matrix) → `release`                          |
| `image-release.yml`  | Docker image dual registry (DockerHub + GHCR) + BuildKit SBOM + SLSA provenance + Sigstore attestation + cosign 簽章       |
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

### Utility

| Workflow                    | 用途                                                          |
| --------------------------- | ------------------------------------------------------------- |
| `artifacts-comment.yml`     | PR 留言列當前 run artifacts，含 [nightly.link](https://nightly.link) 下載連結 |

---

### Meta CI

`ci.yml` — meta repo 自家 CI，透過 `mise-task.yml` matrix 跑 `iac:actionlint` (workflow YAML lint)。

---

## 共用設定檔 (`configs/`)

Atoms 跑時用 `curl` 抓 raw GitHub 設定，跑完 trap cleanup 清除暫存檔。

| 檔案                        | 用途                                       | 由哪些 atom 拉取                          |
| --------------------------- | ------------------------------------------ | ----------------------------------------- |
| `eslint.config.js`          | ESLint flat config + security plugin       | `node:lint-check`, `node:lint-fix`        |
| `.prettierrc.json` + `.prettierignore` | Prettier shared                  | `node:format-check`, `node:format-fix`    |
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

Meta repo 自家 `renovate.json` 額外 customManagers 處理：
- `actions/checkout`, `jdx/mise-action` 等 GitHub Actions 由 native github-actions manager 自動 bump
- `anchore/quill` (go-release.yml) — regex manager
- `snyk/parlay` (sbom-image.yml) — regex manager
- mise [tools] (`actionlint`, `bun`, etc.) — native mise manager

---

## Consumer Repo 設置步驟

1. 從 `templates/facades/mise.<archetype>.toml` (`go-service`/`go-lib`/`frontend`/`python`/`image`) 複製為 repo 自家 `mise.toml`
2. 確認 `[task_config].includes = ["git::https://github.com/nics-dp/meta.git//.mise/tasks?ref=main"]`
3. 加 repo-specific tasks/tools/env at end
4. 寫 `.github/workflows/ci.yml`，用 matrix 呼叫 `nics-dp/meta/.github/workflows/mise-task.yml@main`
5. 設 secrets:
   - `GH_PAT_READ_NICSDP` (Go 私模 + CodeQL private repo + release/snapshot)
   - `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` (Docker image repos)

驗證：`mise tasks ls` 應顯示 ~10 facade 名 + repo-specific extras（atoms hidden）；`mise run --dry-run ci test sbom` resolve 無誤。

---

## 相關文件

- [GitHub: Reusing Workflows](https://docs.github.com/en/actions/learn-github-actions/reusing-workflows)
- [mise: Tasks](https://mise.jdx.dev/tasks/)
