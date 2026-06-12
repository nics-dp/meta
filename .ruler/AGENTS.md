# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Repository Purpose

This is a **meta-configuration repository** for the nics-dp organization. It contains:

- **Reusable GitHub Actions workflows** (`.github/workflows/`) — called via `workflow_call`. Core is `mise-task.yml`, which centralizes checkout + jdx/mise-action + mise atom invocation + GH step summary. Release / SBOM-image / CodeQL / utility workflows live here too.
- **Shared mise atomic tasks** (`.mise/tasks/`) — consumed by consumer repos via `git::` remote includes. All atoms hidden (`#MISE hide=true`).
- **Facade templates** (`templates/facades/`) — five `mise.<archetype>.toml` files (`go-service`, `go-lib`, `frontend`, `python`, `image`) that consumer repos copy as their `mise.toml`.
- **Shared config files** (`configs/`) — fetched on demand by atoms via `curl` (no sync workflow; META_CONFIG_BASE override available). `.golangci.yml` is **excluded** — each Go consumer repo commits its own to encode `gofumpt.module-path` per module.
- **Renovate preset** (`renovate-preset.json`) — org-level Renovate configuration.

There is no buildable code in this repo. It is purely configuration and CI/CD infrastructure.

## How Configs Are Consumed

**GitHub Actions workflows**: Consumer repos call workflows via `uses`:
```yaml
jobs:
  checks:
    name: ${{ matrix.name }}
    strategy:
      matrix:
        include:
          - { name: "Go Lint", task: "go:lint-check" }
          - { name: "Go Test", task: "go:test --race --coverage" }
    uses: nics-dp/meta/.github/workflows/mise-task.yml@main
    with:
      name: ${{ matrix.name }}
      task: ${{ matrix.task }}
```

**Mise task sharing**: Consumer repos pull shared atomic tasks via `git::` remote include in their `mise.toml`:
```toml
[task_config]
includes = ["git::https://github.com/nics-dp/meta.git//.mise/tasks?ref=main"]
```

**Renovate**: Consumer repos reference the org preset via `renovate.json`:
```json
{
  "extends": ["github>nics-dp/meta:renovate-preset"]
}
```

**Shared configs (`configs/`)**: Atoms fetch raw URLs at runtime (no commit to consumer repos). Trap cleanup removes the downloaded config when atom exits. Note: `.golangci.yml` is **per-repo committed** (not shared via curl) — `go:lint-check` / `go:lint-fix` read consumer's own file because gofumpt requires per-module `module-path` setting.

**PAT split**:
- `GH_PAT_READ_NICSDP` — private module access, CodeQL private-repo access, release/snapshot builds, `mise-task.yml` private-modules flag
- `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` — image-release.yml (Docker image push)

## Key Files

- `.mise/tasks/{ci,iac,go,node,py,sbom,gs,meta,lib,ruler}/` — atomic tasks (all hidden)
- `templates/facades/mise.<archetype>.toml` — facade templates for go-service / go-lib / frontend / python / image
- `configs/eslint.config.js` — ESLint flat config (+ eslint-plugin-security)
- `configs/.prettierrc.json` + `configs/.prettierignore` — Prettier shared
- `configs/vitest.config.ts` — Vitest shared
- `configs/knip.json` — Knip shared
- `configs/lighthouserc.json` — Lighthouse CI shared
- `configs/playwright.config.ts` — Playwright base (env-driven via `PW_*`)
- `renovate-preset.json` — Org-level Renovate preset (replaces Dependabot)
- `mise.toml` — Tool version management + meta repo's own aggregate tasks

## Workflow Architecture

### Core
- **`mise-task.yml`** — Reusable. Inputs: `task`, `name`, `runs_on` (JSON via `fromJSON()`), `fetch-depth`, `private-modules`. Secret: `gh_pat`. Encapsulates checkout (SHA-pinned) + `jdx/mise-action@<sha>` + optional git private-modules config + run mise atom + step summary + enforce.

### Release & Build
- **`go-release.yml`** — Multi-arch Go binary release (cosign, macOS notarize via quill, GitHub Release).
- **`image-release.yml`** — Docker image dual-registry (DockerHub + GHCR) + attestations + cosign keyless. Outputs `digest` for `sbom-image.yml`.
- **`sbom-image.yml`** — Container image CycloneDX 1.6 SBOM (anchore/sbom-action + parlay enrich) + Trivy + Grype vuln scan → GitHub Release + Security tab.

### CodeQL
- **`codeql-reusable.yml`** — CodeQL Advanced analysis (configurable language matrix + Go build).
- **`codeql.yml`** — meta repo's own CodeQL (workflow YAML scan only).

### Utility
- **`artifacts-comment.yml`** — Sticky PR comment listing artifacts (nightly.link URLs).

### Meta CI
- **`ci.yml`** — meta repo's own CI: matrix calling `mise-task.yml` with `iac:actionlint` (workflow YAML lint via mise atom).

## Editing Guidelines

- New mise atom: add file under `.mise/tasks/<category>/<name>`, prepend `#MISE description=…` and `#MISE hide=true`. Make executable.
- New facade vocabulary task: edit `templates/facades/mise.<archetype>.toml`. Don't add to atoms (facades only).
- Shared config change in `configs/`: takes effect immediately for consumers (no sync workflow; raw URL fetched at atom runtime).
- Renovate preset change in `renovate-preset.json`: applies to all consumer repos automatically.
- Workflow YAML change: validate with `mise exec -- actionlint <file>` before commit.
- Atom signature change: breaking change requires coordinated bump in all 15 consumer repos once `?ref=` is tagged (`v1`). Until tag is cut, `?ref=main` is mutable and `meta:bump` clears mise cache.


Centralised AI agent instructions. Add coding guidelines, style guides, and project context here.

Ruler concatenates all .md files in this directory (and subdirectories), starting with AGENTS.md (if present), then remaining files in sorted order.
