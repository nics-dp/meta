# Project: meta (nics-dp shared CI/CD configuration)

The meta-configuration repository of the `nics-dp` organization. There is no
buildable code here, only what many nics-dp repositories consume: shared
mise task atoms (`.mise/tasks/`), reusable GitHub Actions workflows
(`.github/workflows/`, called via `workflow_call`), facade templates
(`templates/facades/`), shared tool configs fetched at atom runtime (`configs/`)
and the org Renovate preset (`renovate-preset.json`). Stack: bash atoms under
mise · GitHub Actions YAML · Renovate JSON.

This file is an index, not a description. The code is the source of truth; each
entry below says where to look and which invariants are intentional. GitHub
Copilot code review reads this file too. Long-form rationale lives in
`docs/design-notes/`; `README.md` (zh-TW) carries the per-atom and per-workflow
tables and the consumer setup steps. Because this repository is upstream of its
consumers, an entry here is a contract, and how a change reaches them depends on
the contract: an atom on the consumer's next `mise run` after `meta:bump` or a
cache expiry, a `configs/` file on the next atom run unless the consumer keeps a
repo-local copy, a reusable workflow on its own callers' next run, the Renovate
preset on Renovate's next evaluation, a facade template never (see the Gotchas
and the polyrepo map before judging blast radius).

## Where things are

- `.mise/tasks/<category>/<name>` — one executable bash file per atom under
  `ci/`, `iac/`, `go/`, `node/`, `py/`, `sbom/`, `gs/`, `dc/`, `meta/`, `mise/`.
  Each is hidden (`#MISE hide=true`); an atom that needs a tool beyond bash
  and the consumer's own toolchain declares it inline in `#MISE tools=`.
  `lib/` holds sourced helpers, not tasks (`ci-isolate`,
  `fetch-config`, `go-env`, `go-version`, `logs`, `py-env`).
- `.github/workflows/` — the reusable workflows: `mise-task.yml` (the runner
  every consumer CI matrix calls), `auto-release.yml`, `go-release.yml`,
  `image-release.yml`, `sbom-source.yml`, `sbom-image.yml`,
  `codeql-reusable.yml`, `security-sarif.yml`, `dependency-review.yml`,
  `scorecard.yml`, `go-dependency-submission.yml`,
  `node-dependency-submission.yml`, `artifacts-comment.yml`,
  `pr-issue-check.yml`. Meta's own: `ci.yml`, `codeql.yml` and the `self-*.yml`
  callers that dogfood the reusables. `.github/scripts/github-actions-scanner.sh`
  is the wrapper `ci.yml`'s scanner job execs. Inputs, secrets, outputs and
  defaults are the `workflow_call` declarations at the top of each file.
- `templates/facades/mise.<archetype>.toml` — `go-service`, `go-lib`,
  `frontend`, `python`, `image`. Facade vocabulary (`init`, `test`, `ci`,
  `release-check`, `all`, …) lives only here; a consumer copies one as its
  `mise.toml` and extends it.
- `configs/` — `eslint.config.js`, `.prettierrc.json`, `.prettierignore`,
  `.oxfmtrc.json`, `lighthouserc.json` / `.yml`, `playwright.config.ts`
  (env-driven via `PW_*`), and `renovate.json` (the consumer-side stub that
  extends the preset).
- `renovate-preset.json` — the org preset consumers extend. `renovate.json` —
  meta's own config: extends the preset and adds the custom managers for pins
  that exist only in this repository's workflows and atoms.
- `zizmor.yml` — Zizmor dispositions keyed by `file:line`.
- `mise.toml` — meta's own facade (`ci`, `all`, `sbom`) over the local
  `.mise/tasks`; `[tools]` holds only project-level tools (`act`) because atoms
  declare theirs inline.
- `docs/design-notes/` — rationale moved out of this file.

## Commands

`mise tasks` lists the facades; `mise tasks ls --hidden` lists the atoms.

- `mise run all` is the whole validation gate and the entry point
  `auto-release.yml` runs: `mise:validate`, `iac:actionlint`, `iac:shellcheck`,
  `iac:zizmor` and `ci` (`iac:trivy` + `ci:semgrep`), all read-only and in
  parallel. There is no build or test task. The release driver fails when
  `mise run all` leaves the working tree modified, so every step of `all` must
  stay read-only. → the `[tasks.all]` comment in `mise.toml`, the "Run mise
  run all" step in `auto-release.yml`.
- `mise run ci` is `iac:trivy` + `ci:semgrep` alone. `iac:trivy` runs with
  `--exit-code 0`, so findings do not fail the gate; a Trivy operational
  error (bad config, scan or DB failure) still exits non-zero and does.
