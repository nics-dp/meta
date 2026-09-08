# Semgrep suppression fixtures

Run from the repository root (Python standard library only; no scanner or upload):

```sh
python3 -B -m unittest discover -s .github/tests -p 'test_*.py'
```

The tests extract and execute the actual inline Python from
`security-sarif.yml`, with real files in a temporary directory and an empty
inherited environment. They cover raw producer compatibility, conservative
suppression handling, multiple runs, complete preservation of retained findings,
and the existing read/write/replace failure behavior.

## Input contract

The filter reads the local `semgrep.sarif` produced by `semgrep scan`, before
upload. It removes a result only when `suppressions` is a nonempty list and every
entry is an object with `kind: inSource`, absent or `accepted` status, and no
`state` field. Rejected, under-review, unknown kind/status, external, malformed
entries/containers, and mixed entries remain intact. This checks suppression
eligibility, not the entire SARIF schema.

`state` is deliberately not an alias for `status`. The real GitHub API export
for dcf-platform analysis 1715924510 contains `[{"state":"accepted"}]`, but
[the API returns a subset of uploaded data with additional GitHub properties](https://docs.github.com/en/rest/code-scanning/code-scanning#get-a-code-scanning-analysis-for-a-repository),
not the original scanner file. Tests cover that shape synthetically; the private
historical export is not committed here. State-only and state/status combinations
are preserved, not silently interpreted as approved in-source suppressions.

## Producer provenance

These two SARIF files are untouched local macOS arm64 Semgrep OSS outputs,
generated on 2026-09-08 with versions 1.176.0 and 1.176.1. Both use the synthetic
`cookie-inline.go.txt` (scanned as `cookie-inline.go`), with one precisely
suppressed cookie and one otherwise identical unsuppressed cookie. Each cookie
uses a caller-provided `secure` boolean and preserves HttpOnly/SameSite.

The public rule is pinned to
[semgrep-rules commit 40b8c63f75dc7c22c8a77482d73bfb864b146f7e](https://github.com/semgrep/semgrep-rules/blob/40b8c63f75dc7c22c8a77482d73bfb864b146f7e/go/lang/security/audit/net/cookie-missing-secure.yaml).
The only rule change was expanding its ID from `cookie-missing-secure` to
`go.lang.security.audit.net.cookie-missing-secure.cookie-missing-secure`.

To recreate `rule.yaml`, run the following from the repository root. It downloads
the pinned public rule into a new temporary directory, checks the upstream bytes,
replaces exactly one ID line without reformatting YAML, and checks the resulting
local-rule SHA256 before writing it. Keep this shell open for the scan below.

```sh
set -eu
fixture_dir="$PWD/.github/tests/fixtures/semgrep"
repro_dir="$(mktemp -d "${TMPDIR:-/tmp}/semgrep-fixture.XXXXXXXX")"
cp "$fixture_dir/cookie-inline.go.txt" "$repro_dir/cookie-inline.go"
cd "$repro_dir"
curl -q --fail --silent --show-error --location --max-time 60 \
  --proto '=https' --proto-redir '=https' \
  'https://raw.githubusercontent.com/semgrep/semgrep-rules/40b8c63f75dc7c22c8a77482d73bfb864b146f7e/go/lang/security/audit/net/cookie-missing-secure.yaml' \
  --output rule.upstream.yaml
python3 - <<'PY'
import hashlib
from pathlib import Path

upstream = Path("rule.upstream.yaml").read_bytes()
if hashlib.sha256(upstream).hexdigest() != "1b94d28f69c35ef81b92b0a8a845dbb8c26cd1174ab627d8abcd7e292a5d4d0e":
    raise SystemExit("upstream rule SHA256 mismatch")
old = b"- id: cookie-missing-secure\n"
new = b"- id: go.lang.security.audit.net.cookie-missing-secure.cookie-missing-secure\n"
if upstream.count(old) != 1:
    raise SystemExit("expected exactly one upstream rule ID line")
local = upstream.replace(old, new, 1)
digest = hashlib.sha256(local).hexdigest()
if digest != "3b0df223535ee9912a0febfef7e57a799fe664596417d9363c5573bef9b0e584":
    raise SystemExit("local rule SHA256 mismatch")
Path("rule.yaml").write_bytes(local)
print(f"rule.yaml SHA256: {digest}")
PY
```

Each version was installed into a separate temporary virtual environment. Scans
used an empty inherited environment, isolated HOME/cache, and a macOS sandbox
denying network access and reads under the user's home directory. From the
reproduction directory above, with `$semgrep` pointing to that version's executable
by absolute path and `$output` to a new local output file:

```sh
"$semgrep" scan --enable-nosem --config rule.yaml \
  --no-rewrite-rule-ids --no-git-ignore --metrics=off --disable-version-check \
  --oss-only --jobs=1 --sarif --output "$output" -- cookie-inline.go
```

Both scans succeeded: CLI findings = 1, raw SARIF results = 2, exactly one
`suppressions: [{"kind":"inSource"}]`, no `status` or `state`. The original filter
and the corrected filter both remove that result and preserve the ordinary
finding and all other SARIF data unchanged. The `.txt` suffix keeps the synthetic
Go source out of normal repository language scans; the preparation block copies
it to `cookie-inline.go` only in the temporary reproduction directory.

After inspecting the output, return with `cd "$fixture_dir"` and remove only the
temporary directory named by `$repro_dir`.

| File | SHA256 |
| --- | --- |
| `cookie-inline.go.txt` | `048f1e9e1cff200f08ded49560273f23fc369f5f5648308d08b6cc0535a6f74d` |
| `semgrep-1.176.0.sarif` | `77e3ef7cba15aeb98df090fb44f16514fd0dc86da4a690a8d9b25c7971ac101f` |
| `semgrep-1.176.1.sarif` | `7df760663121c52c2f4ddde015d8c64d993700a20ac32386f095ba774542aeaa` |
| Upstream rule | `1b94d28f69c35ef81b92b0a8a845dbb8c26cd1174ab627d8abcd7e292a5d4d0e` |
| Local rule with expanded ID | `3b0df223535ee9912a0febfef7e57a799fe664596417d9363c5573bef9b0e584` |

## Historical scope

[meta issue 366](https://github.com/nics-dp/meta/issues/366) and
[PR 367](https://github.com/nics-dp/meta/pull/367) introduced this filter to remove
nosemgrep noise. Historical runs 33711565413 and 34091598331 reported zero CLI
findings, while their GitHub `semgrep` analyses went from one result to zero.
The cookie source blob was unchanged. The alert's earlier manual dismissal is a
separate event, not evidence of filter-driven dismissal.

These new fixtures establish producer behavior for the two historical version
numbers. They do not recover missing historical raw files, prove historical
registry-rule identity or Linux output, or test GitHub processing/alert lifecycle.
Version 1.176.0's tagged OCaml formatter also emits inSource without status;
1.176.1's exact OCaml source-to-binary revision was unavailable, so that version's
evidence is its actual installed producer output. The workflow remains unpinned
and this change does not claim compatibility with all future Semgrep formats.
