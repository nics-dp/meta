# meta

nics-dp 組織的共用設定與 CI/CD 基礎設施 repo。本 repo 不包含可建置的程式碼，僅提供 reusable workflows 和共用設定檔給其他 nics-dp repos 使用。

## 內容總覽

| 目錄/檔案 | 說明 |
|-----------|------|
| `.github/workflows/` | Reusable GitHub Actions workflows |
| `codeqls/` | 各 repo 的 CodeQL workflow 設定 (`<repo-name>.yml`) |
| `templates/` | 新專案模板 (workflows + `.golangci.yml` + `.commitlintrc.yml`) |
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

### codeql.yml — CodeQL 分析 (集中管理)

各 repo 的 CodeQL workflow 為**獨立可執行**的 workflow (直接使用 `github/codeql-action`)，集中管理於 `codeqls/<repo-name>.yml`，透過 `sync-codeql.yml` 同步到各 repo 的 `.github/workflows/codeql.yml`。

每個 repo 的 codeql.yml 可依需要自訂：語言 matrix、Go build 指令、額外工具安裝等。詳見 `codeqls/` 目錄下各檔案。

> **注意:** `.github/workflows/codeql.yml` (reusable workflow) 仍保留但已不被 consumer repos 使用。

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

Sync workflows 由 meta repo 的 `cron.yml` 統一排程觸發 (每週一 00:00 UTC)，使用 matrix 對所有 consumer repos 執行同步 (sync-codeql)。Consumer repos 不需要在自己的 cron.yml 中呼叫這些 workflows。

目標 repo 清單定義在 `cron.yml` 頂部的 `env.REPOS`，新增或移除 repo 只需修改該處。

### sync-codeql.yml — CodeQL 設定同步

將本 repo 的 `codeqls/<repo_name>.yml` 複製到 consumer repo 的 `.github/workflows/codeql.yml`。

```yaml
uses: nics-dp/meta/.github/workflows/sync-codeql.yml@main
permissions:
  contents: write
  pull-requests: write
with:
  repo_name: platform  # 必要
secrets:
  gh_token: ${{ secrets.GH_PAT_READ_NICSDP }}
```

| 參數 | 類型 | 必要 | 說明 |
|------|------|------|------|
| `repo_name` | string | **是** | 目標 repo 名稱 (不含 org prefix) |

---

## Utility Workflows

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
| `managed_files` | string | `.github/workflows/codeql.yml` | 逗號分隔的受保護檔案路徑 |

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

## 共用設定檔

### codeqls/

各 repo 的 CodeQL workflow 設定，以 `<repo-name>.yml` 命名。透過 `sync-codeql.yml` 同步到各 repo 的 `.github/workflows/codeql.yml`。

## Consumer Repo 典型設定

新增 repo 時，從 `templates/` 複製所需的 workflow 檔案到 `.github/workflows/`：

| 模板 | 說明 | 必須修改 |
|------|------|----------|
| `.golangci.yml` | 共用 golangci-lint v2 設定 | 直接複製到 repo 根目錄 |
| `ci.yml` | 持續整合 (lint, security, vulncheck, test) | 公開 repo 移除 secrets |
| `release.yml` | 正式發布 (Go binary + Docker image) | `project_name`, `binary`, `image_name` |
| `snapshot.yml` | 預覽建置 | 與 release.yml 保持一致 |
| `codeql.yml` | CodeQL 靜態安全分析 | 公開 repo 移除 secrets |
| `cd.yml` | 自動部署 (Dokploy) | 僅 service repos |
| `notify.yml` | Google Chat 通知 | — |
| `release-please.yml` | 自動版本管理 | — |
| `.commitlintrc.yml` | Commitlint 設定 | 直接複製到 repo 根目錄 |

新增 repo 後，還需：
1. 更新 meta `cron.yml` 的 `env.REPOS` 清單，以納入 sync-codeql
2. 新增 `codeqls/<repo-name>.yml`，設定該 repo 的 CodeQL workflow
3. 新增 `renovate.json`，引用 `github>nics-dp/meta:renovate-preset`

---

## Consumer Repo 前提條件

Consumer repo 需要具備以下條件才能正確使用 meta reusable workflows：

1. **mise.toml** — 定義 `prepare`, `lint`, `security`, `test`, `vulncheck`, `report` tasks
2. **coverage.out** — `mise run test` 需產出此檔案 (go-test.yml 預期此路徑)
3. **Go module** — go.mod 存在且版本正確
4. **Private module access** — `GH_PAT_READ_NICSDP` secret 已設定 (存取 nics-dp 私有 repos)

## 相關文件

- [GitHub: Reusing Workflows](https://docs.github.com/en/actions/learn-github-actions/reusing-workflows)