- Single workflow file: `mise exec -- actionlint <file>`; then `mise run all`
  before committing a workflow change.
- Secret scans are not in `all`: `ci.yml` runs `ci:betterleaks` on every PR and
  `ci:trufflehog` only on PRs whose base is `main` or `release/**`;
  `auto-release.yml` runs `ci:trivy-license`, `ci:betterleaks` and
  `ci:trufflehog` as separate steps after `all`.
- Consumers refresh `?ref=main` atoms with `mise run meta:bump`
  (`mise cache clear` + `mise install`); each facade template chains it into
  `init` and `update`, except `mise.image.toml`, whose `init` is a no-op and
  which chains it into `update` alone.

## Intentional conventions — do not "fix"

Rule, why it is intentional, where it is pinned. Read the named file or comment
before changing any of these; the mechanism is in the code, the history in
`docs/design-notes/`.

**Atoms**

- Every atom is hidden (`#MISE hide=true`) and declares inline any tool it
  needs beyond bash (`#MISE tools={…}`), so a consumer's `mise tasks ls`
  shows only its own facade and tool pins travel with the atom. Facade
  vocabulary never goes into an atom. → any file under `.mise/tasks/`,
  `templates/facades/`.
- Atoms and helpers are tracked as stage-0 regular files with mode `100644` or
  `100755`; `iac:shellcheck` enumerates them from the git index and fails
  closed on anything else (symlink, empty file, unexpected path).
  → `.mise/tasks/iac/shellcheck`.
- The definition checks `mise:validate`, `iac:shellcheck` and `iac:zizmor`
  source `lib/ci-isolate` first: it points `GIT_CONFIG_GLOBAL` at an empty
  mode-0600 file and unsets the `GH_TOKEN` / `GITHUB_TOKEN` and `GOPRIVATE`
  families so an external tool cannot read the runner's credentials.
  → `.mise/tasks/lib/ci-isolate`.
- `go:lint-check` runs `golangci-lint fmt --diff` and `golangci-lint run`, both
  before the exit code is decided (not fail-fast): `run` reaches formatting only
  where a repo declares `formatters:`, with test scope controlled by `run.tests`.
  → the header comment in `.mise/tasks/go/lint-check`.
- `go:sast` pins gosec in its `#MISE tools=` header; `security-sarif.yml` pins
  the same tool in its `go install` line, and the "synchronized gosec pins"
  custom manager in `renovate.json` moves both together. Do not bump one alone.
- `meta:bump` is `mise cache clear` + `mise install` and nothing else; it is
  unconditional — pinning a tag instead of `?ref=main` bounds which revision
  the include resolves to, it does not make the task a no-op.
  → `.mise/tasks/meta/bump`.
- File-mutating lint / format atoms are named `*-fix` and paired with a
  `*-check`; the facade templates define `release-check` as `ci` minus the
  `*-fix` atoms on that basis. → `templates/facades/*.toml`.

**Shared configs** → `docs/design-notes/shared-config-resolution.md`

- `lib/fetch-config` resolves each file as repo-local first (used verbatim,
  never fetched, never deleted), else fetched from `META_CONFIG_BASE` with
  retries and removed on EXIT, else fail loud. It never falls back to the tool's
  built-in defaults and never logs the expanded base URL (it may carry a
  credential). Detection is by file presence, not git status. → the header
  comment of `.mise/tasks/lib/fetch-config`; callers are the `node:lint-*`,
  `node:format-*`, `node:oxfmt-*` and `node:e2e` atoms.
- `node:lighthouse` applies the same repo-local-wins rule on its own, then
  fetches `lighthouserc.json` (or `.yml` via `META_LIGHTHOUSE_DEFAULT`).
  → `.mise/tasks/node/lighthouse`.
