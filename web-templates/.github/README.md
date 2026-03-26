# GitHub Workflows for Web Projects

This directory contains workflow and config templates for Vue + Vite + TypeScript + Bun web projects.
All workflows call reusable workflows from `nics-dp/meta`, and CI tasks run through `mise`.

## Workflows

| File | Purpose | Triggers |
|---|---|---|
| `ci.yml` | Lint, typecheck, build, audit, test, format check, Semgrep, trivy-license, hadolint, trivy-iac, knip, lighthouse | push, PR, manual |
| `release-please.yml` | Automated release management | push to main/release |
| `codeql.yml` | CodeQL security analysis (JS/TS + Actions) | push, PR, weekly, manual |
| `notify.yml` | Google Chat notifications | PR, push, release, issue, CI events |

## Workflow Details

### ci.yml — Web CI Checks

Runs comprehensive CI checks for web projects including linting, type checking, build, security scanning, and tests.

**Triggers:**
- Push to `main`, `dev`, `release/**`, `feature/**`
- PR targeting `main`, `dev`, `release/**`
- Manual (`workflow_dispatch`)

**Jobs:**

```
check-managed ─┐
commitlint ────┤
audit ─────────┤
format-check ──┤
trivy-license ─┤
hadolint ──────┤ (all independent)
trivy-iac ─────┤
semgrep ───────┤
knip ──────────┤
lint ──────────┼──► build ──► lighthouse
typecheck ─────┘      │
                      └──► test
```

#### Required (enabled by default)

| Job | Meta Workflow | Description |
|-----|---------------|-------------|
| check-managed | `check-managed-files.yml` | Check managed files are in sync with meta |
| commitlint | `commitlint.yml` | Validate commit messages (conventional commits) |
| lint | `bun-lint.yml` | Runs `mise run ci:lint` |
| typecheck | `bun-typecheck.yml` | Runs `mise run ci:typecheck` |
| build | `bun-build.yml` | Runs `mise run build` (depends on lint, typecheck) |
| audit | `bun-audit.yml` | Runs `mise run ci:audit` |

#### Recommended (enabled by default)

| Job | Meta Workflow | Description |
|-----|---------------|-------------|
| test | `bun-test.yml` | Runs `mise run ci:test` (depends on lint, typecheck) |
| format-check | `bun-format-check.yml` | Runs `mise run ci:format-check` |
| trivy-license | `trivy-license.yml` | License compliance (no `gh_pat` needed) |
| semgrep | `bun-semgrep.yml` | Semgrep static analysis (JS/TS) |

#### Optional

These jobs are enabled in the shipped `ci.yml` unless otherwise noted. Remove or comment out any that don't apply to your project before the first CI run.

| Job | Meta Workflow | Description |
|-----|---------------|-------------|
| hadolint | `hadolint.yml` | Dockerfile linting (Docker/service repos only) |
| trivy-iac | `trivy-iac.yml` | IaC security scanning for Dockerfiles + compose (Docker/service repos only) |
| knip | `bun-knip.yml` | Runs `mise run ci:knip` |
| lighthouse | `bun-lighthouse.yml` | Runs `mise run lighthouse` (depends on build) |
| bundle-size | `bun-bundle-size.yml` | Commented out by default; enable only after adding repo-specific `size-limit` config |

---

### release-please.yml — Automated Release Management

Auto-creates Release PRs with changelog based on conventional commits. After merge, creates GitHub Release + tag.

**Triggers:**
- Push to `main`, `release/**`

**Flow:**
1. Detect conventional commits, calculate next semver version
2. Create/update Release PR (with auto-generated changelog)
3. After Release PR merge, create GitHub Release + tag

**Note:** `release-please.yml` requires `GH_PAT_RELEASE_NICSDP`; `GITHUB_TOKEN` alone will not trigger downstream workflows.

---

### codeql.yml — CodeQL Analysis

