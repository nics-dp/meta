# meta

Guidance for Claude Code working in this repository.

## Repository Purpose

Meta-configuration repository for the nics-dp organization. There is **no buildable code** here — only CI/CD infrastructure and shared configuration:

- **Reusable GitHub Actions workflows** (`.github/workflows/`) — called via `workflow_call`. `mise-task.yml` is the core (checkout + `jdx/mise-action` + mise atom + step summary). Release / SBOM / CodeQL / security / utility workflows live here too.
- **Shared mise atomic tasks** (`.mise/tasks/`) — consumed by other repos via `git::` remote include. All atoms hidden (`#MISE hide=true`).
- **Facade templates** (`templates/facades/mise.<archetype>.toml`) — `go-service`, `go-lib`, `frontend`, `python`, `image`. Consumer repos copy one as their `mise.toml`.
- **Shared configs** (`configs/`) — fetched at atom runtime, never committed into consumers.
- **Renovate preset** (`renovate-preset.json`) — org-level config. `configs/renovate.json` is the consumer-side stub that extends it.

## How Configs Are Consumed

**GitHub Actions workflows** — consumer repos call the reusables:

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

**Mise task sharing** — `git::` remote include in the consumer's `mise.toml`:

```toml
[task_config]
includes = ["git::https://github.com/nics-dp/meta.git//.mise/tasks?ref=main"]
```

**Renovate** — consumer `renovate.json`: `{"extends": ["github>nics-dp/meta:renovate-preset"]}`

**Shared configs** — `lib/fetch-config` resolves each file in order: (1) repo-local file present → use verbatim, never fetch, never delete (a repo can pin its own); (2) otherwise `curl` from `$META_CONFIG_BASE` (default `raw.githubusercontent.com/nics-dp/meta/main/configs`) with retries, registered for cleanup on EXIT; (3) still failing → **fail loud**, never fall through to the tool's built-in defaults (a `--check` would then flag every file, a `--fix` would rewrite the tree in the wrong style). Some configs are deliberately **not** shared:

- `.golangci.yml` — per-repo committed; gofumpt needs a per-module `module-path`, so `go:lint-check` / `go:lint-fix` read the consumer's own file. `go:lint-check` runs `golangci-lint fmt --diff` **and** `run`, both before the exit code is decided (not fail-fast), because `run` only reaches formatting where the repo declares a `formatters:` section and `run.tests: false` excludes test files.
- `vitest.config.ts` / `knip.json` — per-repo committed; `node:test` / `node:knip` / `node:bench-compare` error out when missing.
- `node:lighthouse` prefers any repo-local rc, else fetches `configs/lighthouserc.json` (or `.yml` via `META_LIGHTHOUSE_DEFAULT`).

**Auth (GitHub Apps + DockerHub)**

- **nics-dp-ci-read** App — private module access, CodeQL on private repos, release/snapshot builds, `mise-task.yml` private-modules flag. Client-id from org **variable** `CI_READ_APP_CLIENT_ID` (auto-available to reusables via `vars`); private key from org **secret** `CI_READ_APP_PRIVATE_KEY`, passed by callers as `ci_read_app_private_key`. No PAT. The legacy `ci_read_app_id` input is gone — do not pass it.
- **nics-dp-scorecard** App — `scorecard.yml` ONLY. Org var `SCORECARD_APP_CLIENT_ID` + secret `scorecard_app_private_key`, minted into a short-lived `repo_token` so Scorecard's API queries (Branch-Protection needs `Administration: Read`) score correctly on private repos. Without it Scorecard falls back to `GITHUB_TOKEN`, queries fail, and the run stays non-blocking.
- `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` — `image-release.yml` push.

## Key Files

- `.mise/tasks/{ci,iac,go,node,py,sbom,gs,meta,mise,lib,dc}/` — atomic tasks, all hidden. `mise:validate`, `iac:shellcheck`, `iac:zizmor`, `iac:actionlint` validate task/workflow definitions. `lib/*` are sourced helpers, not tasks (`ci-isolate`, `fetch-config`, `go-env`, `go-version`, `py-env`, `logs`). `dc/` = Docker Compose lifecycle.
- `mise.toml` — tool versions + meta's own aggregates: `ci` = `iac:trivy` + `ci:semgrep`; `all` = `mise:validate` + `iac:actionlint` + `iac:shellcheck` + `iac:zizmor` + `ci` (the auto-release driver's entry point; secret/license scans run separately in the driver).
- `configs/` — `eslint.config.js` (+ eslint-plugin-security), `.prettierrc.json` / `.prettierignore`, `.oxfmtrc.json`, `lighthouserc.json` / `lighthouserc.yml`, `playwright.config.ts` (env-driven via `PW_*`), `renovate.json`.
- `zizmor.yml` — ignore dispositions keyed by **`file:line`**. See the Meta CI note below before editing any workflow.
- `renovate-preset.json` — org preset (replaces Dependabot).