- Deliberately not shared: `.golangci.yml` (gofumpt needs a per-module
  `module-path`; `go:lint-check` / `go:lint-fix` read the consumer's file) and
  the vitest / knip configs (`node:test`, `node:bench-compare`, `node:knip` fail
  when the repo-local file is missing instead of running on tool defaults).
  → the guard blocks in those atoms.

**`mise-task.yml`** → `docs/design-notes/mise-task-invariants.md`

- `MISE_MINIMUM_RELEASE_AGE: "0"` stays; `jdx/mise-action` pins an exact mise
  version, not `latest`; `MISE_USE_VERSIONS_HOST` is left at the mise default.
  The version pin is carried in `mise-task.yml`, `auto-release.yml`'s
  `mise_version` default and `self-release.yml`, and the "synchronized mise
  pins" custom manager in `renovate.json` bumps them together. → the `env:`
  comment on the `run` job.
- `inputs.task` reaches the shell through an env variable and `read -ra`, never
  an inline `${{ }}` (semgrep run-shell-injection). → the "Run" step comment.
- The private-module App token is minted only when `private-modules` is set and
  the trigger is not `pull_request_target` / `workflow_run`
  (`UNTRUSTED_TRIGGER`); the job-local gitconfig lives in `RUNNER_TEMP` and is
  revoked under `always()`; the remote Go cache is disabled whenever private
  modules are in scope. → `HAS_CI_APP`, "Revoke private-module credential",
  "Resolve Go cache".
- The step summary reads only the job-local output file the "Run" step created
  (`output_ready`), never runner leftovers. → "Job summary".

**Reusable workflows** → `docs/design-notes/security-and-supply-chain-workflows.md`,
`docs/design-notes/pr-issue-check.md`

- `security-sarif.yml` is informational by default; fail-closed enforcement
  exists only under `run_go && run_gosec && gosec_blocking`
  (`EFFECTIVE_BLOCKING`), and caller-configuration checks such as `scan_path`
  validation fail independently of it. The Go scanners run on the toolchain of
  the repository root `go.mod` unless `go_version` is set. → the input
  descriptions and the "Set up Go" step.
- `GO-2026-5932` (`golang.org/x/crypto/openpgp`, unmaintained, no fix) is
  filtered per scanner with the narrowest scope each SARIF can express:
  govulncheck drops it at `note` level only, the Trivy SARIF in
  `sbom-source.yml` / `sbom-image.yml` drops it by rule id, `scorecard.yml`
  drops a `VulnerabilitiesID` finding whose sole vuln is that id; Grype needs no
  filter because `only-fixed: true` already excludes it. Each filter keeps the
  original SARIF on error. → the filter steps naming that id.
- `scorecard.yml` never publishes to the public OpenSSF API:
  `publish_results: false` is hardcoded and the `publish` input is kept only for
  caller compatibility. The posture-noise filter writes `results.filtered.sarif`
  and uploads under `category: scorecard`. → the header comment and the filter
  step.
- `pr-issue-check.yml` enforces only PRs whose base equals `enforce_base`
  (default `dev`); other bases, fork PRs and Bot-authored PRs
  (`pull_request.user.type == "Bot"`) pass with a skip summary — closing
  keywords register only on the default branch, forks cannot mint the App
  token, and automation PRs have no human issue behind them. The
  closing-reference lookup uses `GITHUB_TOKEN`; the Project field lookup uses
  the ci-read App token. → the header comment, the "Guard" step.
- `dependency-review.yml` must be called from a `pull_request`- or
  `pull_request_target`-triggered workflow (the action needs the PR base/head
  refs); `node-dependency-submission.yml` exists apart from the Go one
  because GitHub's dependency graph does not parse `bun.lock`. → the header
  comments.
- `auto-release.yml` runs `mise run all` and fails if the tree changed; the
  secret / license scans run as separate steps after it. → "Run mise run all".

**GitHub Apps and secrets** → `docs/design-notes/github-apps-and-secrets.md`

- Client ids come from org variables (`CI_READ_APP_CLIENT_ID`,
  `SCORECARD_APP_CLIENT_ID`, `PRE_RELEASE_APP_CLIENT_ID`), auto-available to
  reusables via `vars`; private keys are passed by the caller as
  `workflow_call` secrets (`ci_read_app_private_key`,
  `scorecard_app_private_key`, `pre_release_app_private_key`). No PAT anywhere.
  The legacy `ci_read_app_id` input no longer exists. → each workflow's
  `secrets:` declaration.
- The scorecard App is used by `scorecard.yml` only; the release App only by
  `auto-release.yml` for non-dry-run releases; DockerHub credentials only by
  `image-release.yml` (`dockerhub_username` / `dockerhub_token`).

**Renovate**

- The org preset leaves `github-actions` unpinned by digest on purpose so the
  mutable `nics-dp/meta/...@main` reusables keep working; Dockerfile and
  compose images do get `pinDigests`. Internal `github.com/nics-dp/**` Go
  modules are disabled (they move through `go:lib-remote`). → the
  `description` fields of those `packageRules` in `renovate-preset.json`.
- Pins that exist only in this repository's workflows and atoms (quill, parlay,
  gosec, govulncheck, air, shellcheck, zizmor, grype, the mise version) are
  tracked by the custom managers in meta's own `renovate.json`, not the preset.
  Zizmor action + CLI, Anchore action + Grype and the mise pins are grouped and
  never automerge. → `renovate.json`.

