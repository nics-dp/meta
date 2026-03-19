# GitHub Workflows for Go Projects

This directory contains workflow and config templates for setting up CI/CD in a new Go repository.
All workflows call reusable workflows from `nics-dp/meta`.

## Workflows

| File | Purpose | Triggers |
|---|---|---|
| `ci.yml` | Managed file check, commitlint, hadolint, trivy-iac, trivy-license, lint, security scan, vulnerability check, Semgrep, test | push, PR, manual |
| `release-please.yml` | Auto-create Release PR with changelog, then GitHub Release | push to main/release |
| `release.yml` | Build Go binaries, Docker image, SBOMs, sign artifacts | push tag v*, manual |
| `snapshot.yml` | Build snapshot artifacts on PR, post artifact links via `artifacts-comment` | CI success on PR, manual |
| `codeql.yml` | CodeQL security analysis (Go + Actions) | push, PR, weekly, manual |
| `notify.yml` | Google Chat notifications for PR/push/release/issue/CI events | various |

## Workflow Details

### ci.yml — CI Checks

Runs comprehensive CI checks including code style, security scanning, and unit tests.

**Triggers:**
- Push to `main`, `dev`, `release/**`, `feature/**`
- PR targeting `main`, `dev`, `release/**`
- Manual (`workflow_dispatch`)

**Jobs:**

```
check-managed ─┐
commitlint ────┤
hadolint ──────┤ (Service repos only)
trivy-iac ─────┤ (Service repos only)
trivy-license ─┤ (all independent)
go-lint ───────┼──► go-test
go-sec ────────┘
go-vulncheck ──┐
go-semgrep ────┘ (independent)
```

| Job | Meta Workflow | Description |
|-----|---------------|-------------|
| check-managed | `check-managed-files.yml` | Check managed files are in sync with meta |
| commitlint | `commitlint.yml` | Validate commit messages (conventional commits) |
| hadolint | `hadolint.yml` | Dockerfile linting (Service/Docker repos only) |
| trivy-iac | `trivy-iac.yml` | IaC security scanning (Service/Docker repos only) |
| trivy-license | `trivy-license.yml` | Dependency license compliance check |
| go-lint | `go-lint.yml` | Go code linting (golangci-lint) |
| go-sec | `go-sec.yml` | Go security scanning (gosec) |
| go-vulncheck | `go-vulncheck.yml` | Go known vulnerability check (govulncheck) |
| go-semgrep | `go-semgrep.yml` | Semgrep static analysis |
| go-test | `go-test.yml` | Go unit tests (depends on go-lint, go-sec) |

---

### release-please.yml — Automated Release Management

Auto-creates Release PRs with changelog based on conventional commits. After merge, creates GitHub Release + tag which triggers release.yml.

**Triggers:**
- Push to `main`, `release/**`

**Flow:**
1. Detect conventional commits, calculate next semver version
2. Create/update Release PR (with auto-generated changelog)
3. After Release PR merge, create GitHub Release + tag
4. Tag push triggers release.yml

---

### release.yml — Production Release

Builds Go binaries (multi-platform cross-compilation), Docker images, and uploads to GitHub Release with cosign signatures.

**Triggers:**
- Push tag `v*`
- Manual (`workflow_dispatch`)

**Jobs:**

```
go-release ──► sbom-source
image-build ──► sbom-image    (Service repos only)
```

| Job | Meta Workflow | Description |
|-----|---------------|-------------|
| go-release | `go-release.yml` | Multi-platform Go binary build, optional CGO/Linux-only override, cosign signing |
| sbom-source | `sbom-source.yml` | Source SBOM (CycloneDX 1.6) + vulnerability scan (Trivy + Grype) + Security tab upload |
| image-build | `image-release.yml` | Docker image build + push on `{"group":"releasers"}` (Service repos only) |
| sbom-image | `sbom-image.yml` | Image SBOM + vulnerability scan + Security tab upload (Service repos only) |

**Notes:**
- The shipped template pins release builds to `runs_on: '{"group":"releasers"}'`.
- `go-release` receives `GH_PAT_READ_NICSDP` in the template so release jobs can read private modules during builds.
- `release-please.yml` uses `GH_PAT_RELEASE_NICSDP` because release creation must trigger downstream workflows.

---

### snapshot.yml — Preview Build

Automatically builds preview artifacts after CI passes on PRs.

**Triggers:**
- CI workflow success (PR events only, same-repo branches only)
- Manual (`workflow_dispatch`)

**Jobs:**

```
go-release ──┐
image-build ─┼──► artifacts-comment
             │    (Service repos: both; CLI repos: go-release only)
```

