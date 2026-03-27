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

PR 時使用 reviewdog inline annotation，非 PR 時執行 `mise run ci:go-lint` (golangci-lint v2)。

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

執行 gosec 靜態安全掃描，結果以 sticky PR comment 回報。

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

執行 `mise run ci:go-vulncheck` (govulncheck)，結果以 sticky PR comment 回報。

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

執行 `mise run ci:test`，可選產出覆蓋率報告。

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
| `test_command` | string | `mise run ci:test` | 測試指令 (需產出 `coverage.out`) |
| `run_report` | boolean | `false` | 是否執行 report job |

**前提:** Consumer repo 的 mise.toml 需有 `ci:test` task，且產出 `coverage.out`。

---

### hadolint.yml — Dockerfile Lint

PR-only，使用 reviewdog 對 Dockerfile 進行 inline annotation。自動偵測 `Dockerfile*` (排除 `*.env`)。

```yaml
uses: nics-dp/meta/.github/workflows/hadolint.yml@main
```

無需額外輸入參數。

---

### trivy-iac.yml — IaC 安全掃描

對 Dockerfile 和 compose 檔案執行 Trivy config scan，產出 SARIF + sticky PR comment。

```yaml
uses: nics-dp/meta/.github/workflows/trivy-iac.yml@main
permissions:
  actions: read
  contents: read
  pull-requests: write
  security-events: write
```

無需額外輸入參數。呼叫端須授予 `actions: read`、`contents: read`、`pull-requests: write` 與 `security-events: write` 權限。

---

### trivy-license.yml — License 合規檢查

執行 Trivy fs scan 檢查依賴 license 合規性。

```yaml
uses: nics-dp/meta/.github/workflows/trivy-license.yml@main
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}  # 選用，Go repos 存取私有模組
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `go_private_full` | boolean | `true` | 設定 GOPRIVATE/GONOSUMDB |

> Web repos 不需要傳 `gh_pat`，因為不存取私有 Go modules。

---

### commitlint.yml — Commit 訊息驗證

PR-only，使用 wagoid/commitlint-github-action 驗證 conventional commits。

```yaml
uses: nics-dp/meta/.github/workflows/commitlint.yml@main
permissions:
  contents: read
  pull-requests: read
```

無需額外輸入參數。呼叫端須授予 `contents: read` 與 `pull-requests: read` 權限。

---

### actionlint.yml — Workflow YAML Lint

PR 時使用 reviewdog inline annotation，非 PR 時輸出至 step summary。

```yaml
uses: nics-dp/meta/.github/workflows/actionlint.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `actionlint-version` | string | `v1.7.11` | actionlint 版本 (僅非 PR 路徑使用) |

---

### check-managed-files.yml — 集中管理檔案保護

檢查 PR 是否修改了由 meta 集中管理的檔案，若有則 CI 失敗。自動跳過 sync workflow 建立的 PR (`feature/sync-ci-*` 分支)。

```yaml
uses: nics-dp/meta/.github/workflows/check-managed-files.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `managed_files` | string | (見下方) | 逗號分隔的受保護檔案路徑 |

預設受保護檔案: `.github/workflows/codeql.yml`, `.commitlintrc.yml`, `.golangci.yml`, `.prettierrc.json`, `.prettierignore`, `eslint.config.js`, `vitest.config.ts`, `knip.json`, `lighthouserc.json`

---

### bun-lint.yml — ESLint 檢查

執行 `mise run ci:lint` (內部預設呼叫 `bun run lint`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-lint.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `ci:lint` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-typecheck.yml — TypeScript 型別檢查

執行 `mise run ci:typecheck` (內部預設呼叫 `bun run typecheck`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-typecheck.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `ci:typecheck` | `mise` task 名稱 |
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

執行 `mise run ci:audit` (內部預設呼叫 `bun audit`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-audit.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `ci:audit` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-test.yml — 單元測試

執行 `mise run ci:test` (內部預設呼叫 `bun run test:coverage`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-test.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `ci:test` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-format-check.yml — 格式檢查

執行 `mise run ci:format-check` (內部預設呼叫 `bun run format:check`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-format-check.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `ci:format-check` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-knip.yml — Dead Code 檢查

執行 `mise run ci:knip` (內部預設呼叫 `bun run knip`)。

```yaml
uses: nics-dp/meta/.github/workflows/bun-knip.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `ci:knip` | `mise` task 名稱 |
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
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