**Meta's own CI** → `docs/design-notes/meta-self-ci.md`

- The check names in `ci.yml` (`Actionlint`, `Mise Tasks`, `ShellCheck`,
  `Zizmor Action`, `Grype Path (high, fixed)`,
  `GitHub Actions Scanner (experimental)`, `Secret Scan`, `Deep Secret Scan`)
  are what an org-ruleset required-check policy references; `Zizmor Action`
  replaced the old matrix `Zizmor` name, so rename together with the ruleset,
  not before.
- `Zizmor Action` passes `token: "offline-placeholder"`: the action requires a
  value even with online audits disabled, and it is deliberately not
  `github.token` or a secret. → the comment above that input in `ci.yml`.
- `GitHub Actions Scanner (experimental)` is informational: findings and
  failures are reported as `findings` / `incomplete`, never as a false `clean`,
  and the repo token reaches the scanner only on trusted triggers.
  → the `GITHUB_TOKEN` expression and "Classify scanner result" in `ci.yml`.
- `Grype Path (high, fixed)` blocks fixed High/Critical findings only
  (`only-fixed: true`, `severity-cutoff: high`) and fails on any cleanup
  failure; Medium and unfixed findings are outside its policy. → the
  `grype-path` job in `ci.yml`.

## Gotchas the code does not show

- `?ref=main` is mutable: an atom change is live for every consumer on its next
  `mise run` after `meta:bump` or a cache expiry, and a `configs/` change is
  live immediately (raw URL fetched at runtime) except where a consumer commits
  a repo-local copy. There is no sync workflow.
- An atom signature change is a breaking API change for every consumer in the
  polyrepo map. The intended escape is a tag (`git tag -a v1 …`) and moving
  consumers from `?ref=main` to `?ref=v1`.
- Inserting or removing workflow lines shifts `zizmor.yml`'s `file:line`
  dispositions. The symptom is a `dangerous use of GitHub App tokens` finding
  (`iac:zizmor` exit 14) that looks like a new security problem but is only an
  offset; re-point the entries.
- `lib/fetch-config` and `node:lighthouse` detect a repo-local config by file
  presence, so a fetched file left behind by a hard-killed run is treated as
  repo-local until removed.
- `ci_read_app_id` is not a declared input any more; GitHub rejects a call that
  still passes it.
- `mise-task.yml` and the definition-check atoms assume a bash-capable runner
  and a `RUNNER_TEMP` that is absolute and single-line; the steps refuse to run
  otherwise rather than fall back.
- `security-sarif.yml`'s `scan_path` scopes only trivy config and semgrep; the
  Go scanners always build the root module.

## Testing and style

- There is no general test task. Validation is `mise run all`; run it (and
  `mise exec -- actionlint <file>` for a single workflow) before committing.
  Regression suites live under `.github/tests/`; a change to the semgrep
  suppression filter in `security-sarif.yml` must run
  `test_semgrep_suppression.py`. → the command in
  `.github/tests/fixtures/semgrep/README.md`.
- New atom: `.mise/tasks/<category>/<name>`, first lines `#!/usr/bin/env bash`,
  `#MISE description=…`, `#MISE hide=true`, tools in `#MISE tools={…}` when
  the atom needs any, mode `100755`. Bash only; ShellCheck runs at
  `--shell=bash --severity=warning`.
- Workflows: every `uses:` of an external action is SHA-pinned with a version
  comment. Reusable workflows are the deliberate exception: `ci.yml` calls
  `mise-task.yml` by local path and the `self-*.yml` callers use `@main`, the
  same mutable ref every consumer uses. Workflow inputs cross into `run:`
  through `env:`, not inline expressions. Private job state — the gitconfigs
  that carry App tokens, `security-sarif.yml`'s `GOBIN`, `mise-task.yml`'s
  job-local Go cache roots — lives under `RUNNER_TEMP` and is removed under
  `always()`; scanner outputs meant for upload (`results.filtered.sarif`,
  `semgrep.sarif`) stay in the workspace. → each workflow's cleanup steps.
- No hard-coded counts, line numbers or duplicated version literals in
  `CLAUDE.md` / `docs/design-notes/`; point at the file that holds the pin.

## Polyrepo map

Everything in this repository is a contract consumed elsewhere; there is no
vendored copy of a consumer here. The consumers below were read from each
repository's `origin/dev` on 2026-09-08; re-verify there before asserting how a
consumer uses a contract.

