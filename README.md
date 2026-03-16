# meta

nics-dp 組織的共用設定與 CI/CD 基礎設施 repo。本 repo 不包含可建置的程式碼，僅提供 reusable workflows 和共用設定檔給其他 nics-dp repos 使用。

## 內容總覽

| 目錄/檔案 | 說明 |
|-----------|------|
| `.github/workflows/` | Reusable GitHub Actions workflows |
| `configs/` | Sync 來源設定檔 (commitlintrc, renovate, golangci, prettier, eslint, vitest, knip, lighthouserc) |
| `configs/codeqls/` | 各 repo 的 CodeQL workflow 設定 (`<repo-name>.yml`) |
| `golang-templates/` | Go 專案模板 (workflows) |
| `web-templates/` | Web 專案模板 (workflows + `mise.toml`) |
| `renovate-preset.json` | Org-level Renovate 設定 preset |

## 如何引用 Reusable Workflows

Consumer repo 透過 `uses` 呼叫本 repo 的 reusable workflows：

```yaml
jobs:
  lint:
    uses: nics-dp/meta/.github/workflows/go-lint.yml@main
    secrets:
      gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}
```

所有 workflows 固定引用 `@main` 分支。

---

## CI Workflows

### go-lint.yml — 程式碼檢查

執行 `mise run lint` (golangci-lint v2)。

```yaml
uses: nics-dp/meta/.github/workflows/go-lint.yml@main
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}  # 選用，存取私有模組
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `go_private_full` | boolean | `true` | 設定 GOPRIVATE/GONOSUMDB |

---

### go-sec.yml — 靜態安全掃描

執行 `mise run security` (gosec)。

```yaml
uses: nics-dp/meta/.github/workflows/go-sec.yml@main
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `go_private_full` | boolean | `true` | 設定 GOPRIVATE/GONOSUMDB |

---

### go-vulncheck.yml — Go 漏洞檢查

執行 `mise run vulncheck` (govulncheck)。

```yaml
uses: nics-dp/meta/.github/workflows/go-vulncheck.yml@main
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `go_private_full` | boolean | `true` | 設定 GOPRIVATE/GONOSUMDB |

---

### go-semgrep.yml — Semgrep 靜態分析 (Go)

使用 Semgrep 對 Go 程式碼進行靜態安全掃描。

```yaml
uses: nics-dp/meta/.github/workflows/go-semgrep.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `config` | string | `p/golang` | Semgrep config/ruleset (空格分隔，支援多組) |

---

### go-test.yml — 單元測試

執行 `mise run test`，可選產出覆蓋率報告。

```yaml
uses: nics-dp/meta/.github/workflows/go-test.yml@main
with:
  run_report: true  # 選用，產出覆蓋率報告
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `go_private_full` | boolean | `true` | 設定 GOPRIVATE/GONOSUMDB |
| `test_command` | string | `mise run test` | 測試指令 (需產出 `coverage.out`) |
| `run_report` | boolean | `false` | 是否執行 report job |
| `report_command` | string | `mise run report` | 覆蓋率報告指令 |

**前提:** Consumer repo 的 mise.toml 需有 `test` task，且產出 `coverage.out`。

---

### bun-lint.yml — ESLint 檢查

執行 `mise run lint` (內部預設呼叫 `bun run lint`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-lint.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `lint` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-typecheck.yml — TypeScript 型別檢查

執行 `mise run typecheck` (內部預設呼叫 `bun run typecheck`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-typecheck.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `typecheck` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-build.yml — 建置

執行 `mise run build` (內部預設呼叫 `bun run build`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-build.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `build` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-audit.yml — 依賴漏洞檢查

執行 `mise run audit` (內部預設呼叫 `bun audit`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-audit.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `audit` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-test.yml — 單元測試

執行 `mise run test` (內部預設呼叫 `bun run test:coverage`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-test.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `test` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-format-check.yml — 格式檢查

執行 `mise run format-check` (內部預設呼叫 `bun run format:check`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-format-check.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `format-check` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-knip.yml — Dead Code 檢查

執行 `mise run knip` (內部預設呼叫 `bun run knip`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-knip.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `knip` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-lighthouse.yml — Lighthouse CI

執行 `mise run lighthouse`。

```yaml
uses: nics-dp/meta/.github/workflows/bun-lighthouse.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `lighthouse` | `mise` task 名稱 |
| `build_command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-bundle-size.yml — Bundle Size 檢查

執行 `mise run bundle-size`。

```yaml
uses: nics-dp/meta/.github/workflows/bun-bundle-size.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `bundle-size` | `mise` task 名稱 |
| `build_command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-semgrep.yml — Semgrep 靜態分析 (Web)

使用 Semgrep 對 JavaScript/TypeScript 程式碼進行靜態安全掃描。

```yaml
uses: nics-dp/meta/.github/workflows/bun-semgrep.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `config` | string | `p/javascript p/typescript` | Semgrep config/ruleset (空格分隔，支援多組) |

