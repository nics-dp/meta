#!/usr/bin/env python3
"""Checker for Contract markdown files. Stdlib only; self-contained so it can be
copied alone into another repo. Contract bodies are never parsed for headings."""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "0.2.0"

DEFAULT_PHASE_IGNORE = ["docs/**", "*.md", ".github/**"]

_KEY_RE = re.compile(r"^([a-z_][a-z0-9_]*):(?:\s+(.*))?$")


class ImpError(Exception):
    pass


def _unquoted(s: str):
    """Yield (index, char) for each char outside a quoted scalar.

    A quote opens a scalar only at a token start, so an apostrophe inside a plain
    word such as don't stays literal; a backslash escapes inside double quotes."""
    quote, escaped = None, False
    for i, c in enumerate(s):
        if quote:
            if escaped:
                escaped = False
            elif quote == '"' and c == "\\":
                escaped = True
            elif c == quote:
                quote = None
        elif c in "'\"" and (i == 0 or s[i - 1].isspace() or s[i - 1] in ",["):
            quote = c
        else:
            yield i, c


def _strip_comment(s: str) -> str:
    # A '#' starts a comment only outside quotes and at line start or after whitespace.
    for i, c in _unquoted(s):
        if c == "#" and (i == 0 or s[i - 1].isspace()):
            return s[:i].strip()
    return s.strip()


def _split_items(inner: str) -> list[str]:
    cuts = [i for i, c in _unquoted(inner) if c == ","]
    bounds = zip([-1] + cuts, cuts + [len(inner)])
    return [inner[a + 1:b].strip() for a, b in bounds]


def _scalar(v: str) -> str:
    # Double quotes decode \\ and \" to match _unquoted; other escapes and single quotes stay literal.
    if len(v) >= 2 and v[0] == v[-1] == '"':
        return re.sub(r'\\([\\"])', r"\1", v[1:-1])
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1]
    return v


def _value(raw: str, line: str):
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise ImpError(f"unsupported frontmatter line: {line!r}")
        inner = raw[1:-1].strip()
        items = [x for x in _split_items(inner) if x]
        if any(x[0] in "[{" for x in items):
            raise ImpError(f"unsupported frontmatter line: {line!r}")
        return [_scalar(x) for x in items]
    if raw[0] in "{|>&*!":
        raise ImpError(f"unsupported frontmatter line: {line!r}")
    return _scalar(raw)


def parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[0].rstrip() != "---":
        raise ImpError("missing frontmatter: file must start with '---'")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].rstrip() == "---")
    except StopIteration:
        raise ImpError("unterminated frontmatter: no closing '---'") from None

    fm: dict[str, str | list[str]] = {}
    block_key: str | None = None
    for line in lines[1:end]:
        content = _strip_comment(line)
        if not content:
            continue
        if line[0] in " \t":
            if block_key is None or not content.startswith("- "):
                raise ImpError(f"unsupported frontmatter line: {line!r}")
            fm[block_key].append(_scalar(content[2:].strip()))  # type: ignore[union-attr]
            continue
        m = _KEY_RE.match(content)
        if not m:
            raise ImpError(f"unsupported frontmatter line: {line!r}")
        key, raw = m.group(1), m.group(2)
        if key in fm:
            raise ImpError(f"duplicate frontmatter key: {key!r}")
        if raw is None or not raw.strip():
            fm[key] = []
            block_key = key
        else:
            fm[key] = _value(raw.strip(), line)
            block_key = None
    return fm, "\n".join(lines[end + 1:])


@dataclass
class TestPattern:
    __test__ = False  # not a unittest/pytest test class
    glob: str
    regex: re.Pattern


@dataclass
class Config:
    approvals: int = 0
    tests: list[TestPattern] = field(default_factory=list)
    phase_ignore: list[str] = field(default_factory=lambda: list(DEFAULT_PHASE_IGNORE))


