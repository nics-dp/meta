# `pr-issue-check.yml` policy gate

Moved verbatim from `CLAUDE.md` on 2026-09-08 (nics-dp/meta#373). The header
comment of `.github/workflows/pr-issue-check.yml` and its `Guard` step win over
this note; prune rather than extend.

Edits since the move:

- 2026-09-08 (#373): added the Bot-author skip and the token-readable
  qualifier; the moved text named only base and fork.

---

**`pr-issue-check.yml`** — PR-time policy gate backing an org-ruleset **required status check**: fails unless the PR has ≥1 linked issue (`closingIssuesReferences`) AND every token-readable linked issue has the `version` field set on its org Projects v2 item. Inputs: `enforce_base` (default `dev`), `project_number` (default `3`), `version_field` (default `version`). Only enforces PRs whose base == `enforce_base` — closing keywords only register on the default branch, manual Development links have no API, and Bot-authored PRs (`pull_request.user.type == "Bot"`) have no human issue behind them, so other bases, fork PRs and Bot-authored PRs succeed with a skip summary. Linked-issue lookup uses `GITHUB_TOKEN` (`pull-requests: read` + `issues: read`), so only token-readable (in practice same-repo) closing references are verified; unreadable cross-repo references fail or warn explicitly, never pass silently. The Project lookup mints a ci-read token (App needs Organization Projects: Read + org-wide Issues: Read). Callers should trigger on `pull_request` types `[opened, edited, reopened, synchronize]` — `edited` re-runs when `Closes #N` is added; setting the Project field emits no PR event, so that needs a manual re-run.