---

### codeql.yml — CodeQL 分析 (集中管理)

各 repo 的 CodeQL workflow 為**獨立可執行**的 workflow (直接使用 `github/codeql-action`)，集中管理於 `configs/codeqls/<repo-name>.yml`，透過 `sync-codeql.yml` 同步到各 repo 的 `.github/workflows/codeql.yml`。

每個 repo 的 codeql.yml 可依需要自訂：語言 matrix、Go build 指令、額外工具安裝等。詳見 `configs/codeqls/` 目錄下各檔案。

- **Go repos:** 使用 `go` language + `manual` build-mode
- **Web repos:** 使用 `javascript-typescript` language + `none` build-mode

私有 repo 可設定 `GH_PAT_READ_NICSDP` 以存取 private modules / private repositories；未設定時，CodeQL 仍會執行，但不會傳 `external-repository-token`，也不會啟用 private module access 設定。

> **注意:** `.github/workflows/codeql.yml` (reusable workflow) 仍保留供特殊場景使用，但建議優先使用 `configs/codeqls/` per-repo configs。

#### codeql.yml reusable workflow 參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `languages` | string | `[{"language":"actions","build-mode":"none"},{"language":"go","build-mode":"manual"}]` | JSON array of `{language, build-mode}` objects |
| `go_build_commands` | string | `go mod download && go build ./...` | Go build 指令 (支援多行) |
| `go_install_tools` | string | `""` | Build 前安裝工具的指令 (支援多行) |
| `go_cgo_enabled` | boolean | `false` | 啟用 CGO |
| `go_install_system_deps` | boolean | `false` | 安裝 `build-essential` 和 `pkg-config` |

---

## Release & Build Workflows

### go-release.yml — Go Binary 發布

多平台交叉編譯、cosign 簽章、SBOM 產出。3 個 jobs: `prepare` → `build` (matrix) → `release`。

```yaml
# 單一 binary
uses: nics-dp/meta/.github/workflows/go-release.yml@main
permissions:
  contents: write
  id-token: write
with:
  project_name: dcf-platform
  binary: "platform:./cmd/platform"
  cgo_enabled: true
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}

# 多 binary
with:
  project_name: dcf-platform-cli
  binary: "tui:./cmd/tui,node:./cmd/node,dataset:./cmd/dataset"
```

| 參數 | 類型 | 預設值 | 必要 | 說明 |
|------|------|--------|------|------|
| `project_name` | string | — | **是** | 專案名稱 (影響 archive 命名) |
| `binary` | string | — | **是** | Binary 建置清單 (`name:path,...`) |
| `platforms` | string | `linux/amd64,linux/arm64,darwin/amd64,darwin/arm64,windows/amd64` | 否 | 目標平台 |
| `go_version` | string | `stable` | 否 | Go 版本 (由 mise.toml 決定，通常不需覆寫) |
| `cgo_enabled` | boolean | `false` | 否 | 啟用 CGO |
| `go_env` | string | `GOEXPERIMENT=jsonv2,simd,runtimesecret,goroutineleakprofile` | 否 | 建置環境變數 |
| `ldflags` | string | `""` | 否 | 自訂 ldflags (預設注入 version/commit/date) |
| `extra_build_flags` | string | `-trimpath` | 否 | 額外 go build flags |
| `go_private_full` | boolean | `true` | 否 | 設定 GOPRIVATE/GONOSUMDB |
| `notarize` | boolean | `false` | 否 | macOS notarize (需 quill secrets) |
| `snapshot` | boolean | `false` | 否 | 預覽建置 (不上傳 Release) |
| `ref` | string | `""` | 否 | Git ref (預設使用事件 ref) |
| `runs_on` | string | `"ubuntu-latest"` | 否 | Runner (JSON 格式) |