---

### bun-bundle-size.yml — Bundle Size 檢查

執行 `mise run bundle-size`。

```yaml
uses: nics-dp/meta/.github/workflows/bun-bundle-size.yml@main
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `task` | string | `bundle-size` | `mise` task 名稱 |
| `command` | string | `""` | 選用，直接覆寫 shell 指令 |

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

> **注意:** 大多數 repos 使用 `configs/codeqls/` 下的 per-repo configs (透過 `sync-codeql` 同步)。此 reusable workflow 保留供特殊場景使用。

各 repo 的 CodeQL workflow 為**獨立可執行**的 workflow (直接使用 `github/codeql-action`)，集中管理於 `configs/codeqls/<repo-name>.yml`，透過 `sync-codeql.yml` 同步到各 repo 的 `.github/workflows/codeql.yml`。

每個 repo 的 codeql.yml 可依需要自訂：語言 matrix、Go build 指令、額外工具安裝等。詳見 `configs/codeqls/` 目錄下各檔案。

- **Go repos:** 使用 `go` language + `manual` build-mode
- **Web repos:** 使用 `javascript-typescript` language + `none` build-mode

私有 repo 可設定 `GH_PAT_READ_NICSDP` 以存取 private modules / private repositories；未設定時，CodeQL 仍會執行，但不會傳 `external-repository-token`，也不會啟用 private module access 設定。PAT 僅限定於需要的 steps (CodeQL init 和 Git URL rewrite)，不會暴露給 caller 提供的 build commands。Git URL rewrite 僅作用於 `github.com/nics-dp` 範圍 (HTTPS 與 SSH)。

#### codeql.yml reusable workflow 參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `languages` | string | `[{"language":"actions","build-mode":"none"},{"language":"go","build-mode":"manual"}]` | JSON array of `{language, build-mode}` objects |
| `go_build_commands` | string | `go mod download`<br>`go build ./...` | Go build 指令 (支援多行) |
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
  runs_on: '{"group":"releasers"}'  # 選用
secrets:
  gh_pat: ${{ secrets.GH_PAT_READ_NICSDP }}  # 選用；若需要存取私有模組，通常傳 read PAT

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
| `go_version` | string | `stable` | 否 | Go 版本 (`actions/setup-go` 使用的版本字串) |
| `cgo_enabled` | boolean | `false` | 否 | 啟用 CGO；啟用時建議同時把 `platforms` 覆寫為僅 Linux 目標 |
| `go_env` | string | `GOEXPERIMENT=jsonv2,simd,runtimesecret,goroutineleakprofile` | 否 | 建置環境變數 |
| `ldflags` | string | `""` | 否 | 自訂 ldflags (預設注入 version/commit/date) |
| `extra_build_flags` | string | `-trimpath` | 否 | 額外 go build flags |
| `go_private_full` | boolean | `true` | 否 | 設定 GOPRIVATE/GONOSUMDB |
| `notarize` | boolean | `false` | 否 | macOS notarize (需 quill secrets) |
| `snapshot` | boolean | `false` | 否 | 預覽建置模式；版本會改用 `0.0.0-snapshot+<sha>`，不上傳 GitHub Release |
| `ref` | string | `""` | 否 | Git ref (預設使用事件 ref) |
| `runs_on` | string | `"ubuntu-latest"` | 否 | Runner (JSON 格式，經 `fromJSON()` 解析) |

**選用 Secrets:**
- `gh_pat` — 存取私有模組；consumer repo 的 `release.yml` / `snapshot.yml` 通常傳 `GH_PAT_READ_NICSDP`
- macOS notarize (當 `notarize: true`): `quill_sign_p12`, `quill_sign_password`, `quill_notary_key`, `quill_notary_key_id`, `quill_notary_issuer`

---

### image-release.yml — Container Image 建置

建置 Docker image 並推送至 DockerHub + GHCR，支援 attestation 和 cosign 簽章。

```yaml
uses: nics-dp/meta/.github/workflows/image-release.yml@main
permissions:
  contents: read
  packages: write
  attestations: write
  id-token: write