## Workflow Architecture

### Core

**`mise-task.yml`** — Inputs: `task`, `name`, `runs_on` (JSON via `fromJSON()`), `fetch-depth`, `private-modules`. Secret: `ci_read_app_private_key` (client-id via the `CI_READ_APP_CLIENT_ID` org var; the legacy `ci_read_app_id` input is gone). Encapsulates SHA-pinned checkout + `jdx/mise-action` + optional private-module git config + atom run + step summary + enforce.

Implementation invariants (do **not** "simplify" these away):

1. `MISE_MINIMUM_RELEASE_AGE: "0"` disables mise's supply-chain release-age control. Left enabled it injects a pip-only `--uploaded-prior-to=` flag that the uv-backed pipx installer rejects (breaks semgrep et al.). `"0"` requires mise ≥ 2026.6.3.
2. `jdx/mise-action` pins an **exact** mise version, not `latest`, because the self-hosted pool reuses cached mise binaries of mixed versions. Read the current value from its `version:` input; `auto-release.yml`'s `mise_version` default and `self-release.yml`'s explicit pass carry the same version, and the `jdx/mise` custom manager in `renovate.json` bumps all three together. Floor is ≥ 2026.7.0: older builds embed a Sigstore trust root predating GitHub's 2026-06-12 TSA cert rotation and fail artifact-attestation verification on tool installs (jdx/mise#10680).
3. `MISE_USE_VERSIONS_HOST` stays **enabled** (mise default). `mise-versions.jdx.dev` occasionally 403s, but mise then falls back source-direct — cosmetic noise. Setting it `false` to silence the noise removed the cache/fallback layer, and a transient GitHub 504 hard-failed `latest` tool installs (e.g. trivy).

### Release & Build

- **`auto-release.yml`** — Snapshot/release driver; runs `mise run all` plus the secret/license scans, and takes `mise_version` (see invariant 2).
- **`go-release.yml`** — Multi-arch Go binary release (cosign, macOS notarize via quill, GitHub Release).
- **`image-release.yml`** — Docker image to DockerHub + GHCR + attestations + cosign keyless. Outputs `digest` for `sbom-image.yml`.
- **`sbom-image.yml`** — Container CycloneDX 1.6 SBOM (anchore/sbom-action + parlay enrich) + Trivy + Grype scan → Release + Security tab. Its Trivy SARIF (`category: trivy-image`) drops `GO-2026-5932` (`golang.org/x/crypto/openpgp` unmaintained) by rule id unconditionally — Trivy SARIF carries no reachability level (jq, fail-safe: keeps the original on error). The unfixed advisory still ships in the Trivy JSON release asset. Grype needs no filter (`only-fixed: true` already excludes a no-fix advisory).
- **`sbom-source.yml`** — Filesystem SBOM; input `project_name` for artifact naming; same `GO-2026-5932` filter (`category: trivy-source`).
- **`self-release.yml`** — meta dogfooding `auto-release.yml`.

### CodeQL

- **`codeql-reusable.yml`** — CodeQL Advanced (configurable language matrix + Go build).
- **`codeql.yml`** — meta's own (workflow YAML scan only).

### Security

**`security-sarif.yml`** — Runs the gate-only scanners (gosec, govulncheck, semgrep, trivy config, hadolint) and uploads each under its own code-scanning SARIF category. Findings are informational by default.

- Switches: `run_go` master (default `true`), with `run_gosec` / `run_govulncheck` selecting the Go scanners independently (both default `true`).
- **`go_version` defaults to empty → the Go scanners run on the toolchain the caller's own `go.mod` declares** (`go-version-file: go.mod`), not the newest release. gosec and govulncheck report against the Go they execute on, so the old `"stable"` default answered "is this safe once you upgrade" while the question is "is what we ship safe now": every stdlib advisory the caller had not yet adopted was absent from the SARIF, the check stayed green, and code scanning stayed empty with no other signal (measurement in nics-dp/meta#327). An explicit `go_version` from the caller still wins.
  - The version file is the repository **root** `go.mod`, deliberately not `scan_path`: that input scopes only trivy config and semgrep, while vendoring, gosec and govulncheck all build the root module with no `working-directory`. Deriving it from `scan_path` would break a legitimate `scan_path: infra` caller at Set up Go while still scanning the root module.
  - `go.mod` rather than `mise.toml` because `setup-go` parses it natively (no second copy of the version to drift) and this org keeps the two equal. setup-go reads the `toolchain` directive first and falls back to `go`; no repo in this org declares `toolchain` today, so `go` is what is in play.
  - `sbom-source.yml` / `sbom-image.yml` still hardcode `stable` and are deliberately unconverted.
