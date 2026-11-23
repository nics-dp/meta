"""Run the go:workspace atom against throwaway module trees.

Run with: python3 .github/tests/test_go_workspace_atom.py
Needs a go toolchain on PATH (the atom calls `go mod edit` and `go work init`);
each case builds a small tree of go.mod files and reads the go.work the atom
writes. /bin/bash is preferred when present so macOS's bash 3.2 is covered.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATOM = ROOT / ".mise/tasks/go/workspace"
BASH = "/bin/bash" if Path("/bin/bash").exists() else "bash"


def go_version():
    out = subprocess.run(
        ["go", "env", "GOVERSION"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return out.removeprefix("go").split("-")[0]


@unittest.skipIf(shutil.which("go") is None, "go toolchain not on PATH")
class GoWorkspaceAtomTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.root = self.tmp / "root"
        self.version = go_version()

    def tearDown(self):
        self._tmp.cleanup()

    def module(self, rel, path, requires=()):
        d = self.root / rel
        d.mkdir(parents=True)
        lines = [f"module {path}", "", f"go {self.version}", ""]
        lines += [f"require {r} v0.0.0" for r in requires]
        (d / "go.mod").write_text("\n".join(lines) + "\n")
        return d

    def run_atom(self, **usage):
        env = {k: v for k, v in os.environ.items() if k != "GO_WORKSPACE_ROOT"}
        env.update({f"usage_{k}": str(v) for k, v in usage.items()})
        return subprocess.run(
            [BASH, str(ATOM)], env=env, capture_output=True, text=True
        )

    def used(self, work):
        result = subprocess.run(
            ["go", "work", "edit", "-json", str(work)],
            capture_output=True, text=True, check=True,
        )
        return sorted(
            line.split('"')[3]
            for line in result.stdout.splitlines()
            if '"DiskPath"' in line
        )

    def test_joins_modules_that_require_one_another(self):
        lib = self.module("lib", "example.com/lib")
        app = self.module("app", "example.com/app", ["example.com/lib"])
        self.module("solo", "example.com/solo")
        result = self.run_atom(root=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        work = self.root / ".go-workspace" / "go.work"
        self.assertEqual(self.used(work), sorted([str(app), str(lib)]))
        self.assertIn(f"export GOWORK={work}", result.stderr)

    def test_first_directory_keeps_a_duplicated_module_path(self):
        lib = self.module("a-lib", "example.com/lib")
        self.module("b-copy", "example.com/lib")
        app = self.module("app", "example.com/app", ["example.com/lib"])
        result = self.run_atom(root=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("example.com/lib is already taken", result.stderr)
        work = self.root / ".go-workspace" / "go.work"
        self.assertEqual(self.used(work), sorted([str(lib), str(app)]))

    def test_use_replaces_the_discovered_module(self):
        self.module("lib", "example.com/lib")
        app = self.module("app", "example.com/app", ["example.com/lib"])
        tree = self.tmp / "worktree"
        tree.mkdir()
        (tree / "go.mod").write_text(f"module example.com/lib\n\ngo {self.version}\n")
        out = self.tmp / "out" / "dev.work"
        result = self.run_atom(root=self.root, out=out, use=tree)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.used(out), sorted([str(app), str(tree)]))

    def test_refuses_a_go_work_the_go_command_would_find(self):
        self.module("lib", "example.com/lib")
        self.module("app", "example.com/app", ["example.com/lib"])
        out = self.root / "go.work"
        result = self.run_atom(root=self.root, out=out)
        self.assertEqual(result.returncode, 1)
        self.assertIn("would be found by the go command", result.stderr)
        self.assertFalse(out.exists())

    def test_refuses_a_go_work_inside_a_module_left_out(self):
        self.module("lib", "example.com/lib")
        self.module("app", "example.com/app", ["example.com/lib"])
        solo = self.module("solo", "example.com/solo")
        result = self.run_atom(root=self.root, out=solo / "go.work")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"from {solo}", result.stderr)
        self.assertFalse((solo / "go.work").exists())

    def test_refuses_a_go_work_at_the_filesystem_root(self):
        self.module("lib", "example.com/lib")
        self.module("app", "example.com/app", ["example.com/lib"])
        result = self.run_atom(root=self.root, out="/go.work")
        self.assertEqual(result.returncode, 1)
        self.assertIn("would be found by the go command", result.stderr)

    def test_refuses_a_directory_as_out(self):
        self.module("lib", "example.com/lib")
        app = self.module("app", "example.com/app", ["example.com/lib"])
        result = self.run_atom(root=self.root, out=app)
        self.assertEqual(result.returncode, 1)
        self.assertIn("is a directory", result.stderr)
        self.assertFalse((app / "go.work").exists())

    def test_enable_hint_survives_spaces_in_the_path(self):
        self.root = self.tmp / "Work dcf"
        self.module("lib", "example.com/lib")
        self.module("app", "example.com/app", ["example.com/lib"])
        result = self.run_atom(root=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        hint = next(
            line.split(": ", 1)[1]
            for line in result.stderr.splitlines()
            if line.startswith("Enable it")
        )
        echoed = subprocess.run(
            [BASH, "-c", f'{hint}; printf "%s" "$GOWORK"'],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(echoed, str(self.root / ".go-workspace" / "go.work"))

    def test_requires_a_root(self):
        result = self.run_atom()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no scan root", result.stderr)

    def test_fails_when_no_module_requires_another(self):
        self.module("solo", "example.com/solo")
        result = self.run_atom(root=self.root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires another module", result.stderr)


if __name__ == "__main__":
    unittest.main()
