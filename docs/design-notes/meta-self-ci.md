# Meta's own CI (meta self-consuming its reusables)

Moved verbatim from `CLAUDE.md` on 2026-09-08 (nics-dp/meta#373).
`.github/workflows/ci.yml`, the `self-*.yml` callers and `renovate.json` win
over this note; prune rather than extend.

Edits since the move:

- 2026-09-08 (#373): the `Zizmor Action` and `Grype Path (high, fixed)` bullets
  carried version literals that had already gone stale against `ci.yml`; the
  literals are removed — the pins are the `uses:` SHA comments and the
  `grype-version:` input in `ci.yml`, tracked by `renovate.json`.
- 2026-09-08 (#373): the hard-coded hosted-job and scanner-rule counts were
  replaced by references to the jobs themselves and to the scanner job's
  `rules` array.

---

**`ci.yml`** — meta's own CI:

- Matrix checks via `mise-task.yml`: Actionlint, Mise Tasks, ShellCheck. Plus Secret Scan (`ci:betterleaks`) and Deep Secret Scan (`ci:trufflehog`), and the hosted self-validation jobs below. The local gate `mise run all` additionally covers `iac:zizmor`, `iac:trivy` and `ci:semgrep`.
- ShellCheck is fail-closed: it enumerates every tracked task/helper plus `.github/scripts/github-actions-scanner.sh` and accepts only stage-0 regular non-symlinks with mode 100644/100755 before analysis.
- **`Zizmor Action`** — pins the official action and the reviewed Zizmor image mapping at the versions in `ci.yml`; online audits / Advanced Security / SARIF / annotations disabled. The action hands the Zizmor process a fixed public compatibility placeholder that is **not** a credential and carries no permissions; no GitHub credential reaches that process. Checkout uses the job's `contents: read` token with `persist-credentials: false`. This early-development gate is **not** fully offline or network-isolated — residual container egress and raw CLI log output are accepted, with final PR CI as runtime proof. It replaced the old matrix `Zizmor` **check name** but not the local gate: coordinate any org-ruleset required-check rename with `Zizmor Action`.
- **`Grype Path (high, fixed)`** — pins scan-action and Grype at the versions in `ci.yml`, uses a nested exact-SHA target and a trusted mode-0600 config, blocks fixed High/Critical findings and operational/cleanup failures, and does not cache or upload SARIF. Medium and unfixed findings are outside policy.
- **`GitHub Actions Scanner (experimental)`** — pins a Snyk Labs commit + lock digest, installs tokenlessly with lifecycle scripts disabled, runs only the production rules listed in the job's `rules` array. Findings and failures are informational (`findings` / `incomplete`, never a false `clean`); fork, Dependabot, untrusted-association and unsupported-event paths are tokenless `incomplete` with no SHA fallback. Only non-Dependabot push/`workflow_dispatch`, or same-repo OWNER/MEMBER/COLLABORATOR PRs, may pass the current-repo token to the exact Node child. Raw output and the token are never summarized; source/cache/result cleanup failure blocks the job. Snyk source updates are manual source/support/lock/baseline reviews.
- Renovate groups Zizmor action+CLI and Anchore action+Grype; neither automerges.

**`self-supply-chain.yml`** — meta consumes its own `scorecard.yml` (filtered, `publish: false`). No dependency-submission job: meta has no compiled-language manifests.

**`self-dependency-review.yml`** / **`self-pr-issue-check.yml`** — meta consuming its own `dependency-review.yml` / `pr-issue-check.yml` reusables.
