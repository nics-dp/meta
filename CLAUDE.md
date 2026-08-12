# meta

This file provides guidance to Claude Code when working with code in this repository.

## Repository Purpose

This is a **meta-configuration repository** for the nics-dp organization. It contains:

- **Reusable GitHub Actions workflows** (`.github/workflows/`) — called via `workflow_call`. Core is `mise-task.yml`, which centralizes checkout + jdx/mise-action + mise atom invocation + GH step summary. Release / SBOM-image / CodeQL / utility workflows live here too.
- **Shared mise atomic tasks** (`.mise/tasks/`) — consumed by consumer repos via `git::` remote includes. All atoms hidden (`#MISE hide=true`).
- **Facade templates** (`templates/facades/`) — five `mise.<archetype>.toml` files (`go-service`, `go-lib`, `frontend`, `python`, `image`) that consumer repos copy as their `mise.toml`.
- **Shared config files** (`configs/`) — fetched on demand by atoms via `curl` (no sync workflow; META_CONFIG_BASE override available). `.golangci.yml` is **excluded** (per-repo committed — see below).
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

**Auth (GitHub Apps + DockerHub)**:
- **nics-dp-ci-read** App token (private module access, CodeQL private-repo access, release/snapshot builds, `mise-task.yml` private-modules flag): client-id from org **variable** `CI_READ_APP_CLIENT_ID` (auto-available in reusable workflows via `vars`); private key from org **secret** `CI_READ_APP_PRIVATE_KEY`, passed by callers as `ci_read_app_private_key`. The legacy `ci_read_app_id` input has been removed (no longer declared; do not pass it). No PAT.
- **nics-dp-scorecard** App token — `scorecard.yml` ONLY (separate from ci-read). Client-id from org **variable** `SCORECARD_APP_CLIENT_ID`, private key from org **secret** `scorecard_app_private_key`. Minted into a short-lived `repo_token` so Scorecard's API queries (incl. Branch-Protection, which needs `Administration: Read`) score correctly on PRIVATE repos. Without it Scorecard falls back to `GITHUB_TOKEN` (queries fail on a private repo) but the run stays non-blocking.
- `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` — image-release.yml (Docker image push)

## Key Files

- `.mise/tasks/{ci,iac,go,node,py,sbom,gs,meta,mise,lib,dc}/` — atomic tasks (all hidden). `mise:validate`, `iac:shellcheck`, and `iac:zizmor` validate task/workflow definitions; `lib/ci-isolate` is their sourced isolation helper, not a task. `dc/` = Docker Compose lifecycle (`up`/`down`/`pull`/`rec`/`clean`).
- `templates/facades/mise.<archetype>.toml` — facade templates for go-service / go-lib / frontend / python / image
- `configs/eslint.config.js` — ESLint flat config (+ eslint-plugin-security)
- `configs/.prettierrc.json` + `configs/.prettierignore` — Prettier shared
- `configs/.oxfmtrc.json` — Oxfmt (Oxc formatter) config, fetched by `node:oxfmt-check` / `node:oxfmt-fix` atoms
- `vitest.config.ts` / `knip.json` — **repo-local** (each web consumer commits its own at repo root; `node:test` / `node:knip` / `node:bench-compare` no longer fetch from meta and error out if the config is missing)
- `configs/lighthouserc.json` — Lighthouse CI shared
- `configs/playwright.config.ts` — Playwright base (env-driven via `PW_*`)
- `renovate-preset.json` — Org-level Renovate preset (replaces Dependabot)
- `mise.toml` — Tool version management + meta repo's own aggregate tasks

## Workflow Architecture

