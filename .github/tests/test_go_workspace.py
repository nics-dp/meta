"""Check the Go atoms' workspace-mode handling against a stub go command.

Run with: python3 .github/tests/test_go_workspace.py
The stub answers `go env GOWORK` with STUB_GOWORK and records every call as
"<GOWORK env>|<args>", so each case asserts which go commands an atom runs and
which -mod value it picks, without a Go toolchain or a real go.work.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / ".mise/tasks"
STUB = """#!/usr/bin/env bash
printf '%s|%s\\n' "${GOWORK-}" "$*" >> "$STUB_CALLS"
if [ "$1 $2" = "env GOWORK" ]; then
  printf '%s\\n' "$STUB_GOWORK"
fi
"""


class GoWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        (self.bin / "go").write_text(STUB)
        (self.bin / "go").chmod(0o755)
        self.module = self.tmp / "module"
        self.module.mkdir()
        (self.module / "go.mod").write_text("module example.com/m\n\ngo 1.27\n")
        self.calls = self.tmp / "calls"

    def tearDown(self):
        self._tmp.cleanup()

    def run_bash(self, script, gowork, **extra_env):
        env = dict(
            os.environ,
            PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            STUB_CALLS=str(self.calls),
            STUB_GOWORK=gowork,
            **extra_env,
        )
        env.pop("GOWORK", None)
        env.pop("GO_TEST_MOD", None)
        env.update(extra_env)
        return subprocess.run(
            ["bash", "-c", script],
            cwd=self.module,
            env=env,
            capture_output=True,
            text=True,
        )

    def recorded(self):
        if not self.calls.exists():
            return []
        return self.calls.read_text().splitlines()

    def mod_flag(self, gowork, vendored):
        if vendored:
            (self.module / "vendor").mkdir()
        result = self.run_bash(
            f'source "{TASKS}/lib/go-workspace"; echo "$GO_WORKSPACE|$GO_MOD_FLAG"',
            gowork,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_workspace_mode_uses_readonly_even_with_vendor(self):
        self.assertEqual(
            self.mod_flag("/w/go.work", vendored=True), "/w/go.work|readonly"
        )

    def test_vendored_module_outside_workspace_uses_vendor(self):
        self.assertEqual(self.mod_flag("", vendored=True), "|vendor")

    def test_gowork_off_is_not_workspace_mode(self):
        self.assertEqual(self.mod_flag("off", vendored=False), "|mod")

    def test_go_env_test_mod_follows_workspace_mode(self):
        script = f'source "{TASKS}/lib/go-env"; echo "$GO_TEST_MOD"'
        result = self.run_bash(script, "/w/go.work")
        self.assertEqual(result.stdout.strip(), "readonly", result.stderr)

    def test_go_env_keeps_an_explicit_test_mod(self):
        script = f'source "{TASKS}/lib/go-env"; echo "$GO_TEST_MOD"'
        result = self.run_bash(script, "/w/go.work", GO_TEST_MOD="mod")
        self.assertEqual(result.stdout.strip(), "mod", result.stderr)

    def test_install_skips_tidy_and_vendor_in_workspace_mode(self):
        result = self.run_bash(f'bash "{TASKS}/go/install"', "/w/go.work")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("workspace mode (/w/go.work)", result.stderr)
        self.assertEqual(
            [c for c in self.recorded() if not c.endswith("|env GOWORK")], []
        )

    def test_install_tidies_and_vendors_outside_workspace_mode(self):
        result = self.run_bash(f'bash "{TASKS}/go/install"', "")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [c for c in self.recorded() if not c.endswith("|env GOWORK")],
            ["|mod tidy", "|mod vendor"],
        )

    def test_doctor_go_vendor_checks_with_gowork_off(self):
        (self.module / "vendor").mkdir()
        (self.module / "vendor" / "modules.txt").write_text("")
        self.run_bash(f'bash "{TASKS}/doctor/go-vendor"', "/w/go.work")
        vendor_checks = [c for c in self.recorded() if "-mod=vendor" in c]
        self.assertEqual(vendor_checks, ["off|list -mod=vendor -m"])


if __name__ == "__main__":
    unittest.main()
