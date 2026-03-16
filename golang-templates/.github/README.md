# GitHub Workflows for Go Projects

This directory contains workflow and config templates for setting up CI/CD in a new Go repository.
All workflows call reusable workflows from `nics-dp/meta`.

## Workflows

| File | Purpose | Triggers |
|---|---|---|
| `ci.yml` | Lint, security scan, vulnerability check, Semgrep, test, Dockerfile lint | push, PR, manual |
| `release-please.yml` | Auto-create Release PR with changelog, then GitHub Release | push to main/release |
| `release.yml` | Build Go binaries, Docker image, SBOMs, sign artifacts | release created |
| `snapshot.yml` | Build snapshot artifacts on PR, post artifact links via `artifacts-comment` | CI success on PR, manual |
| `codeql.yml` | CodeQL security analysis (Go + Actions) | push, PR, weekly, manual |
| `notify.yml` | Google Chat notifications for PR/push/release/issue/CI events | various |

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
   - `ci.yml`: remove `hadolint` and `trivy-iac` jobs, remove `security-events: write`
   - `release.yml`: remove `image-build` and `sbom-image` jobs
   - `snapshot.yml`: remove `image-build` job, change `artifacts-comment` needs to `[go-release]`

   **Library** (no binary, no Docker):
   - `ci.yml`: remove `hadolint` and `trivy-iac` jobs, remove `security-events: write`
   - Remove `release.yml` and `snapshot.yml` entirely

5. For private repos importing `nics-dp` modules, ensure `GH_PAT_READ_NICSDP` is configured as a repo secret.

## Required Secrets

| Secret | Used by | Required |
|---|---|---|
| `GH_PAT_READ_NICSDP` | ci, release, snapshot, release-please | Private repos |
| `DOCKERHUB_USERNAME` | release, snapshot | Docker image repos |
| `DOCKERHUB_TOKEN` | release, snapshot | Docker image repos |
| `GOOGLE_CHAT_WEBHOOK` | notify | Optional |

## CodeQL

The `codeql.yml` template is a starting point. For repos managed by `sync-codeql`, the per-repo config in `meta/codeqls/<repo-name>.yml` takes precedence. Do not manually edit `.github/workflows/codeql.yml` in synced repos.

## Related Files

| File | Source | Purpose |
|---|---|---|
| `.golangci.yml` | `configs/.golangci.yml` | golangci-lint v2 config (synced via `sync-golangci`) |
| `.commitlintrc.yml` | `configs/.commitlintrc.yml` | Conventional commit message rules (synced via `sync-commitlintrc`) |
| `renovate.json` | `configs/renovate.json` | Renovate preset + ignoreDeps (synced via `sync-renovate`) |