- `gosec_blocking` defaults to `false`. Fail-closed enforcement is active only when `run_go && run_gosec && gosec_blocking`, covering vendor preparation, gosec findings or operational failure, the local SARIF structural precheck, private Go state cleanup, upload-action or terminal processing failure, and SARIF artifact cleanup. In that mode `wait-for-processing: true` treats terminal `failed` as an upload failure, while a polling API error or timeout only warns and leaves processing unknown. govulncheck, semgrep, trivy config and hadolint stay informational — but invalid caller configuration and safety checks such as `scan_path` validation fail independently, so never describe the workflow as unable to fail.
- Secret `ci_read_app_private_key` mints a ci-read App token for private Go module access during gosec/govulncheck.
- The govulncheck step post-filters `GO-2026-5932` out of its SARIF (no native ignore flag; the advisory is transitively-present, never-called, no fixed version). Scoped to that ID **at `note` level only** (govulncheck levels: note = module-only dependency, warning = package imported, error = symbol called), so a genuinely reachable openpgp use still surfaces. Fail-safe.
- Local `go:sast` stays blocking with gosec pinned to `v2.28.0`; a Renovate custom manager keeps that pin and the workflow pin in sync.

**`dependency-review.yml`** — PR-time `actions/dependency-review-action` over the GitHub dependency graph (Go `go.mod` natively supported). **Blocks** PRs introducing dependencies with known vulnerabilities (≥ `fail_on_severity`, default `high`) or disallowed licenses, and posts a summary comment (`comment_summary_in_pr`, default `on-failure`). Optional `allow_licenses` / `deny_licenses` SPDX lists. `runs-on: ubuntu-latest` (no runner input). Callers MUST invoke it from a `pull_request`-triggered workflow.

### Supply Chain

