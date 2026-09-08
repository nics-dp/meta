"""Exercise the workflow's actual inline filter without running scanners or uploads."""

import copy
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "semgrep"


def filter_source():
    workflow = (ROOT / ".github/workflows/security-sarif.yml").read_text()
    marker = "      - name: Drop nosemgrep-suppressed results from semgrep SARIF\n"
    assert workflow.count(marker) == 1
    step = workflow.split(marker, 1)[1].split("      - name:", 1)[0]
    code = step.split("python3 - <<'FILTER_PY'\n", 1)[1].split(
        "          FILTER_PY", 1
    )[0]
    return textwrap.dedent(code)


class SemgrepSuppressionTests(unittest.TestCase):
    source: str

    @classmethod
    def setUpClass(cls):
        cls.source = filter_source()
        compile(cls.source, "security-sarif.yml:semgrep-filter", "exec")

    def run_filter(self, raw, failure=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "semgrep.sarif"
            path.write_bytes(raw)
            source = self.source
            if failure == "write":
                Path(str(path) + ".tmp").mkdir()
            elif failure == "replace":
                source = (
                    "from unittest.mock import patch\n"
                    "patch('os.replace', side_effect=OSError('replace failed')).start()\n"
                    + source
                )
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-c", source],
                cwd=directory,
                env={"HOME": directory, "PATH": "/usr/bin:/bin"},
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            self.assertEqual(completed.stderr, "")
            if failure is None and "skipped" not in completed.stdout:
                self.assertFalse(Path(str(path) + ".tmp").exists())
            return path.read_bytes(), completed.stdout

    def assert_filtered(self, document, expected, removed):
        raw, output = self.run_filter(json.dumps(document).encode())
        self.assertEqual(json.loads(raw), expected)
        self.assertEqual(
            output,
            f"semgrep-filter: removed {removed} nosemgrep-suppressed result(s)\n",
        )

    def test_real_raw_producer_fixtures(self):
        for version in ("1.176.0", "1.176.1"):
            with self.subTest(version=version):
                raw = (FIXTURES / f"semgrep-{version}.sarif").read_bytes()
                document = json.loads(raw)
                run = document["runs"][0]
                self.assertEqual(run["tool"]["driver"]["semanticVersion"], version)
                self.assertEqual(len(run["results"]), 2)
                self.assertEqual(
                    run["results"][0]["suppressions"], [{"kind": "inSource"}]
                )
                self.assertNotIn("suppressions", run["results"][1])
                expected = copy.deepcopy(document)
                del expected["runs"][0]["results"][0]
                filtered, output = self.run_filter(raw)
                self.assertEqual(json.loads(filtered), expected)
                self.assertIn("removed 1 ", output)

    def test_suppression_policy(self):
        cases = [
            (None, False),
            ([], False),
            ([{"kind": "inSource"}], True),
            ([{"kind": "inSource", "status": "accepted"}], True),
            ([{"kind": "inSource"}, {"kind": "inSource", "status": "accepted"}], True),
            ([{"kind": "inSource", "status": "rejected"}], False),
            ([{"kind": "inSource", "status": "underReview"}], False),
            ([{"kind": "inSource", "status": "unknown"}], False),
            ([{"kind": "inSource", "status": None}], False),
            ([{"kind": "inSource", "status": False}], False),
            ([{"kind": "inSource", "status": []}], False),
            ([{"kind": "inSource", "status": ""}], False),
            ([{"kind": "external", "status": "accepted"}], False),
            ([{"kind": "unknown", "status": "accepted"}], False),
            ([{"status": "accepted"}], False),
            ([{"state": "accepted"}], False),
            ([{"kind": "inSource", "state": "accepted"}], False),
            ([{"kind": "inSource", "state": "accepted", "status": "accepted"}], False),
            ([{"kind": "inSource", "state": "rejected", "status": "accepted"}], False),
            ([{"kind": "inSource", "state": None}], False),
            ([None], False),
            ([{}], False),
            (["inSource"], False),
            ([True], False),
            ([[{"kind": "inSource"}]], False),
            ({"kind": "inSource"}, False),
            ("accepted", False),
            (True, False),
            (1, False),
            (0, False),
        ]
        for suppressions, remove in cases:
            with self.subTest(suppressions=suppressions):
                finding = {"ruleId": "test", "suppressions": suppressions}
                document = {"runs": [{"results": [finding]}]}
                expected = {"runs": [{"results": [] if remove else [finding]}]}
                self.assert_filtered(document, expected, int(remove))

    def test_mixed_entries_preserve_entire_result_in_either_order(self):
        for uncertain in (
            {"kind": "inSource", "status": "rejected"},
            {"kind": "inSource", "status": "underReview"},
            {"kind": "external", "status": "accepted"},
            {"state": "accepted"},
            {},
            None,
        ):
            for entries in (
                [{"kind": "inSource", "status": "accepted"}, uncertain],
                [uncertain, {"kind": "inSource"}],
            ):
                with self.subTest(entries=entries):
                    document = {"runs": [{"results": [{"suppressions": entries}]}]}
                    self.assert_filtered(document, document, 0)

    def test_multiple_runs_preserve_order_and_unrelated_data(self):
        plain = {
            "ruleId": "ordinary",
            "message": {"text": "keep the complete finding"},
            "fingerprints": {"id": "original"},
            "properties": {"nested": [1, None, {"key": "value"}]},
        }
        suppressed = {"suppressions": [{"kind": "inSource"}]}
        document: dict = {
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "Semgrep OSS"}},
                    "results": [suppressed, plain],
                },
                {
                    "automationDetails": {"id": "semgrep/"},
                    "results": [plain, suppressed, plain],
                },
                {"results": []},
            ],
        }
        expected = copy.deepcopy(document)
        expected["runs"][0]["results"] = [plain]
        expected["runs"][1]["results"] = [plain, plain]
        self.assert_filtered(document, expected, 2)

    def test_invalid_document_keeps_original_bytes(self):
        for raw in (
            b"{ invalid JSON",
            b'{"runs":[null]}',
            b'{"runs":[{"results":[null]}]}',
        ):
            with self.subTest(raw=raw):
                filtered, output = self.run_filter(raw)
                self.assertEqual(filtered, raw)
                self.assertIn("semgrep-filter: skipped (", output)
                self.assertIn("original SARIF kept", output)

    def test_write_or_replace_failure_keeps_original_bytes(self):
        raw = b'{ "runs": [{ "results": [{"suppressions": [{"kind":"inSource"}]}] }] }'
        for failure in ("write", "replace"):
            with self.subTest(failure=failure):
                filtered, output = self.run_filter(raw, failure=failure)
                self.assertEqual(filtered, raw)
                self.assertIn("semgrep-filter: skipped (", output)
                self.assertIn("original SARIF kept", output)


if __name__ == "__main__":
    unittest.main()