| Contract (owned here)                                                                                               | Consumers                                                                                                                                                                                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.mise/tasks` atoms via `task_config.includes = ["git::https://github.com/nics-dp/meta.git//.mise/tasks?ref=main"]` | libdcf, ZenQuery, dcf-platform, dcf-platform-web, dcf-platform-cli, dcf-proxy, dcf-access, dcf-access-web, dcf-access-cli, dcf-catalog (root, `web/` and `vecsea/`), dcf-service, dcf-synth (root and `synth-core/`), dcf-mcp, otel-bundle, dcf-local-env, dcf-smoke, dcf-autoCICD, patroni; dcf-cloud-env includes the same path without `?ref=` |
| `templates/facades/*` (copied, then extended per repo: `release-check`, `lib:local`, …)                             | every consumer above owns its own `mise.toml`; a template change does not propagate                                                                                                                                                                                                                                                               |
| `mise-task.yml`                                                                                                     | every consumer above except dcf-autoCICD and dcf-cloud-env                                                                                                                                                                                                                                                                                        |
| `pr-issue-check.yml`                                                                                                | every consumer above except dcf-cloud-env, plus dcf-db-cfg and dcf-cfg-templates                                                                                                                                                                                                                                                                  |
| `auto-release.yml`                                                                                                  | libdcf, ZenQuery, dcf-platform, dcf-platform-web, dcf-platform-cli, dcf-proxy, dcf-access, dcf-access-web, dcf-access-cli, dcf-catalog, dcf-service, dcf-synth, dcf-mcp, otel-bundle, patroni                                                                                                                                                     |
| `sbom-source.yml` / `codeql-reusable.yml`                                                                           | the `auto-release.yml` set without patroni for `sbom-source.yml`; the `auto-release.yml` set plus dcf-local-env for `codeql-reusable.yml`                                                                                                                                                                                                         |
| `go-release.yml` / `artifacts-comment.yml`                                                                          | dcf-platform, dcf-platform-cli, dcf-proxy, dcf-access, dcf-access-cli, dcf-catalog, dcf-service, dcf-synth, dcf-mcp, otel-bundle                                                                                                                                                                                                                  |
| `image-release.yml` + `sbom-image.yml`                                                                              | dcf-platform, dcf-proxy, dcf-access, dcf-catalog, dcf-service, dcf-synth, dcf-mcp, otel-bundle, patroni                                                                                                                                                                                                                                           |
| `security-sarif.yml` / `scorecard.yml`                                                                              | libdcf, ZenQuery, dcf-platform, dcf-platform-web, dcf-platform-cli, dcf-proxy, dcf-access, dcf-access-web, dcf-access-cli, dcf-service, dcf-synth, otel-bundle, dcf-local-env, dcf-smoke, patroni (not dcf-catalog or dcf-mcp)                                                                                                                    |
| `dependency-review.yml`                                                                                             | libdcf, ZenQuery, dcf-platform, dcf-platform-web, dcf-platform-cli, dcf-proxy, dcf-access, dcf-access-web, dcf-access-cli, dcf-service, dcf-synth, otel-bundle                                                                                                                                                                                    |
| `go-dependency-submission.yml` / `node-dependency-submission.yml`                                                   | Go: libdcf, ZenQuery, dcf-platform, dcf-platform-cli, dcf-proxy, dcf-access, dcf-access-cli, dcf-service, dcf-synth, otel-bundle. Node: dcf-platform-web, dcf-access-web                                                                                                                                                                          |
| `configs/*` fetched at atom runtime (`META_CONFIG_BASE`)                                                            | dcf-platform-web and dcf-catalog `web/` set `META_CONFIG_BASE` explicitly to the default; dcf-access-web relies on the default; dcf-platform-web, dcf-access-web and dcf-catalog `web/` commit the vitest / vite config and knip config that `node:test` / `node:knip` require                                                                    |
| `renovate-preset.json` via `github>nics-dp/meta:renovate-preset`                                                    | every consumer above except dcf-mcp, dcf-autoCICD and dcf-cfg-templates, which had no `renovate.json` on `origin/dev`; plus dcf-claude-plugins, which consumes the preset only (no `mise.toml`, no workflow calls)                                                                                                                                |
| Org variable / secret names (`CI_READ_APP_CLIENT_ID`, `ci_read_app_private_key`, …) and the `README.md` setup steps | callers of the reusable workflows whose `workflow_call` block declares them (read the file; `dependency-review.yml`, `artifacts-comment.yml`, `node-dependency-submission.yml` and `sbom-image.yml` declare none)                                                                                                                                 |

## Design notes

`docs/design-notes/` holds the long-form rationale moved out of this file. Code
and workflow files win over them; prune rather than extend.
