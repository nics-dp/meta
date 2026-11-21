#!/usr/bin/env python3
"""Check every repository's dependency-graph SBOM against a license denylist.

Reads each repository's SBOM from the GitHub dependency graph through `gh api`
(GH_TOKEN must be able to read the repositories' contents) and evaluates each
package's `licenseConcluded` SPDX expression: an `OR` passes when any operand is
allowed, an `AND` only when every operand is, and `X WITH exception` follows X.
A deprecated bare id such as GPL-2.0 counts as its "-only" form; "+" and
"-or-later" stay distinct, so GPL-2.0-or-later passes a GPL-2.0-only entry.
Identifiers match without regard to case (SPDX 2.3 Annex D.2), on both the
expression and the deny entries. Unknown values (NOASSERTION, empty,
LicenseRef-*) are not denied.

This is plain SPDX semantics, which differs from dependency-review-action's
satisfiesAny: the action rejects a dependency only when one OR alternative is a
single license matching an entry (so it rejects "MIT OR GPL-2.0-only" but not
"MIT AND GPL-2.0-only"), and it treats "-or-later" as matching "-only".

Writes a Markdown report and prints `hits=<n>` and `skipped=<n>` lines for
$GITHUB_OUTPUT. A repository whose SBOM cannot be read is listed as skipped,
not treated as clean.

Usage:
  license-inventory.py --owner ORG --deny "A,B" --report out.md [--repos r1,r2]
Without --repos the repositories come from /installation/repositories, which
requires a GitHub App installation token.
"""

import argparse
import json
import re
import subprocess
import sys

TOKEN_RE = re.compile(r"\(|\)|[^\s()]+")


def parse_list(value):
    return {item.strip() for item in value.split(",") if item.strip()}


def allowed(expression, deny):
    """Return False only when every way to satisfy the expression uses a denied license."""
    tokens = TOKEN_RE.findall(expression or "")
    if not tokens:
        return True
    denied = {item.casefold() for item in deny}
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def primary():
        tok = take()
        if tok == "(":
            value = disjunction()
            if peek() == ")":
                take()
            return value
        folded = tok.casefold()
        value = folded not in denied and f"{folded}-only" not in denied
        if peek() is not None and peek().upper() == "WITH":
            take()
            if peek() is not None:
                take()
        return value

    def conjunction():
        value = primary()
        while peek() is not None and peek().upper() == "AND":
            take()
            value = primary() and value
        return value

    def disjunction():
        value = conjunction()
        while peek() is not None and peek().upper() == "OR":
            take()
            value = conjunction() or value
        return value

    try:
        return disjunction()
    except IndexError:
        # A truncated expression is reported as allowed rather than crashing the
        # whole inventory; the raw value is still visible in the dependency graph.
        return True


def gh_json(path, paginate=False):
    cmd = ["gh", "api", path]
    if paginate:
        cmd[2:2] = ["--paginate", "--slurp"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None, (result.stderr.strip().splitlines() or ["gh api failed"])[-1]
    return json.loads(result.stdout), None


def list_repositories(owner):
    pages, err = gh_json("/installation/repositories", paginate=True)
    if err:
        sys.exit(f"cannot list installation repositories: {err}")
    names = []
    for page in pages:
        for repo in page.get("repositories", []):
            if repo["owner"]["login"] == owner and not repo.get("archived"):
                names.append(repo["name"])
    return sorted(names)


def scan(owner, repos, deny):
    hits, skipped = [], []
    for repo in repos:
        data, err = gh_json(f"/repos/{owner}/{repo}/dependency-graph/sbom")
        if err:
            skipped.append((repo, err))
            continue
        for pkg in data.get("sbom", {}).get("packages", []):
            license_expr = pkg.get("licenseConcluded") or ""
            if not allowed(license_expr, deny):
                hits.append((repo, pkg.get("name", ""), pkg.get("versionInfo", ""), license_expr))
    return hits, skipped


def report(deny, repos, hits, skipped):
    lines = [
        "每週授權盤點:比對各 repo dependency graph SBOM 的 `licenseConcluded` 與",
        "`.github/workflows/dependency-review.yml` 的 `deny_licenses` 預設值加上",
        "`.github/workflows/license-inventory.yml` 的 `INVENTORY_ONLY_DENY`。",
        "",
        f"- 黑名單:{', '.join(f'`{d}`' for d in sorted(deny))}",
        f"- 掃描 repo 數:{len(repos) - len(skipped)} / {len(repos)}",
        "",
    ]
    if hits:
        lines += ["## 命中", "", "| Repo | 套件 | 版本 | 授權 |", "|---|---|---|---|"]
        lines += [f"| {r} | `{n}` | {v} | `{l}` |" for r, n, v, l in hits]
        lines.append("")
    else:
        lines += ["沒有任何依賴命中黑名單。", ""]
    if skipped:
        lines += ["## 無法讀取 SBOM", "", "| Repo | 原因 |", "|---|---|"]
        lines += [f"| {r} | {e} |" for r, e in skipped]
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--deny", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--repos", default="")
    args = parser.parse_args()

    deny = parse_list(args.deny)
    if not deny:
        sys.exit("empty denylist")
    repos = sorted(parse_list(args.repos)) or list_repositories(args.owner)
    hits, skipped = scan(args.owner, repos, deny)
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(report(deny, repos, hits, skipped))
    print(f"hits={len(hits)}")
    print(f"skipped={len(skipped)}")


if __name__ == "__main__":
    main()
