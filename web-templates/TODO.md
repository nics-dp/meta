# Web Template TODO

這份清單用來提醒採用 `web-templates/` 的 repo，哪些項目仍需要依 repo 自行決定或補齊。

## Required Before First CI

- 若 repo 沒有 Dockerfile，先從 `.github/workflows/ci.yml` 移除 `hadolint` 與 `trivy-iac` jobs
- 確認 `package.json` 已包含 README 列出的必要 scripts，特別是 `lint`、`typecheck`、`build`、`test:coverage`、`format:check`
- 安裝 README 列出的必要 devDependencies，至少包含 `prettier`、`prettier-plugin-tailwindcss`、`vitest`、`jsdom`、`@vitest/coverage-v8`
- 若保留 `knip` 或 `lighthouse` job，另外安裝 `knip` 與 `@lhci/cli`
- 確認已設定 `GH_PAT_RELEASE_NICSDP`，否則 `release-please.yml` 無法建立會觸發下游 workflows 的 release/tag

## Optional Follow-ups

- 若 repo 需要 Testing Library 的 matcher，再自行新增 `src/test/setup.ts`，並在 `vitest.config.ts` 加回 `setupFiles`
- 若 repo 想啟用 `bundle-size` job，先補上 repo-specific 的 `size-limit` 設定，再把 `.github/workflows/ci.yml` 中的 `bundle-size` job 打開
- 若未來要把 `eslint-plugin-security` 納入集中 ESLint config，必須先確認所有 web repos 都已安裝該 dependency，再統一 rollout

## Sync Rollout Notes

- `configs/vitest.config.ts` 目前刻意維持最小可用版本，避免同步到現有 repo 時因缺少 `src/test/setup.ts` 而壞掉
- `configs/eslint.config.js` 目前不包含 `eslint-plugin-security`，避免 config sync 先於 dependency rollout
- `bundle-size` workflow 仍保留在 meta，但 template 中預設維持註解狀態，不應在新 repo 直接啟用
