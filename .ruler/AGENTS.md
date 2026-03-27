# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Repository Purpose

This is a **meta-configuration repository** for the nics-dp organization. It contains shared, reusable configuration files that are consumed by other nics-dp repositories:

- **Reusable GitHub Actions workflows** (`.github/workflows/`) - called via `workflow_call`
- **Shared config files** (`configs/`) - synced to consumer repos via sync workflows
- **Per-repo CodeQL configs** (`configs/codeqls/`) - synced to repos via the sync-codeql workflow
- **Project templates** (`golang-templates/`, `web-templates/`) - reference workflow files for new repos
- **Renovate preset** (`renovate-preset.json`) - org-level Renovate configuration

There is no buildable code in this repo. It is purely configuration and CI/CD infrastructure.

## How Configs Are Consumed

**GitHub Actions workflows**: Other repos call workflows via `uses`:
```yaml
jobs:
  ci:
    uses: nics-dp/meta/.github/workflows/go-lint.yml@main
```

**Centralized config sync**: Sync workflows copy config files from `configs/` to consumer repos via PRs. Triggered weekly by `cron.yml` via matrix strategy, with repo-type-specific lists (`ALL_REPOS`, `GO_REPOS`, `WEB_REPOS`, `CODEQL_REPOS`).

**CodeQL config sync**: The `sync-codeql.yml` workflow copies `configs/codeqls/<github-repo-name>.yml` directly as the repo's `.github/workflows/codeql.yml`. File names must match the GitHub repo name (e.g. `dcf-platform.yml` for `nics-dp/dcf-platform`).

**Renovate**: Consumer repos reference the org preset via `renovate.json`:
```json
{
  "extends": ["github>nics-dp/meta:renovate-preset"],
  "ignoreDeps": ["actions/checkout", "github/codeql-action"]
}
```
`ignoreDeps` is set in downstream repos (not in the preset), because `actions/checkout` and `github/codeql-action` are centrally managed by sync-codeql. The 11 repos with synced codeql.yml need this setting; patroni does not (no codeql.yml).

**PAT split**:
- `GH_PAT_READ_NICSDP` is used for private module access, CodeQL private-repo access, and snapshot builds
- `GH_PAT_RELEASE_NICSDP` is used by `release-please.yml` and release workflows so downstream release activity can be triggered
- `GH_PAT_SYNC_NICSDP` is used by sync workflows (`cron.yml` + `sync-*.yml`) to create cross-repo PRs

Key files:
- `configs/codeqls/<repo-name>.yml` - Per-repo CodeQL workflow configs (synced to `.github/workflows/codeql.yml`)
- `configs/.golangci.yml` - Shared golangci-lint v2 config (gofumpt + goimports formatting, extensive linter set)
- `configs/.commitlintrc.yml` - Shared commitlint config (conventional commits)
- `configs/renovate.json` - Consumer repo Renovate config (manually copied to new repos)
- `configs/.prettierrc.json` + `configs/.prettierignore` - Shared Prettier config (web repos)
- `configs/eslint.config.js` - Shared ESLint flat config (web repos)
- `configs/vitest.config.ts` - Shared Vitest config (web repos)
- `configs/knip.json` - Shared Knip config (web repos)
- `configs/lighthouserc.json` - Shared Lighthouse CI config (web repos)
- `renovate-preset.json` - Org-level Renovate preset (replaces Dependabot)
- `mise.toml` - Tool version management (actionlint, act)

## Workflow Architecture

The reusable workflows in `.github/workflows/` accept inputs and secrets via `workflow_call`:

### CI Pipeline (Go)
- **`go-lint.yml`** - CI lint stage using mise + reviewdog (PR inline annotations via reviewdog/action-golangci-lint, falls back to `mise run ci:go-lint` on non-PR)
- **`go-sec.yml`** - CI security scan using mise + sticky PR comment with results
- **`go-vulncheck.yml`** - Go vulnerability check using mise + sticky PR comment (runs on all triggers, not just push)
- **`go-test.yml`** - CI test + optional coverage report (two jobs: `test` and `report`, controlled by `run_report` input)
- **`go-semgrep.yml`** - Semgrep static analysis for Go (`p/golang` ruleset, pinned container image)

### CI Pipeline (Web / Bun)
- **`bun-lint.yml`** - Web lint via ESLint (configurable command)
- **`bun-typecheck.yml`** - TypeScript typecheck via tsc --noEmit (configurable command)
- **`bun-build.yml`** - Web build via Vite (configurable command)
- **`bun-audit.yml`** - Dependency audit via bun audit
- **`bun-test.yml`** - Web unit tests via Vitest (configurable command)
- **`bun-format-check.yml`** - Format check via Prettier (configurable command)
- **`bun-knip.yml`** - Dead code detection via Knip (configurable command)
- **`bun-lighthouse.yml`** - Lighthouse CI (configurable build command)
- **`bun-bundle-size.yml`** - Bundle size check via size-limit (configurable build command)
- **`bun-semgrep.yml`** - Semgrep static analysis for JS/TS (`p/javascript p/typescript` rulesets, pinned container image)