with:
  image_name: dcf-platform                    # 必要
  runs_on: '{"group":"releasers"}'            # 選用
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
| `sbom` | boolean | `true` | 否 | 啟用 BuildKit SBOM 產生 |
| `provenance` | boolean | `true` | 否 | 啟用 SLSA provenance attestation |
| `attest` | boolean | `true` | 否 | 啟用 Sigstore artifact attestation |
| `cosign` | boolean | `true` | 否 | 使用 cosign 簽章 (keyless) |
| `snapshot` | boolean | `false` | 否 | 僅使用 SHA tag (不含 semver/latest) |
| `ref` | string | `""` | 否 | Git ref |

**Outputs:** `digest` — Image digest (`sha256:...`)，供 `sbom-image.yml` 使用

**必要 Secrets:** `dockerhub_username`, `dockerhub_token`
**選用 Secrets:** `gh_pat` (Dockerfile 中存取私有模組時需要)

**Image 推送目標:**
- `docker.io/nicsdp/<image_name>`
- `ghcr.io/nics-dp/<image_name>`

**Tag 策略:**

根據 `snapshot` 輸入和 git ref，依優先順序套用以下三種模式：

| 模式 | 條件 | 產生的 Tag | 範例 |
|------|------|-----------|------|
| Snapshot | `inputs.snapshot == true` | commit SHA (短 + 長) | `abc1234`, `abc1234567890def` |
| Release | ref 是 tag (`refs/tags/v*`) | semver 三層 + `latest` | `v1.2.3`, `v1.2`, `v1` |
| Fallback | 其他情況 | branch 名稱或 PR 編號 | `main`, `pr-42` |

> **實作細節：** 因為此 workflow 透過 `workflow_call` 呼叫，`github.event_name` 是 `workflow_call` 而非 `release`，
> 所以 release 偵測使用 `startsWith(github.ref, 'refs/tags/')` 而非檢查 event name。
> semver pattern 中的 `{{{{raw}}}}` 是因為 `format()` 將 `{{` 轉義為字面 `{`，最終產生 metadata-action 認得的 `{{raw}}`。

---

### release-please.yml — 自動 Release 管理

使用 googleapis/release-please-action，依據 conventional commits 自動建立 Release PR (含 changelog)，merge 後建立 GitHub Release + tag。

```yaml
uses: nics-dp/meta/.github/workflows/release-please.yml@main
secrets:
  gh_pat: ${{ secrets.GH_PAT_RELEASE_NICSDP }}  # 必要，GITHUB_TOKEN 不會觸發下游 workflows
```

| 參數 | 類型 | 預設值 | 必要 | 說明 |
|------|------|--------|------|------|
| `release_type` | string | `simple` | 否 | Release type (`simple`, `go`, `node` 等) |

**必要 Secrets:** `gh_pat` — 需要 `contents:write` + `pull-requests:write` 的 PAT

**Outputs:** `release_created` (boolean), `tag_name` (string)

---

### sbom-source.yml — Source Code SBOM

產出 CycloneDX 1.6 SBOM + parlay 增強 + Trivy/Grype 漏洞掃描，上傳至 GitHub Release 與 GitHub Security tab。非 snapshot 模式時，`anchore/sbom-action` 也會提交 dependency snapshot。

```yaml
uses: nics-dp/meta/.github/workflows/sbom-source.yml@main
permissions:
  actions: read
  contents: write
  security-events: write
with:
  project_name: dcf-platform  # 必要
```