**必要 Secrets:**
- `gh_pat` — 存取私有模組
- macOS notarize (當 `notarize: true`): `quill_sign_p12`, `quill_sign_password`, `quill_notary_key`, `quill_notary_key_id`, `quill_notary_issuer`

---

### image-release.yml — Container Image 建置

建置 Docker image 並推送至 DockerHub + GHCR，支援 Trivy/Grype 掃描和 attestation。

```yaml
uses: nics-dp/meta/.github/workflows/image-release.yml@main
permissions:
  contents: read
  packages: write
  attestations: write
  id-token: write
  security-events: write
with:
  image_name: dcf-platform                    # 必要
  runs_on: '{"group":"releasers"}'            # 選用
  run_trivy: true                             # 選用
  run_grype: true                             # 選用
secrets:
  dockerhub_username: ${{ secrets.DOCKERHUB_USERNAME }}  # 必要
  dockerhub_token: ${{ secrets.DOCKERHUB_TOKEN }}        # 必要
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}              # 選用
```

| 參數 | 類型 | 預設值 | 必要 | 說明 |
|------|------|--------|------|------|
| `image_name` | string | — | **是** | Docker image 名稱 |
| `platforms` | string | `linux/amd64,linux/arm64` | 否 | 目標平台 |
| `runs_on` | string | `"ubuntu-latest"` | 否 | Runner (JSON，使用 `fromJSON()` 解析) |
| `context` | string | `.` | 否 | Docker build context 路徑 |
| `build_args` | string | `""` | 否 | Docker build-args (多行 key=value) |
| `env_file` | string | `""` | 否 | Env 檔案路徑 (載入為 build-args) |
| `run_trivy` | boolean | `false` | 否 | 執行 Trivy 漏洞掃描 |
| `trivy_exit_code` | number | `0` | 否 | Trivy 發現漏洞時的 exit code |
| `run_grype` | boolean | `false` | 否 | 執行 Grype 漏洞掃描 |
| `grype_fail_on` | string | `""` | 否 | Grype 失敗嚴重度門檻 |
| `provenance` | boolean | `true` | 否 | 啟用 SLSA provenance attestation |
| `attest` | boolean | `true` | 否 | 啟用 Sigstore artifact attestation |
| `ref` | string | `""` | 否 | Git ref |

**必要 Secrets:** `dockerhub_username`, `dockerhub_token`
**選用 Secrets:** `gh_pat` (Dockerfile 中存取私有模組時需要)

**Image 推送目標:**
- `docker.io/nicsdp/<image_name>`
- `ghcr.io/nics-dp/<image_name>`

**Tag 策略:** branch ref, PR ref, semver (`v1.2.3`, `v1.2`, `v1`), `latest`

---

## Sync Workflows (設定檔同步)

Sync workflows 由 meta repo 的 `cron.yml` 統一排程觸發 (每週一 00:00 UTC)，使用 matrix 對 consumer repos 執行同步。Consumer repos 不需要在自己的 repo 中呼叫這些 workflows。

目標 repo 清單定義在 `cron.yml` 頂部：

| 清單 | 說明 | 用於 |
|------|------|------|
| `ALL_REPOS` | 所有 DCF repos (含 patroni) | sync-commitlintrc |
| `RENOVATE_SYNC_REPOS` | 需要同步 `renovate.json` 的 repos | sync-renovate |
| `GO_REPOS` | Go repos (不含 web repos、patroni) | sync-golangci |
| `WEB_REPOS` | Web repos | sync-prettier, sync-eslint-config, sync-vitest-config, sync-knip, sync-lighthouserc |
| `CODEQL_REPOS` | 有 CodeQL 設定的 repos (不含 patroni) | sync-codeql |

### All repos

| Workflow | 來源 | 目標 |
|----------|------|------|
| `sync-commitlintrc.yml` | `configs/.commitlintrc.yml` | `.commitlintrc.yml` |

### Renovate sync repos

| Workflow | 來源 | 目標 |
|----------|------|------|
| `sync-renovate.yml` | `configs/renovate.json` | `renovate.json` |

### CodeQL repos

