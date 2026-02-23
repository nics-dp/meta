---

<details>
<summary>Verifying the artifacts</summary>

First, download the [`checksums.txt` file](https://github.com/charmbracelet/{{.ProjectName}}/releases/download/{{.Tag}}/checksums.txt) and the [`checksums.txt.sigstore.json` file](https://github.com/charmbracelet/{{.ProjectName}}/releases/download/{{.Tag}}/checksums.txt.sigstore.json) files, for example, with `wget`:

```bash
wget 'https://github.com/nics-dp/{{.ProjectName}}/releases/download/{{.Tag}}/checksums.txt'
wget 'https://github.com/nics-dp/{{.ProjectName}}/releases/download/{{.Tag}}/checksums.txt.sigstore.json'
```

Then, verify it using [`cosign`](https://github.com/sigstore/cosign):

```bash
cosign verify-blob \
  --certificate-identity 'https://github.com/nics-dp/meta/.github/workflows/goreleaser.yml@refs/heads/main' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  --bundle 'checksums.txt.sigstore.json' \
  ./checksums.txt
```

If the output is `Verified OK`, you can safely use it to verify the checksums of other artifacts you downloaded from the release using `sha256sum`:

```bash
sha256sum --ignore-missing -c checksums.txt
```

Done! You artifacts are now verified!

</details>
