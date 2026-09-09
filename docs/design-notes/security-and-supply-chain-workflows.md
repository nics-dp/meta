# Security and supply-chain reusable workflows

Moved verbatim from `CLAUDE.md` on 2026-09-08 (nics-dp/meta#373): the
`sbom-image.yml` / `sbom-source.yml` bullets of "Release & Build" and the whole
"Security" and "Supply Chain" subsections. Each workflow's `workflow_call`
declarations and step comments win over this note; prune rather than extend.

Edits since the move:

- 2026-09-08 (#373): the gosec sentence carried a version literal that was
  stale against `.mise/tasks/go/sast` and `security-sarif.yml`; it is
  replaced by a pointer to the two pinned locations and the `renovate.json`
  custom manager that syncs them.
- 2026-09-08 (#373, review): the `sbom-image.yml` bullet carried the CycloneDX
  spec version literal; it now points at the `format:` pin in each SBOM
  workflow and the step comment that explains it.
- 2026-09-08 (#373, review): the `dependency-review.yml` caller sentence named
  only `pull_request`; the workflow header also admits `pull_request_target`.
- 2026-09-08 (#373, review): the `go_version` rationale asserted that no repo in
  the org declares a `toolchain` directive; that org-wide snapshot is replaced by
  "read the caller's root `go.mod`".

---

### Release & Build (SBOM workflows)

- **`sbom-image.yml`** — Container CycloneDX SBOM (anchore/sbom-action + parlay enrich; the spec version is pinned in each SBOM workflow's `format:` because the scanners lag syft's default, see the step comment there) + Trivy + Grype scan → Release + Security tab. Its Trivy SARIF (`category: trivy-image`) drops `GO-2026-5932` (`golang.org/x/crypto/openpgp` unmaintained) by rule id unconditionally — Trivy SARIF carries no reachability level (jq, fail-safe: keeps the original on error). The unfixed advisory still ships in the Trivy JSON release asset. Grype needs no filter (`only-fixed: true` already excludes a no-fix advisory).
- **`sbom-source.yml`** — Filesystem SBOM; input `project_name` for artifact naming; same `GO-2026-5932` filter (`category: trivy-source`).

### Security

**`security-sarif.yml`** — Runs the gate-only scanners (gosec, govulncheck, semgrep, trivy config, hadolint) and uploads each under its own code-scanning SARIF category. Findings are informational by default.

- Switches: `run_go` master (default `true`), with `run_gosec` / `run_govulncheck` selecting the Go scanners independently (both default `true`).
- **`go_version` defaults to empty → the Go scanners run on the toolchain the caller's own `go.mod` declares** (`go-version-file: go.mod`), not the newest release. gosec and govulncheck report against the Go they execute on, so the old `"stable"` default answered "is this safe once you upgrade" while the question is "is what we ship safe now": every stdlib advisory the caller had not yet adopted was absent from the SARIF, the check stayed green, and code scanning stayed empty with no other signal (measurement in nics-dp/meta#327). An explicit `go_version` from the caller still wins.
  - The version file is the repository **root** `go.mod`, deliberately not `scan_path`: that input scopes only trivy config and semgrep, while vendoring, gosec and govulncheck all build the root module with no `working-directory`. Deriving it from `scan_path` would break a legitimate `scan_path: infra` caller at Set up Go while still scanning the root module.
  - `go.mod` rather than `mise.toml` because `setup-go` parses it natively (no second copy of the version to drift) and this org keeps the two equal. setup-go reads the `toolchain` directive first and falls back to `go`; read the caller's root `go.mod` to know which one applies.
  - `sbom-source.yml` / `sbom-image.yml` still hardcode `stable` and are deliberately unconverted.
- `gosec_blocking` defaults to `false`. Fail-closed enforcement is active only when `run_go && run_gosec && gosec_blocking`, covering vendor preparation, gosec findings or operational failure, the local SARIF structural precheck, private Go state cleanup, upload-action or terminal processing failure, and SARIF artifact cleanup. In that mode `wait-for-processing: true` treats terminal `failed` as an upload failure, while a polling API error or timeout only warns and leaves processing unknown. govulncheck, semgrep, trivy config and hadolint stay informational — but invalid caller configuration and safety checks such as `scan_path` validation fail independently, so never describe the workflow as unable to fail.
- Secret `ci_read_app_private_key` mints a ci-read App token for private Go module access during gosec/govulncheck.
- The govulncheck step post-filters `GO-2026-5932` out of its SARIF (no native ignore flag; the advisory is transitively-present, never-called, no fixed version). Scoped to that ID **at `note` level only** (govulncheck levels: note = module-only dependency, warning = package imported, error = symbol called), so a genuinely reachable openpgp use still surfaces. Fail-safe.
- Local `go:sast` stays blocking with gosec pinned in the atom's `#MISE tools=` header; `security-sarif.yml` carries the same pin in its `go install` line, and a Renovate custom manager in `renovate.json` keeps the two in sync.

**`dependency-review.yml`** — PR-time `actions/dependency-review-action` over the GitHub dependency graph (Go `go.mod` natively supported). **Blocks** PRs introducing dependencies with known vulnerabilities (≥ `fail_on_severity`, default `high`) or disallowed licenses, and posts a summary comment (`comment_summary_in_pr`, default `on-failure`). Optional `allow_licenses` / `deny_licenses` SPDX lists. `runs-on: ubuntu-latest` (no runner input). Callers MUST invoke it from a `pull_request`- or `pull_request_target`-triggered workflow (the action needs the PR base/head refs to diff; any other event errors).

### Supply Chain

- **`scorecard.yml`** — The only Scorecard variant. Runs `ossf/scorecard-action`, filters posture noise (job-level `TokenPermissionsID`, `nics-dp/` `PinnedDependenciesID`, and `VulnerabilitiesID` findings whose sole vuln is `GO-2026-5932`), uploads `results.filtered.sarif` (`category: scorecard`, non-blocking). Hardcodes `publish_results: false` — the `publish` input is retained for caller compatibility but **ignored**; this never publishes to the public OpenSSF API. Uses the nics-dp-scorecard App to score private repos. Job perms: `contents: read`, `security-events: write`, `actions: read`.
- **`go-dependency-submission.yml`** — Submits the resolved Go dependency graph (`actions/go-dependency-submission`). Inputs: `go_mod_path` (default `go.mod`), `go_build_target` (empty omits the input so the action's own `all` default applies — split across two `if:`-gated steps). `ci_read_app_private_key` mints a token for an org-scoped (`github.com/nics-dp/` only) private-module git rewrite in a short-lived `$RUNNER_TEMP` gitconfig via `GIT_CONFIG_GLOBAL` + `GOPRIVATE`. Perms: `contents: write`.
- **`node-dependency-submission.yml`** — Separate from the Go one because GitHub's dependency graph does **not** parse `bun.lock` (it sees only `package.json` direct deps). Runs `bun install --frozen-lockfile`, then Syft (`anchore/sbom-action`, `dependency-snapshot: true`) catalogs `node_modules` for the full transitive npm graph. Inputs: `working_directory` (default `.`), `bun_version` (default `latest`). All deps public — no token. Perms: `contents: write`.