| Workflow | 來源 | 目標 |
|----------|------|------|
| `sync-codeql.yml` | `configs/codeqls/<repo>.yml` | `.github/workflows/codeql.yml` |

### Go repos

| Workflow | 來源 | 目標 |
|----------|------|------|
| `sync-golangci.yml` | `configs/.golangci.yml` | `.golangci.yml` |

### Web repos

| Workflow | 來源 | 目標 |
|----------|------|------|
| `sync-prettier.yml` | `configs/.prettierrc.json` + `configs/.prettierignore` | `.prettierrc.json` + `.prettierignore` |
| `sync-eslint-config.yml` | `configs/eslint.config.js` | `eslint.config.js` |
| `sync-vitest-config.yml` | `configs/vitest.config.ts` | `vitest.config.ts` |
| `sync-knip.yml` | `configs/knip.json` | `knip.json` |
| `sync-lighthouserc.yml` | `configs/lighthouserc.json` | `lighthouserc.json` |

所有 sync workflows 共用相同模式：

```yaml
uses: nics-dp/meta/.github/workflows/sync-<name>.yml@main
permissions:
  contents: write
  pull-requests: write
with:
  repo_name: <repo-name>  # 必要，不含 org prefix
secrets:
  gh_token: ${{ secrets.GH_PAT_READ_NICSDP }}
```

`workflow_dispatch` 手動執行時，若要同步到 private repo，需先在 meta repo 設定 repo-level `GH_PAT_READ_NICSDP`。

---

## Utility Workflows

### artifacts-comment.yml — PR Artifacts 留言

