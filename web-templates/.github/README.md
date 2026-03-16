# GitHub Workflows for Web Projects

This directory contains workflow and config templates for React + Vite + TypeScript + Bun web projects.
All workflows call reusable workflows from `nics-dp/meta`, and CI tasks run through `mise`.

## Workflows

| File | Purpose | Triggers |
|---|---|---|
| `ci.yml` | Lint, typecheck, build, audit, test, format check, Semgrep, trivy-license, knip, lighthouse, bundle-size | push, PR, manual |
| `codeql.yml` | CodeQL security analysis (JS/TS + Actions) | push, PR, weekly, manual |
| `notify.yml` | Google Chat notifications | PR, push, release, issue, CI events |
| `release-please.yml` | Automated release management | push to main/release |

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

4. Handle the jobs that are enabled in `ci.yml` by default:
   - Keep the default jobs: copy the optional configs below so `knip`, `lighthouse`, and `bundle-size` can run.
   - Slim down the template: remove or comment out those jobs in `.github/workflows/ci.yml` before the first CI run.
   ```
   cp configs/knip.json <new-repo>/
   cp configs/lighthouserc.json <new-repo>/
   ```

5. Add required scripts to `package.json`:
   ```json
   {
     "scripts": {
       "dev": "vite",
       "build": "tsc -b && vite build",
       "lint": "eslint .",
       "lint:fix": "eslint . --fix",
       "typecheck": "tsc --noEmit",
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

6. Install devDependencies:
   ```bash
   # 必備
   bun add -d prettier prettier-plugin-tailwindcss eslint-plugin-security

   # 必備 (預設 ci.yml 會跑 test)
   bun add -d vitest @testing-library/react @testing-library/jest-dom jsdom @vitest/coverage-v8

   # 若保留 ci.yml 內預設啟用的 optional jobs，這些也需要安裝
   bun add -d knip @lhci/cli @size-limit/preset-app size-limit
   ```

7. Create test setup file at `src/test/setup.ts`:
   ```ts
   import '@testing-library/jest-dom/vitest'
   ```
   This file is required by the default `vitest.config.ts`.

## CI Jobs

### Required (enabled by default)

| Job | Tool | What it checks |
|---|---|---|
| `check-managed` | `check-managed-files.yml` | Blocks PRs modifying synced files |
| `commitlint` | `commitlint.yml` | Conventional commit messages |
| `lint` | `bun-lint.yml` | Runs `mise run lint` |
| `typecheck` | `bun-typecheck.yml` | Runs `mise run typecheck` |
| `build` | `bun-build.yml` | Runs `mise run build` |
| `audit` | `bun-audit.yml` | Runs `mise run audit` |

### Recommended (enabled by default)

| Job | Tool | What it checks |
|---|---|---|
| `test` | `bun-test.yml` | Runs `mise run test` |
| `format-check` | `bun-format-check.yml` | Runs `mise run format-check` |
| `trivy-license` | `trivy-license.yml` | License compliance (no `gh_pat` needed — web repos don't access private Go modules) |
| `semgrep` | `bun-semgrep.yml` | Semgrep static analysis (JS/TS) |

### Optional tools

These jobs are currently enabled in the shipped `ci.yml`. If you don't want them, comment them out or remove them before the first CI run.

| Job | Tool | What it checks |
|---|---|---|
| `knip` | `bun-knip.yml` | Runs `mise run knip` |
| `lighthouse` | `bun-lighthouse.yml` | Runs `mise run lighthouse` |
| `bundle-size` | `bun-bundle-size.yml` | Runs `mise run bundle-size` |

## CodeQL

The `codeql.yml` template analyzes `javascript-typescript` and `actions`.
Unlike Go repos, web projects use `build-mode: none` (no manual build needed)
and don't require `GH_PAT` (no private module access).

For repos managed by `sync-codeql`, copy this template to `meta/configs/codeqls/<repo-name>.yml`.

## Required Secrets

| Secret | Used by | Required |
|---|---|---|
| `GH_PAT_READ_NICSDP` | release-please | Yes |
| `GOOGLE_CHAT_WEBHOOK` | notify | Optional |