| 參數 | 類型 | 預設值 | 必要 | 說明 |
|------|------|--------|------|------|
| `project_name` | string | — | **是** | 專案名稱 (影響 artifact 命名) |
| `scan_path` | string | `.` | 否 | 掃描目錄 |
| `ref` | string | `""` | 否 | Git ref |
| `snapshot` | boolean | `false` | 否 | Snapshot 模式 (不上傳 Release) |
| `runs_on` | string | `"ubuntu-latest"` | 否 | Runner (JSON 格式) |

---

### sbom-image.yml — Container Image SBOM

對 container image 產出 CycloneDX 1.6 SBOM + Trivy/Grype 漏洞掃描，上傳至 GitHub Release 與 GitHub Security tab。

```yaml
uses: nics-dp/meta/.github/workflows/sbom-image.yml@main
permissions:
  actions: read
  contents: write
  packages: read
  security-events: write
with:
  project_name: dcf-platform                                    # 必要
  image_name: dcf-platform                                      # 必要
  digest: ${{ needs.image-build.outputs.digest }}                # 必要
```

| 參數 | 類型 | 預設值 | 必要 | 說明 |
|------|------|--------|------|------|
| `project_name` | string | — | **是** | 專案名稱 (影響 artifact 命名) |
| `image_name` | string | — | **是** | Docker image 名稱 |
| `digest` | string | — | **是** | Image digest (`sha256:...`) |
| `ref` | string | `""` | 否 | Git ref |
| `snapshot` | boolean | `false` | 否 | Snapshot 模式 (不上傳 Release) |
| `runs_on` | string | `"ubuntu-latest"` | 否 | Runner (JSON 格式) |

---

## Sync Workflows (設定檔同步)

Sync workflows 由 meta repo 的 `cron.yml` 統一排程觸發 (每週一 00:00 UTC)，使用 matrix 對 consumer repos 執行同步。Consumer repos 不需要在自己的 repo 中呼叫這些 workflows。

目標 repo 清單定義在 `cron.yml` 頂部：

| 清單 | 說明 | 用於 |
|------|------|------|
| `ALL_REPOS` | 所有 DCF repos (含 patroni) | sync-commitlintrc |
| `GO_REPOS` | Go repos (不含 web repos、patroni) | sync-golangci |
| `WEB_REPOS` | Web repos | sync-prettier, sync-eslint-config, sync-vitest-config, sync-knip, sync-lighthouserc |
| `CODEQL_REPOS` | 有 CodeQL 設定的 repos (不含 patroni) | sync-codeql |

### All repos

| Workflow | 來源 | 目標 |
|----------|------|------|
| `sync-commitlintrc.yml` | `configs/.commitlintrc.yml` | `.commitlintrc.yml` |

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
with:
  repo_name: <repo-name>  # 必要，不含 org prefix
secrets:
  gh_token: ${{ secrets.GH_PAT_SYNC_NICSDP }}
```

`workflow_dispatch` 手動執行時，若要同步到 private repo，需先在 meta repo 設定 repo-level `GH_PAT_SYNC_NICSDP`。

---

## Utility Workflows

### artifacts-comment.yml — PR Artifacts 留言

列出當前 workflow run 的所有 build artifacts，以 sticky comment 回覆到 PR，提供 [nightly.link](https://nightly.link) 下載連結。

```yaml
uses: nics-dp/meta/.github/workflows/artifacts-comment.yml@main
permissions:
  actions: read
  issues: write
  pull-requests: write
```

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| `pr_number` | number | `0` | PR 編號 (自動偵測 `pull_request` / `workflow_run` 事件) |

會在 PR 上建立或更新同一則 comment，支援兩種情境：
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
  repository: "org/repo"       # 選用 (預設 github.repository)
  body: "description"          # 選用
  extra_fields: '[{"label":"Branch","value":"main"}]'  # 選用
secrets:
  google_chat_webhook: ${{ secrets.GOOGLE_CHAT_WEBHOOK }}
```

---

### check-upstream-release.yml — 上游版本檢查

檢查上游 repo 是否有新 release，自動建立 bump PR。

