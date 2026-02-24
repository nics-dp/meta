# meta

This repo contains nics-dp's meta configuration files:

- GoReleaser configurations
- GitHub Actions workflows
- golangci-lint config
- Dependabot config

## Related docs

- [GitHub: Reusing Workflows](https://docs.github.com/en/actions/learn-github-actions/reusing-workflows)
- [GoReleaser](https://goreleaser.com/)

## GoReleaser Configs

Available profiles (GoReleaser OSS v2):

| Config | Use Case |
|---|---|
| `goreleaser-full.yml` | CLI with Docker (docker.io + ghcr.io, amd64/arm64/armv7), macOS signing & notarization |
| `goreleaser-simple.yml` | Pure binary release, no Docker, macOS signing & notarization |
| `goreleaser-lab.yml` | Server-only (linux/amd64, ghcr.io only) |
| `goreleaser-lib.yml` | Library-only (skip build, changelog + GitHub release) |

Copy the relevant config into your repo as `.goreleaser.yml`, or use it as a reference.

## Reusable Workflows

All reusable workflows are called via `uses:`. Optional inputs are shown as comments.

### goreleaser.yml

Full release pipeline: Go build, Docker multi-arch, cosign signing, SBOM, dual-registry push. Optionally signs and notarizes macOS binaries.

```yaml
# .github/workflows/goreleaser.yml
name: goreleaser

on:
  push:
    tags:
      - v*.*.*

concurrency:
  group: goreleaser
  cancel-in-progress: true

jobs:
  goreleaser:
    uses: nics-dp/meta/.github/workflows/goreleaser.yml@main
    secrets:
      docker_username: ${{ secrets.DOCKERHUB_USERNAME }}
      docker_token: ${{ secrets.DOCKERHUB_TOKEN }}
      gh_pat: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
      # macOS signing & notarization (optional)
      macos_sign_p12: ${{ secrets.MACOS_SIGN_P12 }}
      macos_sign_password: ${{ secrets.MACOS_SIGN_PASSWORD }}
      macos_notary_key: ${{ secrets.MACOS_NOTARY_KEY }}
      macos_notary_key_id: ${{ secrets.MACOS_NOTARY_KEY_ID }}
      macos_notary_issuer_id: ${{ secrets.MACOS_NOTARY_ISSUER_ID }}
    # with:
    #   go_version: stable                # Go version (default: stable)
    #   goreleaser_version: latest         # GoReleaser version (default: latest)
    #   upload_artifact: true              # Upload dist as artifact (default: true)
    #   lfs: false                         # Download Git-LFS files (default: false)
    #   macos_sign_entitlements: ""        # Path to entitlements file (optional)
```

### build.yml

Build + test matrix (ubuntu/macos/windows), govulncheck, auto-merge dependabot PRs.

```yaml
# .github/workflows/build.yml
name: build

on: [push, pull_request]

jobs:
  build:
    uses: nics-dp/meta/.github/workflows/build.yml@main
    secrets:
      gh_pat: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
    # with:
    #   go-version: stable      # Go version (default: stable)
    #   go-version-file: ""     # Path to go.mod for version detection
    #   working-directory: ""   # Working directory for go commands
```

### snapshot.yml

GoReleaser snapshot build (no publish), uploads artifacts.

```yaml
# .github/workflows/snapshot.yml
name: snapshot

on: [push, pull_request]

jobs:
  snapshot:
    uses: nics-dp/meta/.github/workflows/snapshot.yml@main
    # secrets:
    #   gh_pat: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
    # with:
    #   go_version: "^1"       # Go version (default: ^1)
    #   upload_artifact: true  # Upload dist as artifact (default: true)
```

### lint.yml

golangci-lint across OS matrix (ubuntu/macos/windows). Automatically fetches `golangci.yml` from this meta repo.

```yaml
# .github/workflows/lint.yml
name: lint

on: [push, pull_request]

jobs:
  lint:
    uses: nics-dp/meta/.github/workflows/lint.yml@main
    # with:
    #   directory: ""          # Subdirectory to lint
    #   golangci_path: ""      # Custom path to golangci.yml
    #   golangci_version: v2.4 # golangci-lint version (default: v2.4)
    #   timeout: 5m            # Lint timeout (default: 5m)
```

### govulncheck.yml

Go vulnerability scanning.

```yaml
# .github/workflows/govulncheck.yml
name: govulncheck

on: [push, pull_request]

jobs:
  govulncheck:
    uses: nics-dp/meta/.github/workflows/govulncheck.yml@main
    # secrets:
    #   gh_pat: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
    # with:
    #   go-version: stable  # Go version (default: stable)
    #   cache: true          # Enable Go module cache (default: true)
    #   run: ""              # Extra command to run before scan
```

### ruleguard.yml

Go ruleguard static analysis using [dgryski/semgrep-go](https://github.com/dgryski/semgrep-go) rules.

```yaml
# .github/workflows/ruleguard.yml
name: ruleguard

on: [push, pull_request]

jobs:
  ruleguard:
    uses: nics-dp/meta/.github/workflows/ruleguard.yml@main
    # secrets:
    #   gh_pat: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
    # with:
    #   go-version: stable  # Go version (default: stable)
    #   cache: true          # Enable Go module cache (default: true)
    #   args: ""             # Extra args for ruleguard
    #   run: ""              # Extra command to run before scan
```

### semgrep.yml

Semgrep static analysis using [dgryski/semgrep-go](https://github.com/dgryski/semgrep-go) rules.

```yaml
# .github/workflows/semgrep.yml
name: semgrep

on: [push, pull_request]

jobs:
  semgrep:
    uses: nics-dp/meta/.github/workflows/semgrep.yml@main
    # secrets:
    #   gh_pat: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
```

### pr-comment.yml

Posts artifact download links as comments on PRs after a successful build. Must be triggered by `workflow_run`.

```yaml
# .github/workflows/pr-comment.yml
name: pr-comment

on:
  workflow_run:
    workflows: [build]
    types: [completed]

jobs:
  pr-comment:
    uses: nics-dp/meta/.github/workflows/pr-comment.yml@main
```

### lint-sync.yml

Syncs `golangci.yml` from this meta repo into the calling repo as `.golangci.yml` via PR.

```yaml
# .github/workflows/lint-sync.yml
name: lint-sync

on:
  workflow_dispatch:

jobs:
  lint-sync:
    uses: nics-dp/meta/.github/workflows/lint-sync.yml@main
```

### dependabot-sync.yml

Syncs Dependabot config from this meta repo into a target repo via PR.

```yaml
# .github/workflows/dependabot-sync.yml
name: dependabot-sync

on:
  workflow_dispatch:
    inputs:
      repo_name:
        description: The repository name, without the org prefix.
        required: true
        type: string

jobs:
  dependabot-sync:
    uses: nics-dp/meta/.github/workflows/dependabot-sync.yml@main
    with:
      repo_name: ${{ inputs.repo_name }}
    secrets:
      gh_token: ${{ secrets.PERSONAL_ACCESS_TOKEN }}
```

## macOS Signing & Notarization

`goreleaser-full.yml` and `goreleaser-simple.yml` support macOS code signing and notarization via the cross-platform method ([anchore/quill](https://github.com/anchore/quill)). This runs on any CI runner (no macOS runner required) and works with GoReleaser OSS.

Signing is conditionally enabled — it activates only when `MACOS_SIGN_P12` is set. Repos without the secrets configured will skip signing.

### Required secrets

| Secret | Description |
|---|---|
| `MACOS_SIGN_P12` | Base64-encoded `.p12` certificate (Developer ID Application) |
| `MACOS_SIGN_PASSWORD` | Password for the `.p12` certificate |
| `MACOS_NOTARY_KEY` | Base64-encoded `.p8` App Store Connect API key |
| `MACOS_NOTARY_KEY_ID` | Key ID of the `.p8` key |
| `MACOS_NOTARY_ISSUER_ID` | Issuer UUID from App Store Connect |

To base64-encode your files:

```bash
base64 -w0 < Certificates.p12
base64 -w0 < ApiKey_AAABBBCCC.p8
```

Optionally, pass `macos_sign_entitlements` as a workflow input to specify a path to an entitlements file.

## Standalone Workflows

These workflows are not reusable. Copy them into your repo directly.

### notify-google-chat.yml

Sends notifications to Google Chat on PR, push, and release events. Requires `GOOGLE_CHAT_WEBHOOK` secret.

```yaml
# Copy .github/workflows/notify-google-chat.yml into your repo.
# Set the GOOGLE_CHAT_WEBHOOK secret in your repo settings.
```

### goreleaser-deprecation-check.yml

Validates goreleaser config files on push/PR. Runs on this meta repo only.
