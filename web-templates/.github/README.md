# GitHub Workflows for Web Projects

This directory contains workflow and config templates for React + Vite + TypeScript + Bun web projects.
All workflows call reusable workflows from `nics-dp/meta`.

## Workflows

| File | Purpose | Triggers |
|---|---|---|
| `ci.yml` | Lint, typecheck, build, audit, test, format check | push, PR, manual |
| `codeql.yml` | CodeQL security analysis (JS/TS + Actions) | push, PR, weekly, manual |
| `notify.yml` | Google Chat notifications | PR, push, release, issue, CI events |
| `release-please.yml` | Automated release management | push to main/release |

## Setup

1. Copy workflow files:
   ```
   cp -r web-templates/.github <new-repo>/.github
   ```

2. Copy all configs from `configs/`:
   ```
   cp configs/.prettierrc.json <new-repo>/
   cp configs/.prettierignore <new-repo>/
   cp configs/eslint.config.js <new-repo>/
   cp configs/vitest.config.ts <new-repo>/
   cp configs/.commitlintrc.yml <new-repo>/
   cp configs/renovate.json <new-repo>/
   ```

3. Optional configs (copy if enabling the corresponding CI job):
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

   # 推薦 (test)
   bun add -d vitest @testing-library/react @testing-library/jest-dom jsdom @vitest/coverage-v8

   # 可選
   bun add -d knip @lhci/cli @size-limit/preset-app size-limit
   ```

7. Create test setup file at `src/test/setup.ts`:
   ```ts
   import '@testing-library/jest-dom/vitest'
   ```

## CI Jobs

### Required (enabled by default)

| Job | Tool | What it checks |
|---|---|---|
| `check-managed` | meta workflow | Blocks PRs modifying synced files |
| `commitlint` | meta workflow | Conventional commit messages |
| `lint` | ESLint + security plugin | Code quality + security patterns |
| `typecheck` | `tsc --noEmit` | TypeScript type errors |
| `build` | `vite build` | Build succeeds |
| `audit` | `bun audit` | Known dependency vulnerabilities |

### Recommended (enabled by default)

| Job | Tool | What it checks |
|---|---|---|
| `test` | Vitest | Unit tests + coverage |
| `format-check` | Prettier | Code formatting consistency |
| `trivy-license` | Trivy | License compliance |

### Optional (commented out, uncomment to enable)

| Job | Tool | What it checks |
|---|---|---|
| `knip` | Knip | Unused exports, deps, files |
| `lighthouse` | Lighthouse CI | Performance, a11y, SEO scores |
| `bundle-size` | size-limit | JS bundle size regression |

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
