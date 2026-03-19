# Changelog

## 1.0.0 (2026-03-19)


### Features

* **ci:** add CI reusable workflows and templates ([23a7b8d](https://github.com/nics-dp/meta/commit/23a7b8dcd7187c5fd2a1c5ff145745bd3df14920))
* **ci:** add CI reusable workflows and templates ([a33a38c](https://github.com/nics-dp/meta/commit/a33a38ce34bba088efa7c685c90e5973c02e4096))
* **ci:** add coverage summary sticky PR comment to go-test report ([3204b82](https://github.com/nics-dp/meta/commit/3204b82f510af2bfa63c1394aed63f43f8011a21))
* **ci:** use `cosign-installer@v4` ([ae148dd](https://github.com/nics-dp/meta/commit/ae148dd0a96e1067f0185ee1e9f503602d863cef))
* first commit ([b5bb105](https://github.com/nics-dp/meta/commit/b5bb105c727fb9c4c944428826d72d77dbc8d5bf))
* **goreleaser:** add macos notarize settings ([93143a7](https://github.com/nics-dp/meta/commit/93143a7122f0610ecfb1bdf55f595693a9cfcfcf))
* **infra:** add utility workflows, codeql configs, and cleanup ([401166f](https://github.com/nics-dp/meta/commit/401166fad1ac1ddc7b0f428cc92c62b4c8bbe10e))
* **release:** add release reusable workflows and templates ([855257b](https://github.com/nics-dp/meta/commit/855257b45a3be14a1633e02a9c808edf6443e2e2))
* **release:** add release reusable workflows and templates ([3d96345](https://github.com/nics-dp/meta/commit/3d963452b23b2f18136c6ff08dbbddd0b9ba12ab))


### Bug Fixes

* add ci scope to commitlint config template ([2bbd9dd](https://github.com/nics-dp/meta/commit/2bbd9dd2ea2f26d20af2d1fd1867319684f7c215))
* add permisssions for `commitlint.yml` ([502d934](https://github.com/nics-dp/meta/commit/502d93450df38aeea4d1517e0651779d4eb1d081))
* address review comments for release-pipeline PR ([4392db7](https://github.com/nics-dp/meta/commit/4392db747cabb591c8db10766a64db52fe781858))
* **ci:** add actionlint-version input with default 'latest' ([e3c35ac](https://github.com/nics-dp/meta/commit/e3c35ac0a68339d5ba5c200ee6743e87a3d9e7ea))
* **ci:** add checks:write, permissions, fix actionlint install and trivy-iac comment ([2e637e2](https://github.com/nics-dp/meta/commit/2e637e22159a02b25743508bf95b52dd1f9fc780))
* **ci:** add pipefail, scan all Dockerfiles, restrict git URL rewrite ([822bb8a](https://github.com/nics-dp/meta/commit/822bb8af124e6046ba0748ef7e539f5a8dc5ffbd))
* **ci:** address PR review comments ([e8d4f79](https://github.com/nics-dp/meta/commit/e8d4f790fe280902a2462f0111a33162c0ff0100))
* **ci:** address PR review feedback ([334aaa3](https://github.com/nics-dp/meta/commit/334aaa321a7c339b7010829ea4d9df986353a45e))
* **ci:** allow workflow-run access for sarif upload ([7f45f09](https://github.com/nics-dp/meta/commit/7f45f09cc685459e5421c3b0d849fbb70854ea31))
* **ci:** downgrade SBOM format to CycloneDX 1.5 ([8b4ab14](https://github.com/nics-dp/meta/commit/8b4ab14f7bee542956d7719a31c4ab84e6fd0da0))
* **ci:** fix paginate callback in artifacts-comment workflow ([4d6fbdf](https://github.com/nics-dp/meta/commit/4d6fbdfffd346867d2805d2ee4aa0218a03aae18))
* **ci:** fix SARIF upload failures in sbom-source and sbom-image workflows ([f015bfb](https://github.com/nics-dp/meta/commit/f015bfb7ce9a7fccc165705541c9737e8ee91590))
* **ci:** move expressions from run blocks to env blocks ([8a45b64](https://github.com/nics-dp/meta/commit/8a45b64a9a4935ced9368f0130544413d72c1af6))
* **ci:** pass SBOM path via trivy scan-ref ([d70109e](https://github.com/nics-dp/meta/commit/d70109ea0a35d91ae690ad48a59c9d04b97d0235))
* **ci:** Potential fix for pull request finding ([296f804](https://github.com/nics-dp/meta/commit/296f804395692da1b1e98cda813d58f0bc66cac8))
* **ci:** prevent code injection in go-test coverage summary ([72e4f62](https://github.com/nics-dp/meta/commit/72e4f62564fe2c6d999c526d1beb2df6e246a5f0))
* **ci:** remove paginate mapFn to let Octokit auto-unwrap artifacts ([25786be](https://github.com/nics-dp/meta/commit/25786bed16aff2cd6c6ae1b8c7d407f16d9745b9))
* **ci:** resolve CodeQL code injection and shellcheck warnings ([368d0ef](https://github.com/nics-dp/meta/commit/368d0efabbb08352e71d9f2b1303c8dc0af756bb))
* **ci:** revert SBOM format to CycloneDX 1.5 ([07fe309](https://github.com/nics-dp/meta/commit/07fe3091cf730d347b1e09a21fa46232e64e5276))
* **ci:** scan original SBOM instead of parlay-enriched version ([cb2f95a](https://github.com/nics-dp/meta/commit/cb2f95a6e718fb0eef518c3a4cd6123f14576c23))
* disable scope-enum rule in commitlint config ([472c406](https://github.com/nics-dp/meta/commit/472c4065b54ad0333f5ccf006288974ecfde75ec))
* **release:** add id-token permission and harden env_file parsing ([52c27c8](https://github.com/nics-dp/meta/commit/52c27c8e62f7acb5bc4b32c30fafa78d59fbf059))
* **release:** add permissions, restrict URL rewrite, harden env file parsing ([e9eace3](https://github.com/nics-dp/meta/commit/e9eace331f89c0c52610bf70dc5865cd1a2c43d6))
* **release:** address PR [#6](https://github.com/nics-dp/meta/issues/6) review comments ([fdba5ca](https://github.com/nics-dp/meta/commit/fdba5ca48ea256573734d3f79a639b35e4796514))
* **release:** snapshot-safe image tags and harden env_file build_args ([f8fc037](https://github.com/nics-dp/meta/commit/f8fc037a418d7ca89f50f623ff8b3592b9db5766))
* **release:** use GITHUB_ENV for GOPRIVATE and pin tool versions ([ff9270b](https://github.com/nics-dp/meta/commit/ff9270bd8c2232c63e0f61ae088ba9f253a9f6f8))
* replace A && B || C pattern with proper if-then-fi in actionlint workflow ([dd19e4a](https://github.com/nics-dp/meta/commit/dd19e4a3033782fcbf34a802d331961f4a10e873))
* revamp issue templates for dcf project ([5ea62ba](https://github.com/nics-dp/meta/commit/5ea62ba24d98645c7b83204511c3b99d948524bd))
* trigger release template on tag push instead of release event ([531fed0](https://github.com/nics-dp/meta/commit/531fed0a363def517573c849f5e3dc93b8ae19fb))
* **trivy-license:** correct artifact link wording in PR comment ([9bfbada](https://github.com/nics-dp/meta/commit/9bfbada1b2de52c987786f626a1dc2a4ede59122))
* use correct registries for tools in mise ([e7bd647](https://github.com/nics-dp/meta/commit/e7bd647cbb44a624f580aa1db8549cd4e570bce8))
* use dedicated release PAT for release workflows in templates ([aa0ba5e](https://github.com/nics-dp/meta/commit/aa0ba5e3ecd0fd8364386fe3f6f07c68413f6508))
