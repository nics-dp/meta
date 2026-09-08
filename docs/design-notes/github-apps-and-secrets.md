# GitHub Apps and secrets used by the reusable workflows

Moved verbatim from `CLAUDE.md` on 2026-09-08 (nics-dp/meta#373). Each
workflow's `workflow_call` `secrets:` declaration and the `vars.*` references
inside it win over this note; prune rather than extend.

Edits since the move:

- 2026-09-08 (#373): added the release App entry; the moved text did not
  mention `PRE_RELEASE_APP_CLIENT_ID` / `pre_release_app_private_key`, which
  `auto-release.yml` declares for non-dry-run releases.
- 2026-09-08 (#373): the DockerHub entry names the `workflow_call` secret names
  (`dockerhub_username` / `dockerhub_token`) a caller passes, next to the org
  secret names.

---

**Auth (GitHub Apps + DockerHub)**

- **nics-dp-ci-read** App — private module access, CodeQL on private repos, release/snapshot builds, `mise-task.yml` private-modules flag. Client-id from org **variable** `CI_READ_APP_CLIENT_ID` (auto-available to reusables via `vars`); private key from org **secret** `CI_READ_APP_PRIVATE_KEY`, passed by callers as `ci_read_app_private_key`. No PAT. The legacy `ci_read_app_id` input is gone — do not pass it.
- **nics-dp-scorecard** App — `scorecard.yml` ONLY. Org var `SCORECARD_APP_CLIENT_ID` + secret `scorecard_app_private_key`, minted into a short-lived `repo_token` so Scorecard's API queries (Branch-Protection needs `Administration: Read`) score correctly on private repos. Without it Scorecard falls back to `GITHUB_TOKEN`, queries fail, and the run stays non-blocking.
- Release App (added at the move) — `auto-release.yml` ONLY. Org var `PRE_RELEASE_APP_CLIENT_ID` + secret `pre_release_app_private_key`; the App must be a `main` / `dev` ruleset bypass actor and is needed only for real (non-dry-run) releases. See the secret's `description` in the workflow.
- `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` — `image-release.yml` push (passed by callers as `dockerhub_username` / `dockerhub_token`).