GitHub CodeQL static security analysis for web projects. Managed centrally via `configs/codeqls/<repo-name>.yml` and synced by `sync-codeql`.

**Triggers:**
- Push to `main`, `dev` (excluding `*.md`, `*.txt`)
- PR targeting `main`, `dev` (excluding `*.md`, `*.txt`)
- Weekly schedule (Monday 00:00 UTC)
- Manual (`workflow_dispatch`)

**Languages analyzed:**
- `actions` (build-mode: none)
- `javascript-typescript` (build-mode: none)

**Features:**
- Uses `security-extended` and `security-and-quality` query suites
- No `GH_PAT` needed (no private module access)

For repos managed by `sync-codeql`, copy this template to `configs/codeqls/<repo-name>.yml`.

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
| ci workflow failure | Failed workflow name and link |

## Setup

1. Copy workflow files:
   ```
   cp -r web-templates/.github <new-repo>/.github
   ```

2. Copy `mise.toml`:
   ```
   cp web-templates/mise.toml <new-repo>/
   ```

3. Copy all configs from `configs/`:
   ```
   cp configs/.prettierrc.json <new-repo>/
   cp configs/.prettierignore <new-repo>/
   cp configs/eslint.config.js <new-repo>/
   cp configs/vitest.config.ts <new-repo>/
   cp configs/.commitlintrc.yml <new-repo>/
   cp configs/renovate.json <new-repo>/
   ```

4. If the project does **not** have a Dockerfile, remove `hadolint` and `trivy-iac` from `ci.yml`.

5. Handle the jobs that are enabled in `ci.yml` by default:
   - Keep the default optional jobs: copy the optional configs below so `knip` and `lighthouse` can run.
   - Enable `bundle-size` only after adding your own `size-limit` configuration.
   - Slim down the template: remove or comment out `knip` / `lighthouse` if the repo does not need them before the first CI run.
   ```
   cp configs/knip.json <new-repo>/
   cp configs/lighthouserc.json <new-repo>/
   ```

6. Add required scripts to `package.json`:
   ```json
   {
     "scripts": {
       "dev": "vite",
       "build": "vue-tsc -b && vite build",
       "lint": "eslint .",
       "lint:fix": "eslint . --fix",
       "typecheck": "vue-tsc --noEmit",
       "format:check": "prettier --check .",
       "format": "prettier --write .",
       "test": "vitest run",
       "test:watch": "vitest",
       "test:coverage": "vitest run --coverage",
       "knip": "knip",
       "preview": "vite preview"
     }
   }
   ```

7. Install devDependencies:
   ```bash
   # Required
   bun add -d prettier prettier-plugin-tailwindcss

   # Required (ci.yml runs test by default)
   bun add -d vitest jsdom @vitest/coverage-v8

   # If keeping optional jobs enabled in ci.yml
   bun add -d knip @lhci/cli
   ```

## Required Secrets

| Secret | Used by | Required |
|---|---|---|
| `GH_PAT_RELEASE_NICSDP` | release-please | Yes (creates release/tag and triggers downstream workflows) |
| `GOOGLE_CHAT_WEBHOOK` | notify | Optional |

## Related Files

| File | Source | Purpose |
|---|---|---|
| `.prettierrc.json` | `configs/.prettierrc.json` | Prettier config |
| `.prettierignore` | `configs/.prettierignore` | Prettier ignore patterns |
| `eslint.config.js` | `configs/eslint.config.js` | ESLint flat config |
| `vitest.config.ts` | `configs/vitest.config.ts` | Vitest config |
| `.commitlintrc.yml` | `configs/.commitlintrc.yml` | Conventional commit message rules (synced via `sync-commitlintrc`) |
| `renovate.json` | `configs/renovate.json` | Renovate preset + ignoreDeps (synced via `sync-renovate`) |
| `knip.json` | `configs/knip.json` | Knip config (optional) |
| `lighthouserc.json` | `configs/lighthouserc.json` | Lighthouse CI config (optional) |
