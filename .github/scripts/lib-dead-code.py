#!/usr/bin/env python3
"""Report library functions and packages that no consumer reaches.

A library such as libdcf or ZenQuery has no main package, so deadcode run on it
alone calls every exported function unused. This script answers the question
across repositories instead: it clones every readable repository that has a
root go.mod (its `dev` branch, or the default branch when there is no `dev`),
joins the library modules and every module that requires one into a go.work,
and runs deadcode once per consumer module in workspace mode, so each consumer
compiles against the library's current source rather than its pinned version.

Each consumer runs twice: a production build rooted at its main packages, and a
`-tags <test tags> -test` build rooted at its tests as well, since a library
helper used only by consumer tests is still used. A library function is
reported only when every successful run either did not compile its file (its
package unloaded, or the file excluded by a build tag) or found the function
unreachable. A library package that no run loaded is
reported as a whole. A run that fails to load (a consumer that does not compile
against the library's current source, for instance) is listed as not analysed;
what only that consumer uses then shows up as unused, so the report says so.

The library's own modules (its tests, examples and nested modules) are not
consumers. Generated files are left out, as deadcode does by default.

Writes a Markdown report and prints `functions=<n>`, `packages=<n>` and
`skipped=<n>` lines for $GITHUB_OUTPUT.

Usage:
  lib-dead-code.py --owner ORG --libs MOD1,MOD2 --work DIR --report out.md
                   [--repos r1,r2] [--deadcode PATH] [--test-tags test]
Without --repos the repositories come from /installation/repositories, which
requires a GitHub App installation token.
"""

import argparse
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

SKIP_DIRS = {"vendor", "node_modules", "testdata", ".git", ".worktree", ".worktrees"}
# A GitHub issue body holds at most 65536 characters.
BODY_LIMIT = 60000


def parse_list(value):
    return [v.strip() for v in value.split(",") if v.strip()]


def gh(args):
    result = subprocess.run(
        ["gh", "api", *args], check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        return None, (result.stderr.strip().splitlines() or ["gh api failed"])[-1]
    return result.stdout, None


def not_found(err):
    """True only for a definite absence; rate limits and 5xx are not one."""
    return err is not None and err.endswith("(HTTP 404)")


def list_repositories(owner):
    out, err = gh(["--paginate", "--slurp", "/installation/repositories"])
    if err:
        sys.exit(f"cannot list installation repositories: {err}")
    names = []
    for page in json.loads(out):
        for repo in page.get("repositories", []):
            if repo["owner"]["login"] == owner and not repo.get("archived"):
                names.append(repo["name"])
    return sorted(names)


def git_auth():
    """git -c options that send GH_TOKEN without writing it to .git/config."""
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        return []  # local run: the user's own git credentials
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}"]