- **`scorecard.yml`** — The only Scorecard variant. Runs `ossf/scorecard-action`, filters posture noise (job-level `TokenPermissionsID`, `nics-dp/` `PinnedDependenciesID`, and `VulnerabilitiesID` findings whose sole vuln is `GO-2026-5932`), uploads `results.filtered.sarif` (`category: scorecard`, non-blocking). Hardcodes `publish_results: false` — the `publish` input is retained for caller compatibility but **ignored**; this never publishes to the public OpenSSF API. Uses the nics-dp-scorecard App to score private repos. Job perms: `contents: read`, `security-events: write`, `actions: read`.
- **`go-dependency-submission.yml`** — Submits the resolved Go dependency graph (`actions/go-dependency-submission`). Inputs: `go_mod_path` (default `go.mod`), `go_build_target` (empty omits the input so the action's own `all` default applies — split across two `if:`-gated steps). `ci_read_app_private_key` mints a token for an org-scoped (`github.com/nics-dp/` only) private-module git rewrite in a short-lived `$RUNNER_TEMP` gitconfig via `GIT_CONFIG_GLOBAL` + `GOPRIVATE`. Perms: `contents: write`.
- **`node-dependency-submission.yml`** — Separate from the Go one because GitHub's dependency graph does **not** parse `bun.lock` (it sees only `package.json` direct deps). Runs `bun install --frozen-lockfile`, then Syft (`anchore/sbom-action`, `dependency-snapshot: true`) catalogs `node_modules` for the full transitive npm graph. Inputs: `working_directory` (default `.`), `bun_version` (default `latest`). All deps public — no token. Perms: `contents: write`.

### Utility

- **`artifacts-comment.yml`** — Sticky PR comment listing artifacts (nightly.link URLs).
- **`pr-issue-check.yml`** — PR-time policy gate backing an org-ruleset **required status check**: fails unless the PR has ≥1 linked issue (`closingIssuesReferences`) AND every linked issue has the `version` field set on its org Projects v2 item. Inputs: `enforce_base` (default `dev`), `project_number` (default `3`), `version_field` (default `version`). Only enforces PRs whose base == `enforce_base` — closing keywords only register on the default branch and manual Development links have no API, so other bases and fork PRs succeed with a skip summary. Linked-issue lookup uses `GITHUB_TOKEN` (`pull-requests: read` + `issues: read`), so only token-readable (in practice same-repo) closing references are verified; unreadable cross-repo references fail or warn explicitly, never pass silently. The Project lookup mints a ci-read token (App needs Organization Projects: Read + org-wide Issues: Read). Callers should trigger on `pull_request` types `[opened, edited, reopened, synchronize]` — `edited` re-runs when `Closes #N` is added; setting the Project field emits no PR event, so that needs a manual re-run.

## Meta CI (meta self-consuming its own reusables)

**`ci.yml`** — meta's own CI:

- Matrix checks via `mise-task.yml`: Actionlint, Mise Tasks, ShellCheck. Plus Secret Scan (`ci:betterleaks`) and Deep Secret Scan (`ci:trufflehog`), and the three hosted self-validation jobs below. The local gate `mise run all` additionally covers `iac:zizmor`, `iac:trivy` and `ci:semgrep`.
- ShellCheck is fail-closed: it enumerates every tracked task/helper plus `.github/scripts/github-actions-scanner.sh` and accepts only stage-0 regular non-symlinks with mode 100644/100755 before analysis.
- **`Zizmor Action`** — pins the official action v0.6.2 and the reviewed Zizmor 1.29.0 image mapping; online audits / Advanced Security / SARIF / annotations disabled. The action hands the Zizmor process a fixed public compatibility placeholder that is **not** a credential and carries no permissions; no GitHub credential reaches that process. Checkout uses the job's `contents: read` token with `persist-credentials: false`. This early-development gate is **not** fully offline or network-isolated — residual container egress and raw CLI log output are accepted, with final PR CI as runtime proof. It replaced the old matrix `Zizmor` **check name** but not the local gate: coordinate any org-ruleset required-check rename with `Zizmor Action`.
- **`Grype Path (high, fixed)`** — pins scan-action v7.4.0 + Grype v0.110.0, uses a nested exact-SHA target and a trusted mode-0600 config, blocks fixed High/Critical findings and operational/cleanup failures, and does not cache or upload SARIF. Medium and unfixed findings are outside policy.
- **`GitHub Actions Scanner (experimental)`** — pins a Snyk Labs commit + lock digest, installs tokenlessly with lifecycle scripts disabled, runs only seven production rules. Findings and failures are informational (`findings` / `incomplete`, never a false `clean`); fork, Dependabot, untrusted-association and unsupported-event paths are tokenless `incomplete` with no SHA fallback. Only non-Dependabot push/`workflow_dispatch`, or same-repo OWNER/MEMBER/COLLABORATOR PRs, may pass the current-repo token to the exact Node child. Raw output and the token are never summarized; source/cache/result cleanup failure blocks the job. Snyk source updates are manual source/support/lock/baseline reviews.
- Renovate groups Zizmor action+CLI and Anchore action+Grype; neither automerges.

**`self-supply-chain.yml`** — meta consumes its own `scorecard.yml` (filtered, `publish: false`). No dependency-submission job: meta has no compiled-language manifests.

**`self-dependency-review.yml`** / **`self-pr-issue-check.yml`** — meta consuming its own `dependency-review.yml` / `pr-issue-check.yml` reusables.

## Editing Guidelines

- **New mise atom**: add `.mise/tasks/<category>/<name>`, prepend `#MISE description=…` and `#MISE hide=true`, make it executable.
- **New facade vocabulary task**: edit `templates/facades/mise.<archetype>.toml` only — facade vocabulary does not belong in atoms.
- **`configs/` change**: takes effect immediately for consumers (raw URL fetched at atom runtime, no sync workflow).
- **`renovate-preset.json` change**: applies to all consumer repos automatically.
- **Workflow YAML change**: validate with `mise exec -- actionlint <file>`, then `mise run all`, before commit.
- **Inserting or removing workflow lines shifts `zizmor.yml`'s `file:line` dispositions.** The symptom is a `dangerous use of GitHub App tokens` finding (`iac:zizmor` exit 14) that looks like a newly introduced security problem but is only an offset. Re-point the affected entries.
- **Atom signature change**: a breaking change needs a coordinated bump in every consumer repo whose `mise.toml` includes this repo, once `?ref=` is tagged. Until a tag is cut, `?ref=main` is mutable and `meta:bump` clears the mise cache. To cut one: `git tag -a v1 -m "Release v1" && git push origin v1`, then move consumers from `?ref=main` to `?ref=v1`.