```yaml
uses: nics-dp/meta/.github/workflows/check-upstream-release.yml@main
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
| `configs/renovate.json` | `renovate.json` | 手動複製 |
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

包含: CI (lint, sec, vulncheck, semgrep, test, trivy-license；service repo 另含 hadolint / trivy-iac), release, snapshot, codeql, notify, release-please workflows + `mise.toml` + `.golangci.yml`

### web-templates/ — Web 專案

適用於 Vue + Vite + TypeScript + Bun 專案。包含 workflow templates 與 `mise.toml`。詳見 [`web-templates/.github/README.md`](web-templates/.github/README.md)。

包含: CI (eslint, typecheck, build, audit；預設也啟用 vitest、prettier、semgrep、trivy-license、knip、lighthouse；有 Dockerfile 的 repo 還可保留 hadolint / trivy-iac), codeql, notify, release-please workflows + `mise.toml` + eslint, prettier, vitest, knip, lighthouse configs。`bundle-size` workflow 仍提供，但需 repo 自行補上 `size-limit` 設定後再啟用

---

## Consumer Repo 新增步驟

### Go 專案

1. 從 `golang-templates/.github/` 複製 workflows，並複製 `golang-templates/mise.toml`
2. 從 `configs/` 複製 `.golangci.yml`、`.commitlintrc.yml`、`renovate.json`
3. 替換 `TODO` 標記 (`project_name`, `binary`, `image_name`)
4. 新增 `configs/codeqls/<repo-name>.yml`，設定 CodeQL workflow
5. 更新 `cron.yml` 的 repo 清單 (`CODEQL_REPOS`, `GO_REPOS`, `ALL_REPOS`)
6. 確認 repo secrets:
   - `GH_PAT_READ_NICSDP` (私有 Go modules / release / snapshot / CodeQL 用)
   - `GH_PAT_RELEASE_NICSDP` (release-please 用)
   - `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN` (僅 Docker image repos 需要)

### Web 專案

1. 從 `web-templates/.github/` 複製 workflows，並複製 `web-templates/mise.toml`
2. 從 `configs/` 複製所有 web 設定檔 (`.prettierrc.json`, `.prettierignore`, `eslint.config.js`, `vitest.config.ts`, `knip.json`, `lighthouserc.json`, `.commitlintrc.yml`, `renovate.json`)
3. 安裝 devDependencies (見 `web-templates/.github/README.md`)
4. 若 repo 沒有 Dockerfile，先從 `web-templates/.github/workflows/ci.yml` 移除 `hadolint` 與 `trivy-iac` jobs；若不需要 `knip` / `lighthouse`，也可一併移除
5. 新增 `configs/codeqls/<repo-name>.yml` (使用 `javascript-typescript` language)
6. 更新 `cron.yml` 的 repo 清單 (`CODEQL_REPOS`, `WEB_REPOS`, `ALL_REPOS`)
7. 確認 repo secrets: `GH_PAT_RELEASE_NICSDP`

---

## Consumer Repo 前提條件

### Go repos

1. **mise.toml** — 定義 `init`, `ci:go-lint`, `ci:go-sec`, `ci:go-vulncheck`, `ci:test` 等 CI tasks (建議直接使用 `golang-templates/mise.toml`)
2. **coverage.out** — `mise run ci:test` 需產出此檔案 (go-test.yml 預期此路徑)
3. **Go module** — go.mod 存在且版本正確
4. **Private module access** — 若 repo 會引用私有 `nics-dp` modules，需設定 `GH_PAT_READ_NICSDP`

### Web repos

1. **mise.toml** — 建議直接使用 `web-templates/mise.toml`
2. **bun.lock** — 使用 Bun 作為 package manager
3. **package.json scripts** — 需包含 `lint`, `typecheck`, `build`, `test:coverage`, `format:check`
4. **選用 scripts / configs** — 若保留 `knip`、`lighthouse` 或之後啟用 `bundle-size`，需補齊對應 script 與設定檔
5. **Release token** — `GH_PAT_RELEASE_NICSDP` secret 已設定 (供 release-please 建立 release/tag 並觸發下游 workflows)

## 相關文件

- [GitHub: Reusing Workflows](https://docs.github.com/en/actions/learn-github-actions/reusing-workflows)
