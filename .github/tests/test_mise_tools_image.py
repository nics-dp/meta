"""Exercise the image push step with isolated command stubs."""

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/mise-tools-image.yml"
DIGEST = "sha256:" + "a" * 64


def push_source():
    source = WORKFLOW.read_text()
    marker = "        id: push\n"
    assert source.count(marker) == 1
    step = source.split(marker, 1)[1].split("\n      - ", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


class PushTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mise-image.")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state with spaces"
        (self.state / "image").mkdir(parents=True)
        (self.state / "docker").mkdir()
        self.layout_digest(DIGEST)
        self.output = self.root / "output"
        self.summary = self.root / "summary"
        self.output.touch()
        self.summary.touch()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "HOME": str(self.root),
            "MISE_TOOLS_STATE": str(self.state),
            "DOCKER_CONFIG": str(self.state / "docker"),
            "REGISTRY_AUTH_FILE": str(self.state / "docker/config.json"),
            "IMAGE": "ghcr.io/example/tools",
            "EXTRA_TAG": "experiment",
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "PUSH_ARGS": str(self.root / "push-args"),
            "INSPECT_ARGS": str(self.root / "inspect-args"),
            "PUSH_EXIT": "0",
            "INSPECT_EXIT": "0",
            "REMOTE_DIGEST": DIGEST,
        }
        self.stub(
            "mise",
            """
            test "$REGISTRY_AUTH_FILE" = "$DOCKER_CONFIG/config.json" || exit 99
            printf '%s\\n' "$@" > "$PUSH_ARGS"
            exit "$PUSH_EXIT"
        """,
        )
        self.stub(
            "docker",
            """
            test "$DOCKER_CONFIG" = "$MISE_TOOLS_STATE/docker" || exit 99
            printf '%s\\n' "$@" > "$INSPECT_ARGS"
            printf '%s\\n' "$REMOTE_DIGEST"
            exit "$INSPECT_EXIT"
        """,
        )

    def stub(self, name, source):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\nset -eu\n" + textwrap.dedent(source))
        path.chmod(0o755)

    def layout_digest(self, digest):
        (self.state / "image/index.json").write_text(
            json.dumps({"manifests": [{"digest": digest}]})
        )

    def run_push(self):
        return subprocess.run(
            ["bash", "-e", "-c", push_source()],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def assert_no_output(self):
        self.assertEqual(self.output.read_text(), "")
        self.assertEqual(self.summary.read_text(), "")

    def test_native_push_and_remote_digest(self):
        result = self.run_push()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(
            (self.root / "push-args").read_text().splitlines(),
            [
                "oci",
                "push",
                "--image-dir",
                str(self.state / "image"),
                "ghcr.io/example/tools:experiment",
            ],
        )
        self.assertEqual(
            (self.root / "inspect-args").read_text().splitlines(),
            [
                "buildx",
                "imagetools",
                "inspect",
                "--format",
                "{{.Manifest.Digest}}",
                "ghcr.io/example/tools:experiment",
            ],
        )
        self.assertEqual(self.output.read_text(), f"digest={DIGEST}\n")
        self.assertIn(f"ghcr.io/example/tools@{DIGEST}", self.summary.read_text())

    def test_remote_digest_mismatch(self):
        self.env["REMOTE_DIGEST"] = "sha256:" + "b" * 64
        self.assertNotEqual(self.run_push().returncode, 0)
        self.assert_no_output()

    def test_push_failure_stops_inspection(self):
        self.env["PUSH_EXIT"] = "42"
        self.assertEqual(self.run_push().returncode, 42)
        self.assertFalse((self.root / "inspect-args").exists())
        self.assert_no_output()

    def test_inspection_failure_rejects_matching_output(self):
        self.env["INSPECT_EXIT"] = "43"
        self.assertEqual(self.run_push().returncode, 43)
        self.assert_no_output()

    def test_invalid_layout_digest_stops_push(self):
        self.layout_digest("invalid")
        self.assertNotEqual(self.run_push().returncode, 0)
        self.assertFalse((self.root / "push-args").exists())
        self.assert_no_output()


if __name__ == "__main__":
    unittest.main()