def load_config(root: Path) -> Config:
    path = Path(root) / ".imp.toml"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ImpError(f"missing config: {path}") from None
    except (OSError, UnicodeDecodeError) as e:
        raise ImpError(f"cannot read {path}: {e}") from None
    return parse_config(text, str(path))


def base_config(root: Path, base: str) -> Config | None:
    """The base ref's config, or None when the base has no .imp.toml yet.

    Test patterns and phase rules come from the base ref, so a PR cannot loosen the rules it
    is judged by. Without a base config the branch's own config is used."""
    if base.startswith("-"):
        raise ImpError(f"invalid base ref: {base!r}")
    def git(*args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["git", "-C", str(root), *args],
                                  capture_output=True, text=True, encoding="utf-8")
        except OSError as e:
            raise ImpError(f"cannot run git: {e}") from None

    if git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode != 0:
        raise ImpError(f"unknown base ref: {base!r}")
    r = git("show", f"{base}:.imp.toml")
    if r.returncode != 0:
        return None
    return parse_config(r.stdout, f"{base}:.imp.toml")


def parse_config(text: str, source: str) -> Config:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ImpError(f"invalid {source}: {e}") from None

    approvals = data.get("approvals", 0)
    if not isinstance(approvals, int) or isinstance(approvals, bool):
        raise ImpError(f"approvals must be an integer: {approvals!r}")

    phase = data.get("phase", {})
    if not isinstance(phase, dict):
        raise ImpError("phase must be a table")
    ignore = phase.get("ignore", DEFAULT_PHASE_IGNORE)
    if not isinstance(ignore, list) or not all(isinstance(x, str) for x in ignore):
        raise ImpError(f"phase.ignore must be a list of strings: {ignore!r}")

    raw_tests = data.get("tests", [])
    if not isinstance(raw_tests, list) or not all(isinstance(t, dict) for t in raw_tests):
        raise ImpError("tests must be an array of tables")
    tests = []
    for t in raw_tests:
        glob, pat = t.get("glob"), t.get("regex")
        if not isinstance(glob, str) or not isinstance(pat, str):
            raise ImpError(f"[[tests]] entry needs string glob and regex: {t!r}")
        if glob.startswith("/") or ".." in glob.split("/"):
            raise ImpError(f"[[tests]] glob must stay inside the repo: {glob!r}")
        try:
            rx = re.compile(pat)
        except re.error as e:
            raise ImpError(f"invalid regex {pat!r}: {e}") from None
        if rx.groups < 1:
            raise ImpError(f"regex needs a capture group: {pat!r}")
        tests.append(TestPattern(glob, rx))
    return Config(approvals=approvals, tests=tests, phase_ignore=list(ignore))


@dataclass
class Contract:
    id: str
    path: Path
    tests: list[str]
    behaviors: list[str]
    owner: str | None
    body: str


_CONTRACT_DIR = Path("docs") / "contract"
_BEHAVIORS_FILE = "behaviors.md"
_BEHAVIOR_RE = re.compile(r"^\s*-\s+`([^`]+)`\s*[:：]")


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _contract_files(root: Path) -> list[Path]:
    d = Path(root) / _CONTRACT_DIR
    return sorted(p for p in d.glob("*.md") if p.is_file() and p.name != _BEHAVIORS_FILE)


def _load_contract(root: Path, path: Path) -> Contract:
    rel = _rel(root, path)
    try:
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise ImpError(f"{rel}: cannot read: {e}") from None
    except ImpError as e:
        raise ImpError(f"{rel}: {e}") from None
    cid = fm.get("id")
    if not isinstance(cid, str) or not cid:
        raise ImpError(f"{rel}: missing frontmatter 'id'")
    lists = {}
    for key in ("tests", "behaviors"):
        v = fm.get(key, [])
        if not isinstance(v, list):
            raise ImpError(f"{rel}: '{key}' must be a list")
        lists[key] = v
    owner = fm.get("owner")
    if owner is not None and not isinstance(owner, str):
        raise ImpError(f"{rel}: 'owner' must be a string")
    return Contract(cid, path, lists["tests"], lists["behaviors"], owner, body)


