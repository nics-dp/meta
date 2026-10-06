#!/usr/bin/env python3
"""Print a mise.toml whose [tools] is the union of the atoms' `#MISE tools={...}` headers.

Usage: mise-tools-toml.py <tasks-dir> <go-version> [<atom>,<atom>,...]

With no atom list or an empty one every atom counts; otherwise only the named atoms (task names
such as `go:lint-check` or `iac:img:hadolint`) do, and a name that matches no atom, or an empty
item such as in `a,,b` or `a,`, is an error. An atom is a file with a `#MISE hide=true`
header, so a lib/ helper is not one. A named atom with no `#MISE tools=` header adds no tools,
so the image can hold only Go; with every atom counted, no header at all is an error, which
catches a wrong tasks dir.

Each header value is parsed as a TOML inline table. A tool pinned to different versions by
two atoms is an error that lists both pins, so the image never silently picks one of them.
The Go toolchain comes from the caller because no atom declares it.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

HEADER = "#MISE tools="
GO_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
ATOM = re.compile(r"[a-z0-9_-]+(:[a-z0-9_-]+)+")


def is_atom(path: Path) -> bool:
    return path.is_file() and "#MISE hide=true" in path.read_text(encoding="utf-8").splitlines()


def atom_paths(tasks_dir: Path, atoms: list[str]) -> list[Path]:
    if not atoms:
        return sorted(p for p in tasks_dir.rglob("*") if is_atom(p))
    paths = []
    for atom in atoms:
        if not ATOM.fullmatch(atom):
            sys.exit(f"error: {atom!r} is not an atom task name")
        path = tasks_dir.joinpath(*atom.split(":"))
        if not is_atom(path):
            sys.exit(f"error: no atom {atom} under {tasks_dir}")
        paths.append(path)
    return sorted(set(paths))


def collect(tasks_dir: Path, atoms: list[str]) -> dict[str, tuple[str, str]]:
    tools: dict[str, tuple[str, str]] = {}
    conflicts = []
    for path in atom_paths(tasks_dir, atoms):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith(HEADER):
                continue
            rel = path.relative_to(tasks_dir).as_posix()
            table = tomllib.loads("tools = " + line[len(HEADER):])["tools"]
            for name, version in table.items():
                if not isinstance(version, str):
                    sys.exit(f"error: {rel}: {name} is not a plain version string")
                seen = tools.setdefault(name, (version, rel))
                if seen[0] != version:
                    conflicts.append(f"{name}: {seen[0]} ({seen[1]}) vs {version} ({rel})")
    if conflicts:
        sys.exit("error: atoms pin the same tool to different versions:\n  " + "\n  ".join(conflicts))
    return tools


def main() -> None:
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__.strip().splitlines()[2])
    tasks_dir, go_version = Path(sys.argv[1]), sys.argv[2]
    atoms = sys.argv[3].split(",") if len(sys.argv) == 4 and sys.argv[3] else []
    if not GO_VERSION.fullmatch(go_version):
        sys.exit(f"error: go version {go_version!r} is not of the form X.Y.Z")
    tools = collect(tasks_dir, atoms)
    if not tools and not atoms:
        sys.exit(f"error: no {HEADER} header under {tasks_dir}")
    if "go" in tools and tools["go"][0] != go_version:
        sys.exit(f"error: go: {tools['go'][0]} ({tools['go'][1]}) vs {go_version} (go_version input)")
    tools["go"] = (go_version, "go_version input")
    print("[tools]")
    # JSON string escaping is valid TOML basic-string syntax for these keys and values.
    for name in sorted(tools):
        print(f"{json.dumps(name)} = {json.dumps(tools[name][0])}")


if __name__ == "__main__":
    main()