### CI Pipeline (Shared)
- **`hadolint.yml`** - Dockerfile linting via reviewdog/action-hadolint (auto-detects `Dockerfile*`, excludes `*.env`, PR-only, inline annotations). Trusted registries: docker.io, ghcr.io, dhi.io, gcr.io, quay.io
- **`trivy-iac.yml`** - IaC security scanning (Dockerfile + compose files) via Trivy config scan -> SARIF + sticky PR comment
- **`trivy-license.yml`** - License compliance checking via Trivy fs scan -> step summary + sticky PR comment
- **`commitlint.yml`** - Commit message validation via wagoid/commitlint-github-action (PR-only, conventional commits)
- **`actionlint.yml`** - Workflow YAML linting via reviewdog/action-actionlint (PR inline annotations, step summary on non-PR)
- **`codeql.yml`** - CodeQL Advanced analysis with configurable language matrix and Go build
- **`check-managed-files.yml`** - Blocks PRs that modify centrally-managed files (skips `feature/sync-ci-*` branches)

### Release & Build
- **`release-please.yml`** - Automated release management via googleapis/release-please-action (conventional commits -> Release PR with changelog -> GitHub Release + tag). Supports both `workflow_call` (reusable) and `push` (meta repo self-use); on push, `release_type` defaults to `simple` via event-name gating. Requires PAT (`gh_pat` or `GH_PAT_RELEASE_NICSDP` fallback) to trigger downstream workflows
- **`go-release.yml`** - Go binary release pipeline (multi-arch cross-compile, cosign checksums, macOS notarize via quill, GitHub Release)
- **`image-release.yml`** - Container image build with dual registry (DockerHub + GHCR), attestations, cosign image signing (keyless). Outputs `digest` for sbom-image
- **`sbom-source.yml`** - Source code SBOM (CycloneDX 1.6 via anchore/sbom-action + parlay enrich) + Trivy + Grype vulnerability scan -> GitHub Release + Security tab
- **`sbom-image.yml`** - Container image SBOM (CycloneDX 1.6 via anchore/sbom-action + parlay enrich) + Trivy + Grype vulnerability scan -> GitHub Release + Security tab

### Sync Workflows
- **`sync-codeql.yml`** - Syncs `configs/codeqls/<repo>.yml` -> `.github/workflows/codeql.yml`
- **`sync-commitlintrc.yml`** - Syncs `configs/.commitlintrc.yml` -> `.commitlintrc.yml`
- **`sync-golangci.yml`** - Syncs `configs/.golangci.yml` -> `.golangci.yml`
- **`sync-prettier.yml`** - Syncs `configs/.prettierrc.json` + `configs/.prettierignore`
- **`sync-eslint-config.yml`** - Syncs `configs/eslint.config.js` -> `eslint.config.js`
- **`sync-vitest-config.yml`** - Syncs `configs/vitest.config.ts` -> `vitest.config.ts`
- **`sync-knip.yml`** - Syncs `configs/knip.json` -> `knip.json`
- **`sync-lighthouserc.yml`** - Syncs `configs/lighthouserc.json` -> `lighthouserc.json`

### Utility
- **`notify-gchat.yml`** - PR/push/release event notifications to Google Chat
- **`check-upstream-release.yml`** - Checks upstream repo for new releases, creates bump PR
- **`artifacts-comment.yml`** - Lists build artifacts and upserts a PR comment with nightly.link download URLs

### Scheduling
- **`cron.yml`** - Weekly matrix trigger for all sync workflows across repos (ALL_REPOS, GO_REPOS, WEB_REPOS, CODEQL_REPOS)

### Meta CI
- **`ci.yml`** - Meta repo's own CI: commitlint + actionlint for all workflow YAML files

## Editing Guidelines

- Config source files live in `configs/`; changes are synced to consumer repos via sync workflows + `cron.yml`
- Per-repo CodeQL workflow configs live in `configs/codeqls/<github-repo-name>.yml` (must match GitHub repo name, e.g. `dcf-platform.yml`)
- To add a new repo to sync, update the repo lists in `.github/workflows/cron.yml` (`ALL_REPOS`, `GO_REPOS`, `WEB_REPOS`, `CODEQL_REPOS`)
- Project templates in `golang-templates/` and `web-templates/` are reference files for new repo setup
- Renovate preset changes in `renovate-preset.json` automatically apply to all consumer repos; `ignoreDeps` is set in downstream repos, not in the preset
- Consumer repos need `.commitlintrc.yml` and `renovate.json` copied from `configs/`


Centralised AI agent instructions. Add coding guidelines, style guides, and project context here.

Ruler concatenates all .md files in this directory (and subdirectories), starting with AGENTS.md (if present), then remaining files in sorted order.