def load_contracts(root: Path) -> list[Contract]:
    root = Path(root)
    return [_load_contract(root, p) for p in _contract_files(root)]


def load_behaviors(root: Path) -> dict[str, str]:
    path = Path(root) / _CONTRACT_DIR / _BEHAVIORS_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as e:
        raise ImpError(f"{_rel(Path(root), path)}: cannot read: {e}") from None
    out: dict[str, str] = {}
    group = ""
    for line in text.splitlines():
        if line.startswith("## "):
            group = line[3:].strip()
            continue
        m = _BEHAVIOR_RE.match(line)
        if m:
            bid = m.group(1)
            if bid in out:
                raise ImpError(f"{_rel(Path(root), path)}: duplicate behavior id {bid!r}")
            out[bid] = group
    return out


_WALK_SKIP = {"node_modules", "vendor"}


def _repo_files(root: Path) -> list[str]:
    # Inside git: tracked plus untracked-not-ignored files, which leaves out nested
    # worktrees and checkouts. Outside git: walk, skipping dot, dependency and vendor dirs.
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if r.returncode == 0:
            return [f for f in r.stdout.split("\0") if f]
    except OSError:
        # No git executable: the os.walk below lists the files instead.
        pass
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _WALK_SKIP]
        out += [_rel(root, Path(dirpath) / f) for f in filenames]
    return out


def collect_test_names(root: Path, cfg: Config) -> set[str]:
    root = Path(root)
    names: set[str] = set()
    files = _repo_files(root) if cfg.tests else []
    for pat in cfg.tests:
        for rel in files:
            f = root / rel
            if not _glob_match(pat.glob, rel) or not f.is_file():
                continue
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                m = pat.regex.search(line)
                if m:
                    names.add(m.group(1))
    return names


def validate(root: Path, cfg: Config) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    try:
        behaviors = load_behaviors(root)
    except ImpError as e:
        errors.append(str(e))
        behaviors = {}
    tests = collect_test_names(root, cfg)
    for path in _contract_files(root):
        rel = _rel(root, path)
        try:
            c = _load_contract(root, path)
        except ImpError as e:
            errors.append(str(e))
            continue
        if c.id != path.stem:
            errors.append(f"{rel}: id {c.id!r} does not match filename {path.stem!r}")
        errors += [f"{rel}: test not found: {t}" for t in c.tests if t not in tests]
        errors += [f"{rel}: unknown behavior: {b}" for b in c.behaviors if b not in behaviors]
    return errors


def _glob_match(pattern: str, path: str) -> bool:
    # '**' crosses directories, '*' and '?' stay within one segment, and a
    # pattern without '/' is matched against the basename at any depth.
    if "/" not in pattern:
        path = path.rsplit("/", 1)[-1]
    return _glob_regex(pattern).fullmatch(path) is not None


@functools.lru_cache(maxsize=None)
def _glob_regex(pattern: str) -> re.Pattern:
    # Runs of '*' and of '**/' collapse first: adjacent '.*' groups backtrack exponentially.
    pattern = re.sub(r"(?:\*\*/)+", "**/", re.sub(r"\*{3,}", "**", pattern))
    pattern = re.sub(r"(?:\*\*/)+\*\*(?!/)", "**", pattern)
    rx, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            rx += ".*"
            i += 2
        elif pattern[i] == "*":
            rx += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            rx += "[^/]"
            i += 1
        else:
            rx += re.escape(pattern[i])
            i += 1
    return re.compile(rx)


