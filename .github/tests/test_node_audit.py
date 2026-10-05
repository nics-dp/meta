"""Run the node:audit atom against a stub bun that replays canned dry-run output.

Run with: python3 .github/tests/test_node_audit.py
The stub answers `bun audit fix ...` with the canned dry run and records the
arguments of the final `bun audit` call, so each case asserts what gets ignored.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATOM = ROOT / ".mise/tasks/node/audit"
STUB = """#!/usr/bin/env bash
if [ "$1 $2" = "audit fix" ]; then
  cat "$STUB_DRY_RUN"
  exit "$STUB_DRY_RUN_RC"
fi
printf '%s\\n' "$@" > "$STUB_ARGS"
"""


def run_atom(dry_run, dry_run_rc=1):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "bun").write_text(STUB)
        (tmp / "bun").chmod(0o755)
        (tmp / "dry-run").write_text(dry_run)
        env = dict(
            os.environ,
            PATH=f"{tmp}{os.pathsep}{os.environ['PATH']}",
            STUB_DRY_RUN=str(tmp / "dry-run"),
            STUB_DRY_RUN_RC=str(dry_run_rc),
            STUB_ARGS=str(tmp / "args"),
        )
        result = subprocess.run(
            ["bash", str(ATOM)], env=env, capture_output=True, text=True
        )
        args = (tmp / "args").read_text().split()
    return result, args


class NodeAuditTests(unittest.TestCase):
    def test_ignores_ghsa_and_numeric_tokens(self):
        result, args = run_atom(
            "no published version fixes:\n"
            "  braces@3.0.3  GHSA-vfj7-8cjw-p6xm\n"
            "  xlsx@0.18.5  GHSA-4r6h-8v6p-xvw6, GHSA-5pgg-2g8v-p4x9\n"
            "  no-deps@1.1.0  1234\n"
            "    bun audit fix --ignore GHSA-vfj7-8cjw-p6xm --ignore GHSA-4r6h-8v6p-xvw6"
            " --ignore GHSA-5pgg-2g8v-p4x9 --ignore 1234\n"
            "\n"
            "Fixed 0 of 4 vulnerabilities (checked 9)\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            args,
            [
                "audit",
                "--ignore=1234",
                "--ignore=GHSA-4r6h-8v6p-xvw6",
                "--ignore=GHSA-5pgg-2g8v-p4x9",
                "--ignore=GHSA-vfj7-8cjw-p6xm",
            ],
        )
        self.assertIn("::warning::no published fix for 1234", result.stdout)

    def test_fixable_and_range_blocked_sections_still_gate(self):
        _, args = run_atom(
            "fixing:\n"
            "  ^ lodash 4.17.20 -> 4.18.0\n"
            "blocked by a dependent's range:\n"
            "  ^ minimist 0.0.8 -> 1.2.8\n"
            "    bun audit fix --ignore GHSA-xvch-5gv4-984h --ignore 5678\n"
            "\n"
            "Fixed 0 of 2 vulnerabilities (checked 3)\n"
        )
        self.assertEqual(args, ["audit"])

    def test_unreadable_dry_run_ignores_nothing(self):
        for dry_run, rc in [
            ("", 1),
            ("error: ConnectionRefused downloading advisories\n", 1),
            ("No published fix:\n    bun audit fix --ignore GHSA-vfj7-8cjw-p6xm\n", 1),
            ("", 139),
        ]:
            with self.subTest(dry_run=dry_run, rc=rc):
                _, args = run_atom(dry_run, rc)
                self.assertEqual(args, ["audit"])


if __name__ == "__main__":
    unittest.main()