列出當前 workflow run 的所有 build artifacts，以 sticky comment 回覆到 PR，提供 [nightly.link](https://nightly.link) 下載連結。

```yaml
uses: nics-dp/meta/.github/workflows/artifacts-comment.yml@main
permissions:
  actions: read
  pull-requests: write
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `pr_number` | number | `0` | PR 編號 (自動偵測 `pull_request` / `workflow_run` 事件) |

支援兩種情境：
- **`pull_request` 觸發的 workflow** — 自動偵測 PR 編號
- **`workflow_run` 觸發的 workflow** (如 snapshot) — 從 `workflow_run.pull_requests` 自動偵測

---

### notify-gchat.yml — Google Chat 通知

發送 Google Chat 卡片通知。

```yaml
uses: nics-dp/meta/.github/workflows/notify-gchat.yml@main
with:
  type: pr                    # 必要: pr | push | release | issue | ci-failure | ci-success
  title: "PR #1: Title"       # 必要
  url: "https://..."          # 必要
  actor: "username"            # 選用 (預設 github.actor)
  body: "description"          # 選用
  extra_fields: '[{"label":"Branch","value":"main"}]'  # 選用
secrets:
  google_chat_webhook: ${{ secrets.GOOGLE_CHAT_WEBHOOK }}
```

---

### check-managed-files.yml — 集中管理檔案保護

檢查 PR 是否修改了由 meta 集中管理的檔案，若有則 CI 失敗。自動跳過 sync workflow 建立的 PR (`ci/sync-*` 分支)。

```yaml
uses: nics-dp/meta/.github/workflows/check-managed-files.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `managed_files` | string | `.github/workflows/codeql.yml,.commitlintrc.yml,.golangci.yml,renovate.json` | 逗號分隔的受保護檔案路徑 |

---

### check-upstream-release.yml — 上游版本檢查

檢查上游 repo 是否有新 release，自動建立 bump PR。

```yaml
uses: nics-dp/meta/.github/workflows/check-upstream-release.yml@main
permissions:
  contents: write
  pull-requests: write
with:
  upstream_repo: patroni/patroni     # 必要
  version_file: Dockerfile.env       # 必要
  version_variable: PATRONI_VERSION  # 必要
secrets:
  gh_token: ${{ secrets.GH_PAT_READ_NICSDP }}
```

| 參數 | 類型 | 預設值 | 必要 | 說明 |
|------|------|--------|------|------|
| `upstream_repo` | string | — | **是** | 上游 repo (例如 `patroni/patroni`) |
| `version_file` | string | — | **是** | 版本號檔案路徑 |
| `version_variable` | string | — | **是** | 版本號變數名稱 |
| `release_suffix` | string | `.dcf` | 否 | Release tag 後綴 |

---

## 共用設定檔 (`configs/`)

所有 sync 來源設定檔集中管理於 `configs/` 目錄：

| 檔案 | 同步目標 | 適用 |
|------|----------|------|
| `configs/codeqls/<repo>.yml` | `.github/workflows/codeql.yml` | Per-repo |
| `configs/.commitlintrc.yml` | `.commitlintrc.yml` | All repos |
| `configs/renovate.json` | `renovate.json` | `RENOVATE_SYNC_REPOS` |
| `configs/.golangci.yml` | `.golangci.yml` | Go repos |
| `configs/.prettierrc.json` | `.prettierrc.json` | Web repos |
| `configs/.prettierignore` | `.prettierignore` | Web repos |
| `configs/eslint.config.js` | `eslint.config.js` | Web repos |
| `configs/vitest.config.ts` | `vitest.config.ts` | Web repos |
| `configs/knip.json` | `knip.json` | Web repos |
| `configs/lighthouserc.json` | `lighthouserc.json` | Web repos |

---

## 專案模板

### golang-templates/ — Go 專案

適用於 Go service、CLI、library 專案。詳見 [`golang-templates/.github/README.md`](golang-templates/.github/README.md)。

包含: CI (lint, sec, vulncheck, semgrep, test), release, snapshot, codeql, notify, release-please workflows + `mise.toml` + `.golangci.yml`

### web-templates/ — Web 專案

適用於 React + Vite + TypeScript + Bun 專案。包含 workflow templates 與 `mise.toml`。詳見 [`web-templates/.github/README.md`](web-templates/.github/README.md)。

包含: CI (eslint, typecheck, build, audit, vitest, prettier, semgrep, trivy-license), codeql, notify, release-please workflows + `mise.toml` + eslint, prettier, vitest, knip, lighthouse configs

---

## Consumer Repo 新增步驟

### Go 專案

1. 從 `golang-templates/.github/` 複製 workflows，並複製 `golang-templates/mise.toml`
2. 從 `configs/` 複製 `.golangci.yml`、`.commitlintrc.yml`、`renovate.json`
3. 替換 `TODO` 標記 (`project_name`, `binary`, `image_name`)
4. 新增 `configs/codeqls/<repo-name>.yml`，設定 CodeQL workflow
5. 更新 `cron.yml` 的 repo 清單 (`CODEQL_REPOS`, `GO_REPOS`, `ALL_REPOS`)
6. 確認 repo secrets: `GH_PAT_READ_NICSDP`, `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`

### Web 專案

1. 從 `web-templates/.github/` 複製 workflows，並複製 `web-templates/mise.toml`
2. 從 `configs/` 複製所有 web 設定檔 (`.prettierrc.json`, `.prettierignore`, `eslint.config.js`, `vitest.config.ts`, `knip.json`, `lighthouserc.json`, `.commitlintrc.yml`, `renovate.json`)
3. 安裝 devDependencies (見 `web-templates/.github/README.md`)
4. 新增 `configs/codeqls/<repo-name>.yml` (使用 `javascript-typescript` language)
5. 更新 `cron.yml` 的 repo 清單 (`CODEQL_REPOS`, `WEB_REPOS`, `ALL_REPOS`, `RENOVATE_SYNC_REPOS`)
6. 確認 repo secrets: `GH_PAT_READ_NICSDP`

---

## Consumer Repo 前提條件

### Go repos

1. **mise.toml** — 定義 `prepare`, `lint`, `security`, `test`, `vulncheck`, `report` tasks (建議直接使用 `golang-templates/mise.toml`)
2. **coverage.out** — `mise run test` 需產出此檔案 (go-test.yml 預期此路徑)
3. **Go module** — go.mod 存在且版本正確
4. **Private module access** — `GH_PAT_READ_NICSDP` secret 已設定

### Web repos

1. **mise.toml** — 建議直接使用 `web-templates/mise.toml`
2. **bun.lock** — 使用 Bun 作為 package manager
3. **package.json scripts** — 需包含 `lint`, `typecheck`, `build`, `test:coverage`, `format:check`
4. **Private access** — `GH_PAT_READ_NICSDP` secret 已設定 (用於 release-please)

## 相關文件

- [GitHub: Reusing Workflows](https://docs.github.com/en/actions/learn-github-actions/reusing-workflows)
