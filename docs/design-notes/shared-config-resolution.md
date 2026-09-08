# Shared config resolution and the configs that are deliberately not shared

Moved verbatim from `CLAUDE.md` on 2026-09-08 (nics-dp/meta#373). The header
comment of `.mise/tasks/lib/fetch-config` and the guard blocks in the atoms it
names win over this note; prune rather than extend.

Edits since the move:

- 2026-09-08 (#373): the `vitest.config.ts` / `knip.json` bullet named one file
  each; the atoms accept `vitest.config.*` or `vite.config.*` (`node:test`,
  `node:bench-compare`) and any knip config name knip auto-discovers or a
  top-level `knip` field in `package.json` (`node:knip`). Noted in brackets.
- 2026-09-08 (#373, review): the `META_CONFIG_BASE` default was quoted without
  its scheme; it now matches `.mise/tasks/lib/fetch-config` verbatim.

---

**Shared configs** — `lib/fetch-config` resolves each file in order: (1) repo-local file present → use verbatim, never fetch, never delete (a repo can pin its own); (2) otherwise `curl` from `$META_CONFIG_BASE` (default `https://raw.githubusercontent.com/nics-dp/meta/main/configs`, set in `.mise/tasks/lib/fetch-config`) with retries, registered for cleanup on EXIT; (3) still failing → **fail loud**, never fall through to the tool's built-in defaults (a `--check` would then flag every file, a `--fix` would rewrite the tree in the wrong style). Some configs are deliberately **not** shared:

- `.golangci.yml` — per-repo committed; gofumpt needs a per-module `module-path`, so `go:lint-check` / `go:lint-fix` read the consumer's own file. `go:lint-check` runs `golangci-lint fmt --diff` **and** `run`, both before the exit code is decided (not fail-fast), because `run` only reaches formatting where the repo declares a `formatters:` section and `run.tests: false` excludes test files.
- `vitest.config.ts` / `knip.json` — per-repo committed; `node:test` / `node:knip` / `node:bench-compare` error out when missing [the guards accept `vitest.config.*` or `vite.config.*`, and for knip any auto-discovered config file name or a top-level `knip` field in `package.json`].
- `node:lighthouse` prefers any repo-local rc, else fetches `configs/lighthouserc.json` (or `.yml` via `META_LIGHTHOUSE_DEFAULT`).