| Job | Meta Workflow | Description |
|-----|---------------|-------------|
| go-release | `go-release.yml` | Snapshot build (snapshot mode, PR-only for `workflow_run`) |
| image-build | `image-release.yml` | Snapshot Docker image with SBOM/provenance/attest disabled (Service repos only) |
| artifacts-comment | `artifacts-comment.yml` | Post artifact links as PR comment; for CLI repos change `needs` to `[go-release]` |

**Notes:**
- `workflow_run` execution only proceeds for successful same-repo pull requests; manual dispatch bypasses that gate.
- The shipped template pins snapshot builds to `runs_on: '{"group":"releasers"}'`.
- In snapshot mode, `go-release` only needs `contents: read`; `artifacts-comment` only needs `actions: read` and `issues: write`.

---

### codeql.yml — CodeQL Analysis

GitHub CodeQL static security analysis. Managed centrally via `configs/codeqls/<repo-name>.yml` and synced by `sync-codeql`.

**Triggers:**
- Push to `main`, `dev` (excluding `*.md`, `*.txt`)
- PR targeting `main`, `dev` (excluding `*.md`, `*.txt`)
- Weekly schedule (Monday 00:00 UTC)
- Manual (`workflow_dispatch`)

**Languages analyzed:**
- `actions` (build-mode: none)
- `go` (build-mode: manual)

**Features:**
- Uses `security-extended` and `security-and-quality` query suites
- Supports private repo access via `external-repository-token`
- Narrows PAT-backed git access to `github.com/nics-dp` instead of rewriting all GitHub HTTPS fetches

---

### notify.yml — Google Chat Notifications

Sends GitHub event notifications to Google Chat.

**Events and notifications:**

| Event | Notification |
|-------|-------------|
| PR opened/closed/reopened | PR title, status, branch info |
| Push to main/dev | Commit message |
| Release published | Release tag and content |
| Issue opened/closed | Issue title |
| ci/release workflow failure | Failed workflow name and link |

## Setup

1. Copy workflow files and `mise.toml`:
   ```
   cp -r golang-templates/.github <new-repo>/.github
   cp golang-templates/mise.toml <new-repo>/
   ```

2. Copy configs from `configs/`:
   ```
   cp configs/.golangci.yml <new-repo>/
   cp configs/.commitlintrc.yml <new-repo>/
   cp configs/renovate.json <new-repo>/
   ```

3. Search for `TODO` in the copied files and replace with project-specific values:
   - `release.yml` / `snapshot.yml`: `project_name`, `binary`, `image_name`

4. Adjust by project type:

   **Service repo** (Go binary + Docker image): use all workflows as-is.

   **CLI repo** (Go binary only):
   - `ci.yml`: remove `hadolint` and `trivy-iac` jobs
   - `release.yml`: remove `image-build` and `sbom-image` jobs
   - `snapshot.yml`: remove `image-build` job, change `artifacts-comment` needs to `[go-release]`

   **Library** (no binary, no Docker):
   - `ci.yml`: remove `hadolint` and `trivy-iac` jobs
   - Remove `release.yml` and `snapshot.yml` entirely

5. Configure repo secrets as needed:
   - `GH_PAT_READ_NICSDP` for private repos importing `nics-dp` modules, snapshot builds, or private-module CodeQL access
   - `GH_PAT_RELEASE_NICSDP` for `release-please.yml`, `release.yml`, and release-time private module access

## Required Secrets

| Secret | Used by | Required |
|---|---|---|
| `GH_PAT_READ_NICSDP` | ci, snapshot, codeql | Private repos / private module access |
| `GH_PAT_RELEASE_NICSDP` | release-please, release | All repos (triggers downstream workflows) |
| `DOCKERHUB_USERNAME` | release, snapshot | Docker image repos |
| `DOCKERHUB_TOKEN` | release, snapshot | Docker image repos |
| `GOOGLE_CHAT_WEBHOOK` | notify | Optional |

## CodeQL

The `codeql.yml` template is a starting point. For repos managed by `sync-codeql`, the per-repo config in `configs/codeqls/<repo-name>.yml` takes precedence. Do not manually edit `.github/workflows/codeql.yml` in synced repos.

## Related Files

| File | Source | Purpose |
|---|---|---|
| `.golangci.yml` | `configs/.golangci.yml` | golangci-lint v2 config (synced via `sync-golangci`) |
| `.commitlintrc.yml` | `configs/.commitlintrc.yml` | Conventional commit message rules (synced via `sync-commitlintrc`) |
| `renovate.json` | `configs/renovate.json` | Renovate preset + ignoreDeps (synced via `sync-renovate`) |