def fetch(owner, repos, src):
    """Clone each repository with a root go.mod; return {repo: sha} and skips.

    A git checkout, not the GitHub source archive: repositories mark tests and
    non-code assets export-ignore in .gitattributes, so the archive does not
    build.
    """
    fetched, skipped = {}, []
    for repo in repos:
        ref = "dev"
        _, err = gh([f"/repos/{owner}/{repo}/branches/dev", "--silent"])
        if err and not not_found(err):
            skipped.append((repo, err))
            continue
        if err:
            out, err = gh([f"/repos/{owner}/{repo}", "--jq", ".default_branch"])
            if err:
                skipped.append((repo, err))
                continue
            ref = out.strip()
        _, err = gh([f"/repos/{owner}/{repo}/contents/go.mod?ref={ref}", "--silent"])
        if not_found(err):
            continue  # no root go.mod (or an empty repository): not a Go module repository
        if err:
            skipped.append((repo, err))
            continue
        dest = src / repo
        clone = subprocess.run(
            [
                "git",
                *git_auth(),
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                ref,
                f"https://github.com/{owner}/{repo}.git",
                str(dest),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if clone.returncode != 0:
            skipped.append((repo, last_error(clone)))
            continue
        sha = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        fetched[repo] = sha
    return fetched, skipped


def go_version(text):
    """'1.27.4', '1.27' or 'go1.27.4' as a comparable tuple; () when unreadable."""
    match = re.fullmatch(r"(?:go)?(\d+(?:\.\d+)*)", text.strip())
    return tuple(int(n) for n in match.group(1).split(".")) if match else ()


def version_text(version):
    return ".".join(map(str, version))


def read_go_mod(path):
    """Return (module path, required module paths, go line, toolchain line)."""
    module, requires, in_block = "", set(), False
    go, toolchain = (), ()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if in_block:
            if line == ")":
                in_block = False
            else:
                requires.add(line.split()[0].strip('"'))
        elif line.startswith("module "):
            module = line.split()[1].strip('"')
        elif line == "require (":
            in_block = True
        elif line.startswith("require "):
            requires.add(line.split()[1].strip('"'))
        elif line.startswith("go "):
            go = go_version(line.split()[1])
        elif line.startswith("toolchain "):
            toolchain = go_version(line.split()[1])
    return module, requires, go, toolchain


def find_modules(src):
    """Map each module directory under src to read_go_mod's tuple."""
    mods = {}
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if "go.mod" in filenames:
            mods[pathlib.Path(dirpath)] = read_go_mod(pathlib.Path(dirpath) / "go.mod")
    return mods


def plan(mods, src, libs):
    """Split modules into library modules and consumer modules.

    Returns ({lib path: dir}, {consumer path: dir}, {lib repo dir names}).
    Modules inside a library's repository are neither: they are the library's
    own tests and examples.
    """
    lib_dirs = {mod[0]: d for d, mod in mods.items() if mod[0] in libs}
    lib_repos = {d.relative_to(src).parts[0] for d in lib_dirs.values()}
    consumers = {}
    for d, (path, requires, *_) in sorted(mods.items()):
        if d.relative_to(src).parts[0] in lib_repos:
            continue
        if requires & set(libs):
            consumers.setdefault(path, d)
    return lib_dirs, consumers, lib_repos


def workspace_versions(mods, dirs):
    """The go.work go line and toolchain: the highest among the member modules.

    go.work must list a go version no lower than any member's, and the toolchain
    is the newest any member pins, so `go` (GOTOOLCHAIN=auto) and deadcode's
    type checker both understand every member's source.
    """
    go = max((mods[d][2] for d in dirs), default=())
    toolchain = max([go, *(mods[d][3] for d in dirs)])
    return go, toolchain


def write_go_work(dirs, work, go, toolchain):
    """Write work/go.work using dirs; work must sit outside every module.

    Written as text rather than with `go work init`, which refuses a member
    whose go line is newer than the installed toolchain.
    """
    work.mkdir(parents=True, exist_ok=True)
    target = work / "go.work"
    lines = [f"go {version_text(go)}", ""]
    if toolchain > go:
        lines += [f"toolchain go{version_text(toolchain)}", ""]
    # Quoted as Go string literals (JSON escaping is a subset), so a path with
    # spaces stays one `use` entry.
    lines += ["use (", *(f"\t{json.dumps(d)}" for d in sorted(map(str, dirs))), ")", ""]
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def install_deadcode(version, toolchain, bin_dir):
    """Build deadcode with the workspace toolchain, so go/types reads its source."""
    env = dict(
        os.environ,
        GOBIN=str(bin_dir),
        GOWORK="off",
        GOTOOLCHAIN=f"go{version_text(toolchain)}",
    )
    subprocess.run(
        ["go", "install", f"golang.org/x/tools/cmd/deadcode@{version}"],
        env=env,
        check=True,
    )
    return str(bin_dir / "deadcode")


def run(cmd, env, cwd):
    return subprocess.run(
        cmd, check=False, capture_output=True, text=True, env=env, cwd=cwd
    )


def last_error(result):
    """The first specific error line; deadcode ends with a generic summary."""
    lines = [l.strip() for l in result.stderr.splitlines() if l.strip()]
    specific = [l for l in lines if l != "deadcode: packages contain errors"]
    if specific:
        return specific[0]
    return lines[-1] if lines else f"exit {result.returncode}"


def analyse(consumer, deadcode, lib_re, env, cwd, test_tags):
    """Run one consumer's production and test builds.

    Returns ([(unreachable, loaded, compiled)], [(label, error)]), where
    unreachable maps (package, function) to (file, line), loaded is the set of
    library packages the build loaded and compiled the set of their source
    files it compiled (a file a build tag excludes is loaded with its package
    but not compiled, so deadcode cannot have judged its functions).
    """
    runs, errors = [], []
    pattern = f"{consumer}/..."
    files = '{{.ImportPath}}\t{{.Dir}}\t{{join .GoFiles ","}}\t{{join .CgoFiles ","}}'
    for label, extra in (("production", []), ("test", ["-tags", test_tags, "-test"])):
        dc = run(
            [deadcode, "-json", "-filter", lib_re.pattern, *extra, pattern], env, cwd
        )
        if dc.returncode != 0:
            if label == "production" and "no main packages" in dc.stderr:
                continue  # no binary to root at: the test build still counts
            errors.append((label, last_error(dc)))
            continue
        listed = run(["go", "list", "-deps", *extra, "-f", files, pattern], env, cwd)
        if listed.returncode != 0:
            errors.append((label, last_error(listed)))
            continue
        loaded, compiled = set(), set()
        for line in listed.stdout.splitlines():
            path, pkg_dir, go_files, cgo_files = (line.split("\t") + ["", "", ""])[:4]
            pkg = path.split(" [", 1)[0]
            if not lib_re.match(pkg) or pkg.endswith(".test"):
                continue
            loaded.add(pkg)
            for name in f"{go_files},{cgo_files}".split(","):
                if name:
                    compiled.add(os.path.realpath(os.path.join(pkg_dir, name)))
        runs.append((parse_unreachable(dc.stdout), loaded, compiled))
    return runs, errors


def parse_unreachable(stdout):
    """Map deadcode -json output to {(package, function): (file, line)}.

    deadcode prints JSON null, not [], when nothing matches the filter.
    """
    unreachable = {}
    for pkg in json.loads(stdout or "null") or []:
        for fn in pkg.get("Funcs") or []:
            pos = fn.get("Position") or {}
            unreachable[(pkg["Path"], fn["Name"])] = (
                os.path.realpath(pos["File"]) if pos.get("File") else "",
                pos.get("Line", 0),
            )
    return unreachable


def aggregate(runs, lib_packages):
    """Functions every run leaves unreached, and packages no run loads.

    A run vouches for a function only when it compiled the function's file and
    deadcode did not report it.
    """
    loaded_any = set().union(*(loaded for _, loaded, _ in runs)) if runs else set()
    candidates = {}
    for unreachable, _, _ in runs:
        candidates.update(unreachable)
    dead = {
        key: pos
        for key, pos in candidates.items()
        if all(
            key in unreachable or pos[0] not in compiled
            for unreachable, _, compiled in runs
        )
    }
    unimported = sorted(set(lib_packages) - loaded_any)
    return dict(sorted(dead.items())), unimported


def is_lib_test(pkg, libs):
    """A package under a library's top-level test/ directory: its own test support."""
    return any(pkg == f"{l}/test" or pkg.startswith(f"{l}/test/") for l in libs)


IGNORE_BUILD = re.compile(r"^//go:build\s+ignore\s*$", re.MULTILINE)


def lib_packages(libs, env, cwd):
    """The libraries' non-main packages, without their own test support.

    Maps each package to its non-test source files, including those a build
    constraint excludes from the default build (`IgnoredGoFiles`), but not
    `//go:build ignore` files, which no build ever compiles.
    """
    template = (
        '{{if ne .Name "main"}}{{.ImportPath}}\t{{.Dir}}\t{{join .GoFiles ","}}'
        '\t{{join .CgoFiles ","}}\t{{join .IgnoredGoFiles ","}}{{end}}'
    )
    listed = run(["go", "list", "-f", template, *[f"{p}/..." for p in libs]], env, cwd)
    if listed.returncode != 0:
        sys.exit(f"cannot list library packages: {last_error(listed)}")
    packages = {}
    for line in listed.stdout.splitlines():
        if not line:
            continue
        pkg, pkg_dir, *groups = (line.split("\t") + ["", "", "", ""])[:5]
        if is_lib_test(pkg, libs):
            continue
        files = set()
        for name in ",".join(groups).split(","):
            if not name or name.endswith("_test.go"):
                continue
            path = os.path.realpath(os.path.join(pkg_dir, name))
            if IGNORE_BUILD.search(pathlib.Path(path).read_text(encoding="utf-8")):
                continue
            files.add(path)
        packages[pkg] = files
    return packages


def uncompiled(packages, runs, unimported):
    """Files of imported library packages that no successful build compiled.

    deadcode judges only compiled functions, so these are outside the analysis
    rather than used.
    """
    compiled_any = (
        set().union(*(compiled for _, _, compiled in runs)) if runs else set()
    )
    skip = set(unimported)
    return sorted(
        f
        for pkg, files in packages.items()
        if pkg not in skip
        for f in files
        if f not in compiled_any
    )


def link(owner, src, shas, name, file, line):
    try:
        rel = pathlib.Path(file).resolve().relative_to(src.resolve())
    except ValueError:
        return f"`{name}`"
    repo, path = rel.parts[0], "/".join(rel.parts[1:])
    sha = shas.get(repo)
    if not sha:
        return f"`{name}`"
    return f"[`{name}`](https://github.com/{owner}/{repo}/blob/{sha}/{path}#L{line})"


def report(owner, src, shas, libs, consumers, dead, unimported, skipped):
    lines = [
        "每週 library dead code 盤點：把 library 和所有 require 它的 module 組成 go.work，",
        "逐個 consumer 跑 deadcode（production build 一次、`-test` build 一次），",
        "列出沒有任何 consumer 走得到的 library 函式與 package。產生的程式碼與 library",
        "自己 `test/` 底下的測試輔助不列入。",
        "",
        f"- Library：{', '.join(f'`{l}`' for l in libs)}",
        "- 分析的 commit（`dev`，沒有 `dev` 時用預設分支）："
        + ", ".join(f"{r}@{s[:7]}" for r, s in sorted(shas.items())),
        f"- Consumer module：{', '.join(f'`{c}`' for c in consumers)}",
        "",
    ]
    if skipped:
        lines += [
            "## 未分析",
            "",
            (
                "下列 repo、build 或檔案沒有分析到：只有失敗的 build 用到的函式會出現在下面的清單裡，"
                "沒有任何 build 編入的檔案裡的函式則完全沒有判斷。"
            ),
            "",
            "| 對象 | 原因 |",
            "|---|---|",
        ]
        lines += [f"| {who} | {why.replace('|', '¦')} |" for who, why in skipped]
        lines.append("")
    if unimported:
        lines += ["## 沒有 consumer import 的 package", ""]
        lines += [f"- `{p}`" for p in unimported]
        lines.append("")
    if dead:
        lines += [f"## 沒有 consumer 走得到的函式（{len(dead)}）", ""]
        by_pkg = {}
        for (pkg, name), (f, l) in dead.items():
            by_pkg.setdefault(pkg, []).append(link(owner, src, shas, name, f, l))
        lines += [
            f"- `{pkg}`（{len(fns)}）：{'、'.join(fns)}" for pkg, fns in by_pkg.items()
        ]
        lines.append("")
    if not dead and not unimported:
        if skipped:
            # An empty list proves nothing about what was not analysed.
            lines += [
                (
                    "成功分析的 build 沒有發現未使用的 library 函式或 package；"
                    "上面「未分析」的部分不在這個結論內。"
                ),
                "",
            ]
        else:
            lines += ["每個 library 函式都有 consumer 用到。", ""]
    body = "\n".join(lines)
    if len(body) > BODY_LIMIT:
        cut = body.rfind("\n", 0, BODY_LIMIT)
        body = (
            body[:cut]
            + "\n\n（清單過長已截斷，完整內容見 workflow run 的 summary。）\n"
        )
    return body, "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", required=True)
    parser.add_argument("--libs", required=True)
    parser.add_argument(
        "--work", required=True, help="empty directory for sources and go.work"
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--summary", default="", help="untruncated report path")
    parser.add_argument("--repos", default="")
    parser.add_argument(
        "--deadcode",
        default="deadcode",
        help="deadcode binary (ignored with --deadcode-version)",
    )
    parser.add_argument(
        "--deadcode-version",
        default="",
        help="build golang.org/x/tools/cmd/deadcode at this version with the workspace toolchain",
    )
    parser.add_argument("--test-tags", default="test")
    args = parser.parse_args()

    libs = parse_list(args.libs)
    if not libs:
        sys.exit("no library module given")
    work = pathlib.Path(args.work).resolve()
    src = work / "src"
    src.mkdir(parents=True, exist_ok=True)
    repos = sorted(parse_list(args.repos)) or list_repositories(args.owner)
    shas, skipped = fetch(args.owner, repos, src)
    skipped = [(f"repo {r}", e) for r, e in skipped]

    mods = find_modules(src)
    lib_dirs, consumers, _ = plan(mods, src, libs)
    missing = [l for l in libs if l not in lib_dirs]
    if missing:
        # Usually a GitHub API error on the library repository: report it as
        # not analysed so the workflow still updates the issue, instead of
        # exiting and leaving last week's result standing.
        skipped += [
            (f"library `{l}`", "沒有在任何取得的 repo 中找到這個 module")
            for l in missing
        ]
        body, full = report(args.owner, src, {}, libs, [], {}, [], skipped)
        emit(args, body, full, 0, 0, len(skipped))
        return
    members = [*lib_dirs.values(), *consumers.values()]
    go, toolchain = workspace_versions(mods, members)
    go_work = write_go_work(members, work / "workspace", go, toolchain)
    deadcode = args.deadcode
    if args.deadcode_version:
        deadcode = install_deadcode(args.deadcode_version, toolchain, work / "bin")
    env = dict(
        os.environ, GOWORK=str(go_work), GOFLAGS="-mod=readonly", GOTOOLCHAIN="auto"
    )
    cwd = work / "workspace"
    lib_re = re.compile("^(" + "|".join(re.escape(l) for l in libs) + ")(/|$)")

    runs = []
    for consumer in consumers:
        consumer_runs, errors = analyse(
            consumer, deadcode, lib_re, env, cwd, args.test_tags
        )
        runs += consumer_runs
        # Errors name files by absolute path or relative to the workspace
        # directory; keep only the repository-relative part.
        skipped += [
            (
                f"`{consumer}` {label} build",
                e.replace(f"{src}/", "").replace("../src/", ""),
            )
            for label, e in errors
        ]
    packages = lib_packages(libs, env, cwd)
    dead, unimported = aggregate(runs, list(packages))
    dead = {key: pos for key, pos in dead.items() if not is_lib_test(key[0], libs)}
    skipped += [
        (
            f"`{f.replace(os.path.realpath(src) + '/', '')}`",
            "沒有任何成功的 build 編入這個檔案（build tag 或平台限制）",
        )
        for f in uncompiled(packages, runs, unimported)
    ]

    used_repos = {
        d.relative_to(src).parts[0] for d in [*lib_dirs.values(), *consumers.values()]
    }
    shas = {repo: sha for repo, sha in shas.items() if repo in used_repos}
    body, full = report(
        args.owner, src, shas, libs, list(consumers), dead, unimported, skipped
    )
    emit(args, body, full, len(dead), len(unimported), len(skipped))
    shutil.rmtree(src, ignore_errors=True)


def emit(args, body, full, functions, packages, skipped):
    """Write the report files and the $GITHUB_OUTPUT counts."""
    pathlib.Path(args.report).write_text(body, encoding="utf-8")
    if args.summary:
        pathlib.Path(args.summary).write_text(full, encoding="utf-8")
    print(f"functions={functions}")
    print(f"packages={packages}")
    print(f"skipped={skipped}")


if __name__ == "__main__":
    main()