def _changed_files(root: Path, base: str) -> list[str]:
    if base.startswith("-"):
        raise ImpError(f"invalid base ref: {base!r}")
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "--relative", "-z", f"{base}...HEAD"],
            capture_output=True, text=True, encoding="utf-8",
        )
    except OSError as e:
        raise ImpError(f"cannot run git: {e}") from None
    if r.returncode != 0:
        raise ImpError(f"git diff {base}...HEAD failed: {r.stderr.strip()}")
    return [f for f in r.stdout.split("\0") if f]


def phase_errors(root: Path, cfg: Config, base: str) -> list[str]:
    root = Path(root)
    changed = _changed_files(root, base)
    if all(any(_glob_match(g, f) for g in cfg.phase_ignore) for f in changed):
        return []  # contract phase: only contracts/docs changed
    errors: list[str] = []
    for f in sorted(changed):
        path = root / f
        if (
            Path(f).parent != _CONTRACT_DIR
            or path.suffix != ".md"
            or path.name == _BEHAVIORS_FILE
            or not path.is_file()
        ):
            continue
        try:
            c = _load_contract(root, path)
        except ImpError as e:
            errors.append(str(e))
            continue
        if not c.owner and not c.tests:
            errors.append(f"{f}: tests is empty but this PR changes code")
    return errors


def coverage(contracts: list[Contract], behaviors: dict[str, str]) -> dict:
    local = [c for c in contracts if not c.owner]
    claimed = {b for c in local for b in c.behaviors}
    groups: dict[str, dict[str, int]] = {}
    for bid, group in behaviors.items():
        g = groups.setdefault(group, {"total": 0, "covered": 0})
        g["total"] += 1
        g["covered"] += bid in claimed
    return {
        "behaviors": {
            "total": len(behaviors),
            "covered": sum(g["covered"] for g in groups.values()),
            "groups": groups,
        },
        "contracts": {"total": len(local), "with_tests": sum(1 for c in local if c.tests)},
        "without_behaviors": [c.id for c in local if not c.behaviors],
    }


def _ratio(covered: int, total: int) -> str:
    pct = "-" if total == 0 else f"{covered * 100 // total}%"
    return f"{covered}/{total} ({pct})"


def format_coverage(cov: dict) -> str:
    lines = [f"{name}: {_ratio(g['covered'], g['total'])}" for name, g in cov["behaviors"]["groups"].items()]
    lines.append(f"behaviors: {_ratio(cov['behaviors']['covered'], cov['behaviors']['total'])}")
    lines.append(f"contracts with tests: {_ratio(cov['contracts']['with_tests'], cov['contracts']['total'])}")
    if cov["without_behaviors"]:
        lines.append("contracts without behaviors: " + ", ".join(cov["without_behaviors"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="imp_check.py", description="Check Contract files and report behavior coverage.")
    ap.add_argument("--root", default=".", help="repo root containing .imp.toml (default: .)")
    ap.add_argument("--base", help="git ref; judge with its .imp.toml and check the contract phase against base...HEAD")
    ap.add_argument("--json", action="store_true", help="print coverage as JSON")
    ap.add_argument("--version", action="store_true", help="print the checker version and exit")
    args = ap.parse_args(argv)
    if args.version:
        print(VERSION)
        return 0
    root = Path(args.root)
    try:
        cfg = load_config(root)
        # With --base, the base branch's config judges the PR: test patterns and phase rules
        # come from it, so a PR cannot loosen the rules it is checked against.
        base_cfg = base_config(root, args.base) if args.base else None
        errors = validate(root, base_cfg if base_cfg is not None else cfg)
        if base_cfg is not None:
            errors += phase_errors(root, base_cfg, args.base)
        if not errors:
            cov = coverage(load_contracts(root), load_behaviors(root))
    except ImpError as e:
        print(e, file=sys.stderr)
        return 1
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print(json.dumps(cov, ensure_ascii=False, indent=2) if args.json else format_coverage(cov))
    return 0


if __name__ == "__main__":
    sys.exit(main())