### Core
- **`mise-task.yml`** — Reusable. Inputs: `task`, `name`, `runs_on` (JSON via `fromJSON()`), `fetch-depth`, `private-modules`. Secret: `ci_read_app_private_key` (client-id via `CI_READ_APP_CLIENT_ID` org var; legacy `ci_read_app_id` input removed). Encapsulates checkout (SHA-pinned) + `jdx/mise-action@<sha>` + optional git private-modules config + run mise atom + step summary + enforce.
  - **Implementation gotchas (don't "simplify" away):** (1) `MISE_MINIMUM_RELEASE_AGE: "0"` disables mise's supply-chain release-age control — left enabled it injects a pip-only `--uploaded-prior-to=` flag that the uv-backed pipx installer rejects (breaks semgrep et al.). "0" needs mise ≥ 2026.6.3, and the self-hosted pool reuses mixed cached mise binaries, so `jdx/mise-action` **pins an exact version** rather than `latest` — currently `2026.7.0`, kept in lockstep with `auto-release.yml`'s `mise_version` default and `self-release.yml`'s explicit pass; ≥ 2026.7.0 is required because older builds embed a Sigstore trust root predating GitHub's 2026-06-12 TSA cert rotation and fail artifact-attestation verification on tool installs (jdx/mise#10680). (2) `MISE_USE_VERSIONS_HOST` is **kept ENABLED** (mise default). The `mise-versions.jdx.dev` CDN occasionally 403s, but mise falls back to source-direct — cosmetic noise, not failure. Setting it `false` to silence the noise removed the cache/fallback layer, so a transient GitHub 504 hard-failed `latest` tool installs (e.g. trivy). Keep the host on.

### Release & Build
- **`go-release.yml`** — Multi-arch Go binary release (cosign, macOS notarize via quill, GitHub Release).
- **`image-release.yml`** — Docker image dual-registry (DockerHub + GHCR) + attestations + cosign keyless. Outputs `digest` for `sbom-image.yml`.
- **`sbom-image.yml`** — Container image CycloneDX 1.6 SBOM (anchore/sbom-action + parlay enrich) + Trivy + Grype vuln scan → GitHub Release + Security tab. The Trivy SARIF (`category: trivy-image`) is post-filtered to drop `GO-2026-5932` (`golang.org/x/crypto/openpgp` unmaintained) before upload — mirrors the govulncheck filter in `security-sarif.yml`, but since Trivy SARIF has no reachability level it drops by rule id unconditionally (jq, fail-safe: keeps the original SARIF on error). The unfixed advisory still ships in the Trivy JSON asset on release runs (snapshot runs upload no assets). Grype needs no such filter (`only-fixed: true` already excludes this no-fix advisory).
- **`sbom-source.yml`** — Source-tree (filesystem) SBOM. Input `project_name` for artifact naming. Applies the same `GO-2026-5932` Trivy SARIF post-filter (`category: trivy-source`) as `sbom-image.yml`.

### CodeQL
- **`codeql-reusable.yml`** — CodeQL Advanced analysis (configurable language matrix + Go build).
- **`codeql.yml`** — meta repo's own CodeQL (workflow YAML scan only).

### Security
- **`security-sarif.yml`** — Reusable. Runs the gate-only scanners (gosec, govulncheck, semgrep, trivy config, hadolint) and uploads each as a distinct GitHub code-scanning SARIF category. Scanner findings are informational/non-blocking by default. `run_gosec` and `run_govulncheck` independently select the Go scanners (both default `true`) under the `run_go` master switch (also default `true`). `gosec_blocking` defaults to `false`; fail-closed enforcement is active only when `run_go && run_gosec && gosec_blocking`. It covers vendor preparation, gosec findings or operational failure, the local SARIF structural precheck, private Go state cleanup, upload action or terminal processing failure, and SARIF artifact cleanup. In that mode `wait-for-processing: true` treats terminal `failed` as an upload failure, while a polling API error or timeout only warns and leaves processing unknown. Govulncheck, semgrep, trivy config, and hadolint remain informational. Invalid caller configuration and safety checks such as `scan_path` validation can still fail independently; do not describe the entire workflow as never failing. Secret `ci_read_app_private_key` mints a ci-read App token (via `vars.CI_READ_APP_CLIENT_ID`) for private Go module access during gosec/govulncheck (mirrors `mise-task.yml`; the PAT model was retired org-wide). The govulncheck step post-filters its SARIF to drop `GO-2026-5932` (`golang.org/x/crypto/openpgp` unmaintained) before upload — govulncheck has no native ignore flag, and the advisory is non-actionable (transitively-present, never-called subpackage, no fixed version). Scoped to that ID **at `note` level only** (govulncheck levels: note = module-only dependency, warning = package imported, error = symbol called), so a genuinely reachable openpgp use still surfaces; fail-safe (keeps the original SARIF on error). Local `go:sast` remains blocking with gosec pinned to `v2.28.0`; the meta repo's Renovate custom manager synchronizes that pin with the workflow pin.
- **`dependency-review.yml`** — Reusable. PR-time `actions/dependency-review-action` over the GitHub dependency graph (Go go.mod natively supported). BLOCKS PRs introducing dependencies with known vulnerabilities (>= `fail_on_severity`, default `high`) or disallowed licenses, and posts a summary comment (`comment_summary_in_pr`, default `on-failure`). Optional `allow_licenses` / `deny_licenses` SPDX lists. `runs-on: ubuntu-latest` (no runner input). Callers MUST invoke it from a `pull_request`-triggered workflow.
### Security & Supply Chain
- **`scorecard.yml`** — Reusable, the only Scorecard variant. Runs OpenSSF Scorecard (`ossf/scorecard-action@<sha>`), filters posture noise (job-level `TokenPermissionsID`, `nics-dp/` `PinnedDependenciesID`, and `VulnerabilitiesID` findings whose sole vuln is `GO-2026-5932` — mirrors the govulncheck filter in `security-sarif.yml`), and uploads `results.filtered.sarif` to code scanning (`category: scorecard`, non-blocking). Hardcodes `publish_results: false`; the `publish` input is retained for caller compatibility but ignored (this workflow never publishes to the public OpenSSF API). Uses the **nics-dp-scorecard** App (separate from ci-read; secret `scorecard_app_private_key` + org var `SCORECARD_APP_CLIENT_ID`) to score private repos — see Auth above. Job perms: `contents: read`, `security-events: write`, `actions: read`.
- **`go-dependency-submission.yml`** — Reusable. (Go and Node submission are SEPARATE workflows because `go.mod` is natively parsed by GitHub's dependency graph while `bun.lock` is not — see `node-dependency-submission.yml`.) Submits the resolved Go dependency graph (`actions/go-dependency-submission@<sha>`) to the Dependency Submission API. Inputs: `go_mod_path` (default `go.mod`), `go_build_target` (empty omits the input so the action's own `all` default applies — split across two `if:`-gated steps). Secret `ci_read_app_private_key` mints a ci-read App token (via `vars.CI_READ_APP_CLIENT_ID`) for an org-scoped (`github.com/nics-dp/` only) private-module git rewrite in a short-lived `$RUNNER_TEMP` gitconfig via `GIT_CONFIG_GLOBAL` + `GOPRIVATE`. Perms: `contents: write`.
- **`node-dependency-submission.yml`** — Reusable. Submits a bun project's FULL transitive npm graph to the Dependency Submission API. GitHub's native dependency graph does NOT parse `bun.lock` (it sees only `package.json` direct deps), so this runs `bun install --frozen-lockfile` then has Syft (`anchore/sbom-action@<sha>`, `dependency-snapshot: true`) catalog `node_modules`. Inputs: `working_directory` (default `.`), `bun_version` (default `latest`). All deps are public npm — no token needed. Perms: `contents: write`.

### Utility
- **`artifacts-comment.yml`** — Sticky PR comment listing artifacts (nightly.link URLs).
- **`pr-issue-check.yml`** — Reusable PR-time policy gate: fails unless the PR has at least one linked issue (`closingIssuesReferences`) AND every linked issue has the `version` custom field set on its org Projects v2 item (inputs: `enforce_base` default `dev`, `project_number` default `3`, `version_field` default `version`). Designed to back an org-ruleset REQUIRED STATUS CHECK. Only enforces PRs whose base == `enforce_base` (closing keywords only register on the default branch; manual Development links have no API) — other bases and fork PRs succeed with a skip summary. Linked-issue lookup uses GITHUB_TOKEN (`pull-requests: read` + `issues: read`), so only token-readable (in practice same-repo) closing references are verified — unreadable cross-repo references fail/warn explicitly, never pass silently; the Project lookup mints a ci-read App token (App needs Organization Projects: Read + org-wide Issues: Read; client-id from org var `CI_READ_APP_CLIENT_ID`). Callers should trigger on `pull_request` types `[opened, edited, reopened, synchronize]` — `edited` re-runs the check when `Closes #N` is added; setting the Project field emits no PR event (manual re-run).

### Meta CI (meta self-consuming its own reusables)
- **`ci.yml`** — meta repo's own CI. Stable matrix checks are Actionlint, Mise Tasks, and ShellCheck; local `mise run all` still includes `iac:zizmor`. ShellCheck fail-closed enumerates every tracked task/helper plus `.github/scripts/github-actions-scanner.sh`, accepting only stage-0 regular non-symlinks with modes 100644/100755 before Bash/warning analysis. Local Zizmor 1.29.0 is strict-collection/offline/regular/high and accepts only 24 exact line dispositions in `zizmor.yml` (20 existing App trust/cleanup boundaries and 4 protected-`main` self-dogfood boundaries).
- **Hosted self-validation jobs** — `Zizmor Action` replaces the old matrix `Zizmor` check name but not the local gate. It pins official action v0.6.2 and the reviewed Zizmor 1.29.0 image mapping, has an empty token, disables online audits/Advanced Security/SARIF/annotations, and runs without secrets under `contents: read`. It is early-development and tokenless but not fully offline: residual container egress and raw CLI log output are accepted, with final PR CI required as runtime proof. `Grype Path (high, fixed)` pins scan-action v7.4.0 + Grype v0.110.0, uses a nested exact-SHA target and trusted mode-0600 config, blocks fixed High/Critical findings and operational/cleanup failures, and does not cache/upload SARIF; Medium and unfixed findings are outside policy. `GitHub Actions Scanner (experimental)` pins Snyk Labs commit `1a269c9c…` + lock digest, installs tokenlessly with lifecycle scripts disabled, and runs only seven production rules. Its exact base baseline is `UNSAFE_INPUT_ASSIGN=27`, others 0. Findings and failures are informational (`findings`/`incomplete`, never false `clean`); fork, Dependabot, untrusted association, and unsupported event paths are tokenless incomplete with no SHA fallback. Only non-Dependabot push/workflow_dispatch or same-repo OWNER/MEMBER/COLLABORATOR PRs may pass the current-repo token to the exact Node child. Raw output/token is never summarized; source/cache/result cleanup failure blocks. Snyk source updates are manual source/support/lock/baseline reviews. Renovate groups Zizmor action+CLI and Anchore action+Grype, both non-automerge.
- **Rollback/check names** — scanner-only rollback removes the three hosted jobs, wrapper, scanner Renovate/docs and restores the matrix `Zizmor`, while retaining local E2 atoms/config/`all`. Do not publish while a required-check policy still names old `Zizmor`; coordinate replacement with `Zizmor Action` first.
- **`self-supply-chain.yml`** — meta consumes its own `scorecard.yml` reusable (filtered) with `publish: false`. No dependency-submission job — meta has no compiled-language manifests (config only).
- **`self-dependency-review.yml`** — meta's PR-time dependency review via the `dependency-review.yml` reusable.

## Editing Guidelines

- New mise atom: add file under `.mise/tasks/<category>/<name>`, prepend `#MISE description=…` and `#MISE hide=true`. Make executable.
- New facade vocabulary task: edit `templates/facades/mise.<archetype>.toml`. Don't add to atoms (facades only).
- Shared config change in `configs/`: takes effect immediately for consumers (no sync workflow; raw URL fetched at atom runtime).
- Renovate preset change in `renovate-preset.json`: applies to all consumer repos automatically.
- Workflow YAML change: validate with `mise exec -- actionlint <file>` before commit.
- Atom signature change: breaking change requires a coordinated bump in every consumer repo (all repos whose `mise.toml` `task_config.includes` this repo) once `?ref=` is tagged (`v1`). Until tag is cut, `?ref=main` is mutable and `meta:bump` clears mise cache. To cut a tag: `git tag -a v1 -m "Release v1" && git push origin v1`, then bump consumers from `?ref=main` to `?ref=v1`.
