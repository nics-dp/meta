# `mise-task.yml` implementation invariants

Moved verbatim from `CLAUDE.md` on 2026-09-08 (nics-dp/meta#373). The workflow
file and the comments inside it win over this note; prune rather than extend.

Edits since the move:

- 2026-09-08 (#373): the encapsulation sentence predates the job-local Go cache
  steps (`Prepare job-local Go roots` through `Cleanup Go cache`) and the
  `Revoke private-module credential` step; they are appended in brackets.
- 2026-09-08 (#373, review): invariant 2 counted the synchronized mise-version
  locations ("all three"); it now says "these locations" so `renovate.json`
  stays the only source.
- 2026-09-14 (#395): invariant 4 added (pinned task-level tools,
  `MISE_FETCH_REMOTE_VERSIONS_TIMEOUT`, `require_tool`).

---

**`mise-task.yml`** — Inputs: `task`, `name`, `runs_on` (JSON via `fromJSON()`), `fetch-depth`, `private-modules`. Secret: `ci_read_app_private_key` (client-id via the `CI_READ_APP_CLIENT_ID` org var; the legacy `ci_read_app_id` input is gone). Encapsulates SHA-pinned checkout + `jdx/mise-action` + optional private-module git config + atom run + step summary + enforce [and, since the move: job-local Go build / module cache roots under `RUNNER_TEMP` with restore, sanitize, save and cleanup steps, plus a credential-revoke step that runs under `always()`].

Implementation invariants (do **not** "simplify" these away):

1. `MISE_MINIMUM_RELEASE_AGE: "0"` disables mise's supply-chain release-age control. Left enabled it injects a pip-only `--uploaded-prior-to=` flag that the uv-backed pipx installer rejects (breaks semgrep et al.). `"0"` requires mise ≥ 2026.6.3.
2. `jdx/mise-action` pins an **exact** mise version, not `latest`, because the self-hosted pool reuses cached mise binaries of mixed versions. Read the current value from its `version:` input; `auto-release.yml`'s `mise_version` default and `self-release.yml`'s explicit pass carry the same version, and the `jdx/mise` custom manager in `renovate.json` bumps these locations together. Floor is ≥ 2026.7.0: older builds embed a Sigstore trust root predating GitHub's 2026-06-12 TSA cert rotation and fail artifact-attestation verification on tool installs (jdx/mise#10680).
3. `MISE_USE_VERSIONS_HOST` stays **enabled** (mise default). `mise-versions.jdx.dev` occasionally 403s, but mise then falls back source-direct — cosmetic noise. Setting it `false` to silence the noise removed the cache/fallback layer, and a transient GitHub 504 hard-failed `latest` tool installs (e.g. trivy).
4. Task-level tools in the atoms (`#MISE tools=`) are pinned to **exact** versions and bumped by the `renovate.json` custom managers, never `latest`. Resolving `latest` for a Go-backend tool lists every tag from the module proxy inside mise's remote-versions timeout, and on timeout mise only warns and runs the task without the tool (`command not found`, nics-dp/meta#395); an exact version resolves with no listing. `MISE_FETCH_REMOTE_VERSIONS_TIMEOUT: "60s"` covers any remaining `latest`, and `.mise/tasks/lib/require-tool` fails an atom at the top when its tool is missing. Scanner freshness is a run-time property (trivy-db, grype-db, the opengrep registry); the pins carry a 3-day release-age buffer and automerge daily — see the `security scanners` rules in `renovate.json`.
