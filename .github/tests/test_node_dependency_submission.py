"""Execute the reusable workflow's helper without submitting dependency snapshots."""

import argparse
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/node-dependency-submission.yml"


def helper_source():
    source = WORKFLOW.read_text()
    marker = "cat > \"$state/helper.py\" <<'SUBMISSION_PY'\n"
    assert source.count(marker) == 1
    return textwrap.dedent(
        source.split(marker, 1)[1].split("          SUBMISSION_PY", 1)[0]
    )


def helper_module():
    with tempfile.TemporaryDirectory(prefix="node-helper.") as directory:
        path = Path(directory) / "helper.py"
        path.write_text(helper_source())
        spec = importlib.util.spec_from_file_location("submission_helper", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="node-submission.")
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name).resolve()
        self.project = self.state / "project"
        self.project.mkdir()
        self.helper = helper_module()
        self.manifest = {
            "name": "fixture",
            "dependencies": {"app": "1.0.0"},
            "devDependencies": {"dev": "1.0.0"},
        }
        self.entries = {
            "app": [
                "app@1.0.0",
                "",
                {
                    "dependencies": {"shared": "1.0.0"},
                    "peerDependencies": {"peer": "1.0.0"},
                    "optionalDependencies": {"optional": "1.0.0", "absent": "1.0.0"},
                },
                "sha512-AAAA",
            ],
            "shared": ["shared@1.0.0", "", {}, "sha512-AAAA"],
            "peer": ["peer@1.0.0", "", {}, "sha512-AAAA"],
            "optional": ["optional@1.0.0", "", {}, "sha512-AAAA"],
            "dev": [
                "dev@1.0.0",
                "",
                {"dependencies": {"shared": "1.0.0"}},
                "sha512-AAAA",
            ],
        }
        self.context = {
            "sha": "a" * 40,
            "ref": "refs/heads/dev",
            "workflow": "CI 🚀",
            "job": "node-dependency-submission",
            "run_id": "42",
            "repository": "org/repo",
            "working_directory": "web",
        }
        self.producer = {
            "name": "syft",
            "version": "1.52.0",
            "configuration": {
                "packages": {"javascript": {"include-dev-dependencies": True}}
            },
        }

    def fixture(self):
        h = self.helper
        lock = {
            "lockfileVersion": 1,
            "configVersion": 1,
            "workspaces": {"": self.manifest},
            "packages": self.entries,
        }
        if "patchedDependencies" in self.manifest:
            lock["patchedDependencies"] = self.manifest["patchedDependencies"]
        (self.project / "package.json").write_text(json.dumps(self.manifest))
        (self.project / "bun.lock").write_text(json.dumps(lock))
        packages = []
        for i, (key, entry) in enumerate(self.entries.items()):
            name, version = (
                entry[0].split("@", 1)
                if not entry[0].startswith("@")
                else entry[0].rsplit("@", 1)
            )
            path = self.project / h.key_path(key)
            path.mkdir(parents=True, exist_ok=True)
            (path / "package.json").write_text(
                json.dumps({"name": name, "version": version, "license": "MIT"})
            )
            packages.append(
                {
                    "id": "npm-" + str(i),
                    "name": name,
                    "version": version,
                    "type": "npm",
                    "purl": "pkg:npm/"
                    + h.quote(name, safe="/")
                    + "@"
                    + h.quote(version, safe=""),
                    "foundBy": "javascript-lock-cataloger",
                    "language": "javascript",
                    "licenses": [],
                    "metadataType": "javascript-bun-lock-entry",
                    "metadata": next(x for x in entry[1:] if isinstance(x, dict)),
                    "locations": [{"path": "/bun.lock", "accessPath": "/bun.lock"}],
                }
            )
        packages.append(
            {
                "id": "action",
                "name": "actions/checkout",
                "version": "v7",
                "type": "github-action",
                "purl": "pkg:github/actions/checkout@v7",
                "locations": [{"path": "/.github/workflows/ci.yml"}],
                "metadata": {"untouched": ["value", 1]},
                "licenses": [],
            }
        )
        raw = {
            "artifacts": packages,
            "artifactRelationships": [],
            "files": [{"id": "file", "location": {"path": "/bun.lock"}}],
            "source": {
                "id": "source",
                "name": "fixture",
                "type": "directory",
                "version": "1.0.0",
                "metadata": {"path": str(self.project)},
            },
            "descriptor": self.producer,
            "schema": {"version": "16.1.10", "url": "https://example.com/schema"},
            "distro": {},
        }
        for package in packages:
            raw["artifactRelationships"].extend(
                [
                    {"parent": "source", "child": package["id"], "type": "contains"},
                    {"parent": package["id"], "child": "file", "type": "evident-by"},
                ]
            )
        return raw

    def inventory(self, members):
        records, _, _ = self.helper.graph(self.project)
        representatives = {}
        for location in sorted(members):
            record = records[location]
            representatives.setdefault(record["name"], {}).setdefault(
                record["version"], str(self.project / location)
            )
        entries = [
            {
                "name": name,
                "versions": sorted(versions),
                "paths": [versions[version] for version in sorted(versions)],
                "license": "MIT",
            }
            for name, versions in sorted(representatives.items())
        ]
        return {"MIT": entries} if entries else {}

    def normalized(self):
        raw = self.fixture()
        _, _, edges = self.helper.graph(self.project)
        return raw, self.helper.normalize(
            raw, self.inventory(edges), self.project, self.project
        )

    def converted(self):
        return {
            "version": 0,
            "detector": {
                "name": "syft",
                "version": "1.52.0",
                "url": "https://github.com/anchore/syft",
            },
            "scanned": "2026-01-01T00:00:00Z",
            "manifests": {
                str(self.project / ".github/workflows/ci.yml"): {
                    "name": "first-party",
                    "file": {
                        "source_location": str(
                            self.project / ".github/workflows/ci.yml"
                        )
                    },
                    "resolved": {
                        "action": {
                            "package_url": "pkg:github/actions/checkout@v7",
                            "scope": "runtime",
                            "relationship": "direct",
                            "dependencies": [],
                        }
                    },
                    "metadata": {"keep": "value"},
                }
            },
        }

    def test_shared_optional_peer_graph_and_non_npm_preservation(self):
        raw, (corrected, selected, roots, edges) = self.normalized()
        self.assertEqual(
            set(edges),
            {"node_modules/" + x for x in ("app", "shared", "peer", "optional")},
        )
        self.assertEqual(roots, {"node_modules/app"})
        self.assertEqual(corrected["source"], raw["source"])
        self.assertEqual(corrected["files"], raw["files"])
        self.assertEqual(corrected["artifacts"][0], raw["artifacts"][-1])
        npm_edges = [
            r
            for r in corrected["artifactRelationships"]
            if r["type"] == "dependency-of"
        ]
        self.assertTrue(
            all(r["child"] == selected["node_modules/app"]["id"] for r in npm_edges)
        )
        self.assertEqual(len(npm_edges), 3)
        final = self.helper.snapshot(
            self.converted(), selected, roots, edges, self.project, self.context
        )
        graph = final["manifests"]["web/bun.lock"]["resolved"]
        self.assertEqual(graph["pkg:npm/app@1.0.0"]["relationship"], "direct")
        self.assertEqual(graph["pkg:npm/shared@1.0.0"]["relationship"], "indirect")
        self.assertEqual(
            graph["pkg:npm/app@1.0.0"]["dependencies"],
            sorted(
                selected[location]["purl"] for location in edges["node_modules/app"]
            ),
        )
        self.assertEqual(final["job"]["correlator"], "CI _node-dependency-submission")
        self.assertIn("web/.github/workflows/ci.yml", final["manifests"])

    def test_version_split_alias_cycles_git_and_multiple_locations(self):
        self.manifest["dependencies"].update(
            {"alias": "npm:real@2.0.0", "git": "github:org/repo"}
        )
        self.entries["app"][2]["dependencies"]["shared"] = "2.0.0"
        self.entries["app/shared"] = [
            "shared@2.0.0",
            "",
            {"dependencies": {"app": "1.0.0"}},
            "sha512-AAAA",
        ]
        self.entries["alias"] = ["real@2.0.0", "", {}, "sha512-AAAA"]
        self.entries["git"] = [
            "git@github:org/repo#abcdef0",
            {},
            "org-repo-abcdef0",
            "sha512-AAAA",
        ]
        raw, (corrected, selected, roots, edges) = self.normalized()
        self.assertIn("node_modules/app/node_modules/shared", edges)
        self.assertNotIn("node_modules/shared", edges)
        self.assertIn("node_modules/app", edges["node_modules/app/node_modules/shared"])
        self.assertEqual(selected["node_modules/alias"]["name"], "real")
        self.assertEqual(
            selected["node_modules/git"]["version"], "github:org/repo#abcdef0"
        )
        self.assertEqual(
            self.helper.normalize(
                raw, self.inventory(edges), self.project, self.project
            )[0],
            corrected,
        )
        self.assertIn("node_modules/alias", roots)

    def test_same_identity_at_distinct_locations(self):
        self.entries["app/shared"] = copy.deepcopy(self.entries["shared"])
        self.manifest["dependencies"]["shared"] = "1.0.0"
        _, (_, selected, _, edges) = self.normalized()
        self.assertIn("node_modules/shared", edges)
        self.assertIn("node_modules/app/node_modules/shared", edges)
        self.assertNotEqual(
            selected["node_modules/shared"]["id"],
            selected["node_modules/app/node_modules/shared"]["id"],
        )

    def test_deduplicated_native_identity_retains_context_edges_and_cross_types(self):
        self.manifest["dependencies"]["shared"] = "1.0.0"
        self.entries["shared"][2] = {"peerDependencies": {"peer": "*"}}
        self.entries["app/shared"] = copy.deepcopy(self.entries["shared"])
        self.entries["app"][2]["peerDependencies"]["peer"] = "2.0.0"
        self.entries["app/peer"] = ["peer@2.0.0", "", {}, "sha512-AAAA"]
        self.entries["dev/shared"] = copy.deepcopy(self.entries["shared"])
        raw = self.fixture()
        records, roots, edges = self.helper.graph(self.project)
        inventory = self.inventory(edges)
        shared_inventory = next(
            item for item in inventory["MIT"] if item["name"] == "shared"
        )
        self.assertEqual(shared_inventory["versions"], ["1.0.0"])
        self.assertEqual(len(shared_inventory["paths"]), 1)
        self.assertNotIn("node_modules/dev/node_modules/shared", edges)
        app = next(p for p in raw["artifacts"] if p["name"] == "app")
        shared = next(p for p in raw["artifacts"] if p["name"] == "shared")
        dev = next(p for p in raw["artifacts"] if p["name"] == "dev")
        raw["artifactRelationships"].extend(
            [
                {"parent": shared["id"], "child": "action", "type": "dependency-of"},
                {"parent": "action", "child": app["id"], "type": "dependency-of"},
                {"parent": "action", "child": dev["id"], "type": "dependency-of"},
            ]
        )
        corrected, selected, _, _ = self.helper.normalize(
            raw, inventory, self.project, self.project
        )
        cross = [
            r
            for r in corrected["artifactRelationships"]
            if r["type"] == "dependency-of" and "action" in (r["parent"], r["child"])
        ]
        self.assertEqual(len(cross), 3)
        converted = self.converted()
        action = next(iter(converted["manifests"].values()))["resolved"]["action"]
        action["dependencies"] = ["pkg:npm/app@1.0.0", "pkg:npm/dev@1.0.0"]
        final = self.helper.snapshot(
            converted,
            selected,
            roots,
            edges,
            self.project,
            self.context,
            native=corrected,
        )
        npm = final["manifests"]["web/bun.lock"]["resolved"]
        members = self.helper.inventory_members(inventory, self.project, records)
        self.assertEqual(len(npm), len(members))
        self.assertLess(len(npm), len(selected))
        self.assertEqual(npm["pkg:npm/shared@1.0.0"]["relationship"], "direct")
        self.assertEqual(
            npm["pkg:npm/shared@1.0.0"]["dependencies"],
            ["pkg:npm/peer@1.0.0", "pkg:npm/peer@2.0.0"],
        )
        self.assertIn("action", npm["pkg:npm/app@1.0.0"]["dependencies"])
        self.assertEqual(
            final["manifests"]["web/.github/workflows/ci.yml"]["resolved"]["action"][
                "dependencies"
            ],
            ["pkg:npm/shared@1.0.0"],
        )
        self.assertNotIn("pkg:npm/dev@1.0.0", npm)
        if shutil.which("bun"):
            self.helper.configs(self.state)
            actual = json.loads(
                self.helper.execute(
                    [
                        shutil.which("bun"),
                        "--config=" + str(self.state / "bunfig.toml"),
                        "pm",
                        "licenses",
                        "--prod",
                        "--json",
                    ],
                    self.state,
                    self.project,
                )
            )
            self.assertEqual(
                self.helper.inventory_members(actual, self.project, records), members
            )
            native_shared = next(
                item for item in actual["MIT"] if item["name"] == "shared"
            )
            self.assertEqual(native_shared["versions"], ["1.0.0"])
            self.assertEqual(len(native_shared["paths"]), 1)
            self.helper.normalize(raw, actual, self.project, self.project)

    def test_native_representative_is_validated_as_an_installed_record(self):
        self.fixture()
        records, _, edges = self.helper.graph(self.project)
        inventory = self.inventory(edges)
        (self.project / "node_modules/app/package.json").write_text(
            '{"name":"wrong","version":"1.0.0"}'
        )
        with self.assertRaisesRegex(ValueError, "installed name"):
            self.helper.inventory_members(inventory, self.project, records)

    def test_npm_purl_identity_and_qualifiers_are_validated(self):
        raw = self.fixture()
        _, _, edges = self.helper.graph(self.project)
        inventory = self.inventory(edges)
        app = next(p for p in raw["artifacts"] if p["name"] == "app")
        for value in (
            "pkg:npm/other@1.0.0",
            "pkg:npm/app@9.0.0",
            "pkg:npm/app@1.0.0?source=x&source=y",
            "pkg:npm/app@1.0.0?source=%ZZ",
            "pkg:npm/app@1.0.0?source=line%0Abreak",
            "pkg:npm/app@1.0.0#../file",
        ):
            app["purl"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.helper.normalize(raw, inventory, self.project, self.project)
        app["purl"] = "pkg:npm/app@1.0.0?vcs_url=https%3A%2F%2Fexample.com%2Frepo"
        _, selected, roots, edges = self.helper.normalize(
            raw, inventory, self.project, self.project
        )
        final = self.helper.snapshot(
            self.converted(), selected, roots, edges, self.project, self.context
        )
        self.assertEqual(
            final["manifests"]["web/bun.lock"]["resolved"]["pkg:npm/app@1.0.0"][
                "package_url"
            ],
            app["purl"],
        )
        conflict = copy.deepcopy(app)
        conflict["id"] = "conflicting-source"
        conflict["purl"] = (
            "pkg:npm/app@1.0.0?vcs_url=https%3A%2F%2Fother.example%2Frepo"
        )
        raw["artifacts"].append(conflict)
        with self.assertRaisesRegex(ValueError, "conflicting npm PURLs"):
            self.helper.normalize(raw, inventory, self.project, self.project)

    def test_retained_npm_references_are_not_pruned(self):
        _, (_, selected, roots, edges) = self.normalized()
        converted = self.converted()
        action = next(iter(converted["manifests"].values()))["resolved"]["action"]
        action["dependencies"] = ["pkg:npm/shared@1.0.0", "pkg:npm/dev@1.0.0"]
        final = self.helper.snapshot(
            converted, selected, roots, edges, self.project, self.context
        )
        self.assertEqual(
            final["manifests"]["web/.github/workflows/ci.yml"]["resolved"]["action"][
                "dependencies"
            ],
            ["pkg:npm/shared@1.0.0"],
        )

    def test_empty_production_is_valid(self):
        self.manifest["dependencies"] = {}
        raw, (corrected, selected, roots, edges) = self.normalized()
        self.assertEqual(selected, {})
        self.assertEqual(edges, {})
        self.assertEqual(corrected["artifacts"], [raw["artifacts"][-1]])
        self.assertEqual(
            self.helper.snapshot(
                self.converted(), selected, roots, edges, self.project, self.context
            )["manifests"]["web/bun.lock"]["resolved"],
            {},
        )

    def test_missing_converted_manifests_requires_empty_native(self):
        _, (corrected, selected, roots, edges) = self.normalized()
        converted = self.converted()
        converted.pop("manifests")
        with self.assertRaisesRegex(ValueError, "omitted nonempty"):
            self.helper.snapshot(
                converted,
                selected,
                roots,
                edges,
                self.project,
                self.context,
                native=corrected,
            )
        final = self.helper.snapshot(
            converted,
            {},
            set(),
            {},
            self.project,
            self.context,
            native={"artifacts": [], "artifactRelationships": []},
        )
        self.assertEqual(set(final["manifests"]), {"web/bun.lock"})
        self.assertEqual(final["manifests"]["web/bun.lock"]["resolved"], {})
        converted["manifests"] = None
        with self.assertRaisesRegex(ValueError, "invalid converted manifests"):
            self.helper.snapshot(
                converted,
                {},
                set(),
                {},
                self.project,
                self.context,
                native={"artifacts": [], "artifactRelationships": []},
            )

    def test_git_directory_links_are_validated_before_pruning(self):
        self.fixture()
        outside = self.state / "outside"
        outside.mkdir()
        for parent in (self.project, self.project / "node_modules/app"):
            git = parent / ".git"
            git.mkdir()
            self.helper.check_tree(self.project)
            git.rmdir()
            git.symlink_to(outside, target_is_directory=True)
            with (
                self.subTest(parent=parent),
                self.assertRaisesRegex(ValueError, "escapes"),
            ):
                self.helper.check_tree(self.project)
            git.unlink()
            git.symlink_to(outside / "missing", target_is_directory=True)
            with self.subTest(parent=parent), self.assertRaises(FileNotFoundError):
                self.helper.check_tree(self.project)
            git.unlink()

    def test_proto_is_data_and_controls_are_rejected(self):
        self.manifest["dependencies"]["__proto__"] = "1.0.0"
        self.entries["__proto__"] = ["__proto__@1.0.0", "", {}, "sha512-AAAA"]
        _, (_, selected, _, _) = self.normalized()
        self.assertIn("node_modules/__proto__", selected)
        for value in ("a\nb", "a\x00b", "a\rb", "a\x7fb", "a\x85b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.helper.text(value)

    def test_missing_malformed_native_and_required_edges_fail(self):
        raw = self.fixture()
        for value in (
            [],
            {"MIT": {}},
            {"MIT": [{"name": "app", "versions": [], "paths": []}]},
            {},
        ):
            with (
                self.subTest(value=value),
                self.assertRaises((ValueError, KeyError, TypeError)),
            ):
                self.helper.normalize(raw, value, self.project, self.project)
        (self.project / "node_modules/shared/package.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing required"):
            self.helper.graph(self.project)

    def test_native_versions_and_path_mismatch_fail(self):
        raw = self.fixture()
        _, _, edges = self.helper.graph(self.project)
        value = self.inventory(edges)
        value["MIT"][0]["versions"] = ["9.0.0"]
        with self.assertRaisesRegex(ValueError, "native identity"):
            self.helper.normalize(raw, value, self.project, self.project)
        value = self.inventory(edges)
        value["MIT"][0]["paths"] = [str(self.state)]
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.helper.normalize(raw, value, self.project, self.project)

    def test_missing_syft_and_invalid_references_fail(self):
        raw = self.fixture()
        _, _, edges = self.helper.graph(self.project)
        inventory = self.inventory(edges)
        raw["artifactRelationships"].append(
            {"parent": "file", "child": "missing", "type": "contains"}
        )
        with self.assertRaisesRegex(ValueError, "dangling"):
            self.helper.normalize(raw, inventory, self.project, self.project)
        raw["artifactRelationships"].pop()
        raw["descriptor"]["configuration"]["packages"]["javascript"][
            "include-dev-dependencies"
        ] = False
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.helper.normalize(raw, inventory, self.project, self.project)

    def test_root_evidence_cannot_be_replaced_by_nested_lock(self):
        raw = self.fixture()
        _, _, edges = self.helper.graph(self.project)
        inventory = self.inventory(edges)
        app = next(p for p in raw["artifacts"] if p["name"] == "app")
        app["locations"] = [{"path": "/fixture/bun.lock"}]
        with self.assertRaisesRegex(ValueError, "root Syft evidence"):
            self.helper.normalize(raw, inventory, self.project, self.project)

    def test_relative_source_prefix_is_applied_once(self):
        converted = self.converted()
        manifest = next(iter(converted["manifests"].values()))
        for prefix in (".", "web"):
            source_location = (
                ".github/workflows/ci.yml"
                if prefix == "."
                else "web/.github/workflows/ci.yml"
            )
            manifest["file"]["source_location"] = source_location
            final = self.helper.snapshot(
                converted, {}, set(), {}, self.project, self.context, prefix
            )
            self.assertIn("web/.github/workflows/ci.yml", final["manifests"])
            self.assertNotIn("web/web/.github/workflows/ci.yml", final["manifests"])

    def test_paths_containment_and_internal_links(self):
        self.fixture()
        for value in ("", "/absolute", "../outside", "a/../../b", "a\nb", "a\\b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.helper.prepare(self.project, value)
        link = self.project / "external"
        link.symlink_to(self.state)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.helper.prepare(self.project, ".")
        link.unlink()
        link.symlink_to(self.project / "package.json")
        self.assertEqual(self.helper.prepare(self.project, "."), self.project)
        link.unlink()
        link.symlink_to(self.project / "missing")
        with self.assertRaises(FileNotFoundError):
            self.helper.prepare(self.project, ".")

    def test_sha_event_allowlist(self):
        expected_events = (
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
        )
        self.assertEqual(self.helper.PR_EVENTS, set(expected_events))
        for event in expected_events:
            self.assertEqual(
                self.helper.selected_sha(
                    event, {"pull_request": {"head": {"sha": "b" * 40}}}, "a" * 40
                ),
                "b" * 40,
            )
        for event in ("push", "schedule", "pull_request_target", "workflow_dispatch"):
            self.assertEqual(self.helper.selected_sha(event, {}, "a" * 40), "a" * 40)
        issue_comment = {
            "action": "created",
            "issue": {
                "number": 42,
                "pull_request": {
                    "url": "https://api.github.com/repos/org/repo/pulls/42"
                },
            },
        }
        self.assertEqual(
            self.helper.selected_sha("issue_comment", issue_comment, "a" * 40),
            "a" * 40,
        )
        with self.assertRaises(ValueError):
            self.helper.selected_sha("push", {}, "not-a-sha")

    def test_jsonc_duplicates_and_unsafe_metadata(self):
        path = self.state / "input.json"
        path.write_text('{/*comment*/"url":"https://a/b", "array":[1,],}')
        self.assertEqual(
            self.helper.load(path, jsonc=True), {"url": "https://a/b", "array": [1]}
        )
        path.write_text('{"__proto__":1,"__proto__":2}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.helper.load(path)
        final = self.converted()
        next(iter(final["manifests"].values()))["file"]["source_location"] = (
            "/outside/file"
        )
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.helper.snapshot(final, {}, set(), {}, self.project, self.context)

    def test_atomic_write_failure_and_stale_output(self):
        path = self.state / "output.json"
        with (
            patch.object(
                self.helper.os, "replace", side_effect=OSError("publication failed")
            ),
            self.assertRaises(OSError),
        ):
            self.helper.atomic(path, {"data": 1})
        self.assertFalse(path.exists())
        self.assertFalse(list(self.state.glob(".pending-*")))
        self.helper.atomic(path, {"data": 1})
        with self.assertRaisesRegex(ValueError, "stale"):
            self.helper.atomic(path, {"data": 2})

    def patch_fixture(self):
        name = "patches/@scope%2Fapp@github%3Aorg%2Frepo#abcdef0.patch"
        self.manifest["patchedDependencies"] = {"app@1.0.0": name}
        self.fixture()
        shutil.rmtree(self.project / "node_modules")
        path = self.project / name
        path.parent.mkdir()
        path.write_text(
            "diff --git a/index.js b/index.js\n--- a/index.js\n+++ b/index.js\n@@ -1 +1 @@\n-old\n+new\n"
        )
        return name

    def run_with_install_stub(self, state, install):
        argv = [
            "helper.py",
            "run",
            "--state",
            str(state),
            "--workspace",
            str(self.project),
            "--wd",
            ".",
            "--sha",
            self.context["sha"],
            "--bun",
            "fixture-bun",
            "--syft",
            "fixture-syft",
        ]
        environment = {
            "REPOSITORY": "org/repo",
            "WORKFLOW": "CI",
            "JOB": "node-dependency-submission",
            "RUN_ID": "42",
            "REF": "refs/heads/dev",
            "GITHUB_OUTPUT": str(state / "outputs"),
        }

        def execute(command, run_state, cwd, output=None):
            if command[0] == "/usr/bin/git":
                return (self.context["sha"] + "\n").encode()
            if command[0] == "fixture-bun" and command[1] == "install":
                self.assertIn("--frozen-lockfile", command)
                self.assertIn("--ignore-scripts", command)
                install(cwd)
                return b"installed"
            if output is not None:
                output.write_text("{}")
            return b"{}"

        with (
            patch.object(sys, "argv", argv),
            patch.dict(os.environ, environment),
            patch.object(self.helper, "execute", side_effect=execute),
            patch.object(
                self.helper, "finish", return_value="fixture.spdx.json"
            ) as finish,
        ):
            self.helper.main()
            finish.assert_called_once()

    def test_actual_run_stages_patch_inputs_before_install(self):
        name = self.patch_fixture()
        state = self.state / "run"
        state.mkdir(mode=0o700)
        expected = self.helper.input_hashes(
            self.project, ["package.json", "bun.lock", name]
        )
        (self.project / "bunfig.toml").write_text('preload = ["consumer.js"]\n')

        def install(project):
            self.assertEqual(self.helper.input_hashes(project, expected), expected)
            self.assertFalse((project / "bunfig.toml").exists())
            self.assertEqual(
                (project / name).read_bytes(), (self.project / name).read_bytes()
            )

        self.run_with_install_stub(state, install)
        self.assertEqual(self.helper.input_hashes(self.project, expected), expected)

    def test_actual_run_creates_inventory_directory_for_empty_install(self):
        self.manifest = {"name": "fixture"}
        self.entries = {}
        self.fixture()
        state = self.state / "run"
        state.mkdir(mode=0o700)
        self.run_with_install_stub(state, lambda project: None)
        self.assertTrue((state / "project/node_modules").is_dir())
        self.assertTrue((self.project / "node_modules").is_dir())

    def test_actual_run_rejects_changed_manifest_lock_or_patch(self):
        name = self.patch_fixture()
        for index, target in enumerate(("package.json", "bun.lock", name)):
            state = self.state / ("run-" + str(index))
            state.mkdir(mode=0o700)

            def install(project, target=target):
                path = project / target
                path.write_bytes(path.read_bytes() + b"\n")

            with (
                self.subTest(target=target),
                self.assertRaisesRegex(ValueError, "installation inputs changed"),
            ):
                self.run_with_install_stub(state, install)

    def test_actual_run_rejects_unsafe_or_missing_patch_inputs(self):
        self.patch_fixture()
        for index, value in enumerate(
            (
                "../escape.patch",
                "/escape.patch",
                "patches/a\nb.patch",
                "bunfig.toml",
                "node_modules/a/package.json",
                "patches",
                "patches/missing.patch",
            )
        ):
            self.manifest["patchedDependencies"] = {"app@1.0.0": value}
            self.fixture()
            shutil.rmtree(self.project / "node_modules")
            state = self.state / ("unsafe-" + str(index))
            state.mkdir(mode=0o700)

            def install(_):
                self.fail("unsafe patch reached Bun installation")

            with (
                self.subTest(value=value),
                self.assertRaises((ValueError, FileNotFoundError)),
            ):
                self.run_with_install_stub(state, install)
        outside = self.state / "outside.patch"
        outside.write_text("outside")
        link = self.project / "patches/escape.patch"
        link.symlink_to(outside)
        self.manifest["patchedDependencies"] = {"app@1.0.0": "patches/escape.patch"}
        self.fixture()
        shutil.rmtree(self.project / "node_modules")
        state = self.state / "symlink"
        state.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.run_with_install_stub(state, install)

    def test_environment_is_allowlisted(self):
        with patch.dict(
            os.environ,
            {
                "NODE_OPTIONS": "--require=evil",
                "BUN_OPTIONS": "--preload=evil",
                "SYFT_CONFIG": "evil",
                "GITHUB_TOKEN": "secret",
            },
        ):
            environment = self.helper.safe_env(self.state)
        for name in ("NODE_OPTIONS", "BUN_OPTIONS", "SYFT_CONFIG", "GITHUB_TOKEN"):
            self.assertNotIn(name, environment)

    def test_warning_failure_and_exact_conversion_notice(self):
        for stderr, code in (
            (b"warning: missing selected package", 0),
            (b"", 1),
            (b"error: skipped", 0),
        ):
            with (
                patch.object(
                    self.helper.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], code, b"{}", stderr),
                ),
                self.assertRaises(ValueError),
            ):
                self.helper.execute(["bun", "pm"], self.state, self.project)
        notice = b"[0000]  WARN convert is an experimental feature, run `syft convert -h` for help\n"
        with patch.object(
            self.helper.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, b"{}", notice),
        ):
            self.assertEqual(
                self.helper.execute(["syft", "convert"], self.state, self.project),
                b"{}",
            )
        with (
            patch.object(
                self.helper.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(
                    [], 0, b"{}", notice + b"warning: incomplete\n"
                ),
            ),
            self.assertRaises(ValueError),
        ):
            self.helper.execute(["syft", "convert"], self.state, self.project)

    def test_cleanup_partial_initialization_and_symlink(self):
        code = textwrap.dedent(
            WORKFLOW.read_text()
            .split("python3 -I - <<'CLEANUP_PY'\n")[1]
            .split("          CLEANUP_PY")[0]
        )
        target = Path(tempfile.mkdtemp(prefix="node-submission.", dir=self.state))
        (target / "partial").write_text("partial")

        def run_cleanup():
            return subprocess.run(
                [sys.executable, "-I", "-B", "-c", code],
                env={"STATE": str(target), "RUNNER_TEMP": str(self.state)},
                capture_output=True,
                timeout=10,
                check=False,
            )

        self.assertEqual(run_cleanup().returncode, 0)
        self.assertFalse(target.exists())
        target.symlink_to(self.project)
        self.assertNotEqual(run_cleanup().returncode, 0)
        self.assertTrue(self.project.exists())

    @unittest.skipUnless(shutil.which("node"), "Node is required for publisher checks")
    def test_actual_publisher_rejects_tampering_and_api_failure(self):
        step = (
            WORKFLOW.read_text()
            .split("      - name: Submit validated snapshot\n")[1]
            .split("      - name:")[0]
        )
        code = textwrap.dedent(step.split("          script: |\n")[1])
        publication = self.state / "published"
        publication.mkdir()
        snapshot = publication / "snapshot.json"
        snapshot.write_text(json.dumps({"sha": "a" * 40}))
        receipt = {
            "sha": "a" * 40,
            "sha256": self.helper.hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        }
        (publication / "receipt.json").write_text(json.dumps(receipt))
        wrapper = """
        const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
        const github = {request: async (route, body) => {
          if (route !== 'POST /repos/{owner}/{repo}/dependency-graph/snapshots' ||
              body.owner !== 'org' || body.repo !== 'repo') throw new Error('wrong request');
          if (process.env.REJECT === '1') throw new Error('request rejected');
          return JSON.parse(process.env.RESPONSE);
        }};
        const context = {repo: {owner: 'org', repo: 'repo'}};
        new AsyncFunction('require', 'github', 'context', process.env.CODE)(require, github, context)
          .catch(error => { console.error(error.message); process.exitCode = 1; });
        """

        def run_publisher(response, *, reject=False):
            return subprocess.run(
                [shutil.which("node"), "-e", wrapper],
                env={
                    "STATE": str(self.state),
                    "SELECTED_SHA": "a" * 40,
                    "CODE": code,
                    "RESPONSE": json.dumps(response),
                    "REJECT": "1" if reject else "0",
                },
                capture_output=True,
                timeout=10,
                check=False,
            )

        valid = {"status": 201, "data": {"result": "SUCCESS"}}
        cases = [
            (valid, True),
            ({"status": 201, "data": {"result": "ACCEPTED"}}, True),
            (
                {
                    "status": 201,
                    "data": {
                        "result": "INVALID",
                        "message": "invalid snapshot fixture",
                    },
                },
                False,
            ),
            ({"status": 201, "data": {"result": "UNEXPECTED"}}, False),
            ({"status": 201, "data": {"result": None}}, False),
            ({"status": 201, "data": {"result": 1}}, False),
            ({"status": 201, "data": {}}, False),
            ({"status": 201}, False),
            ({"status": 201, "data": None}, False),
            ({"status": 500, "data": {"result": "SUCCESS"}}, False),
            ({"status": 202, "data": {"result": "ACCEPTED"}}, False),
        ]
        for response, accepted in cases:
            with self.subTest(response=response):
                completed = run_publisher(response)
                self.assertEqual(completed.returncode == 0, accepted)
                if (response.get("data") or {}).get("result") == "INVALID":
                    self.assertIn(b"INVALID", completed.stderr)
                    self.assertIn(b"invalid snapshot fixture", completed.stderr)
        completed = run_publisher(valid, reject=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(b"request rejected", completed.stderr)
        snapshot.write_text(json.dumps({"sha": "b" * 40}))
        completed = run_publisher(valid)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn(b"snapshot publication validation failed", completed.stderr)

    @unittest.skipUnless(
        shutil.which("bun"), "Bun is required for non-execution checks"
    )
    def test_native_install_inventory_do_not_execute_scripts_or_preloads(self):
        bun = shutil.which("bun")
        self.manifest = {
            "name": "fixture",
            "scripts": {"preinstall": "touch lifecycle-sentinel"},
        }
        self.manifest["dependencies"] = {"local": "file:../local"}
        local = self.state / "local"
        local.mkdir()
        (local / "package.json").write_text(
            json.dumps(
                {
                    "name": "local",
                    "version": "1.0.0",
                    "scripts": {"install": "touch dependency-sentinel"},
                }
            )
        )
        (self.project / "package.json").write_text(json.dumps(self.manifest))
        self.helper.configs(self.state)
        evil = self.state / "preload.js"
        sentinel = self.state / "preload-sentinel"
        evil.write_text(
            f"require('fs').writeFileSync({json.dumps(str(sentinel))}, 'ran');"
        )
        (self.project / "bunfig.toml").write_text(
            "preload = [" + json.dumps(str(evil)) + "]\n"
        )
        with patch.dict(
            os.environ,
            {
                "NODE_OPTIONS": "--require=" + str(evil),
                "BUN_OPTIONS": "--preload=" + str(evil),
            },
        ):
            self.helper.execute(
                [
                    bun,
                    "install",
                    "--config=" + str(self.state / "bunfig.toml"),
                    "--ignore-scripts",
                ],
                self.state,
                self.project,
            )
            self.helper.execute(
                [
                    bun,
                    "install",
                    "--config=" + str(self.state / "bunfig.toml"),
                    "--frozen-lockfile",
                    "--ignore-scripts",
                ],
                self.state,
                self.project,
            )
            output = self.helper.execute(
                [
                    bun,
                    "--config=" + str(self.state / "bunfig.toml"),
                    "pm",
                    "licenses",
                    "--prod",
                    "--json",
                ],
                self.state,
                self.project,
            )
        self.assertIsInstance(json.loads(output), dict)
        self.assertFalse(sentinel.exists())
        self.assertFalse((self.project / "lifecycle-sentinel").exists())
        self.assertFalse((local / "dependency-sentinel").exists())

    def assert_empty_actual_conversion(self, dev_only):
        self.manifest = {"name": "fixture", "dependencies": {}}
        self.entries = {}
        if dev_only:
            self.manifest["devDependencies"] = {"dev": "1.0.0"}
            self.entries = {"dev": ["dev@1.0.0", "", {}, "sha512-AAAA"]}
        self.fixture()
        (self.project / "node_modules").mkdir(exist_ok=True)
        self.helper.configs(self.state)
        inventory = self.helper.execute(
            [
                shutil.which("bun"),
                "--config=" + str(self.state / "bunfig.toml"),
                "pm",
                "licenses",
                "--prod",
                "--json",
            ],
            self.state,
            self.project,
        )
        self.assertEqual(json.loads(inventory), {})
        syft = os.environ["SUBMISSION_TEST_SYFT"]
        raw = self.helper.execute(
            [
                syft,
                "scan",
                "dir:" + str(self.project),
                "--config",
                str(self.state / "syft.yaml"),
                "--source-name",
                "fixture",
                "--source-version",
                self.context["sha"],
                "--exclude",
                self.helper.EXCLUDE,
                "-o",
                "syft-json",
            ],
            self.state,
            self.state,
        )
        (self.state / "raw.json").write_bytes(raw)
        (self.state / "inventory.json").write_bytes(inventory)
        (self.state / "inventory.stderr").write_bytes(b"")
        (self.state / "context.json").write_text(json.dumps(self.context))
        args = argparse.Namespace(
            state=str(self.state),
            project=str(self.project),
            source=str(self.project),
            syft=syft,
            raw=str(self.state / "raw.json"),
            inventory=str(self.state / "inventory.json"),
            inventory_stderr=str(self.state / "inventory.stderr"),
            context=str(self.state / "context.json"),
        )
        self.helper.finish(args)
        self.assertNotIn(
            "manifests", self.helper.load(self.state / "converted.github.json")
        )
        final = self.helper.load(self.state / "published/snapshot.json")
        self.assertEqual(set(final["manifests"]), {"web/bun.lock"})
        self.assertEqual(final["manifests"]["web/bun.lock"]["resolved"], {})

    @unittest.skipUnless(
        shutil.which("bun") and os.environ.get("SUBMISSION_TEST_SYFT"),
        "Bun and released Syft are required for empty-inventory conversion",
    )
    def test_actual_dev_only_inventory_without_other_findings(self):
        self.assert_empty_actual_conversion(dev_only=True)

    @unittest.skipUnless(
        shutil.which("bun") and os.environ.get("SUBMISSION_TEST_SYFT"),
        "Bun and released Syft are required for empty-inventory conversion",
    )
    def test_actual_dependency_empty_inventory_without_other_findings(self):
        self.assert_empty_actual_conversion(dev_only=False)

    @unittest.skipUnless(
        os.environ.get("SUBMISSION_TEST_SYFT"),
        "Set SUBMISSION_TEST_SYFT to a released Syft binary",
    )
    def test_actual_syft_conversion_and_atomic_publication(self):
        self.manifest["dependencies"]["shared"] = "1.0.0"
        self.entries["app/shared"] = copy.deepcopy(self.entries["shared"])
        self.fixture()
        for relative_path, action in (
            (".github/workflows/first-party.yml", "actions/checkout"),
            ("node_modules/dev/.github/workflows/bundled.yml", "bundled/action"),
        ):
            path = self.project / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "name: fixture\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: " + action + "@v1\n"
            )
        _, _, edges = self.helper.graph(self.project)
        self.helper.configs(self.state)
        raw = json.loads(
            self.helper.execute(
                [
                    os.environ["SUBMISSION_TEST_SYFT"],
                    "scan",
                    "dir:" + str(self.project),
                    "--config",
                    str(self.state / "syft.yaml"),
                    "--source-name",
                    "fixture",
                    "--source-version",
                    self.context["sha"],
                    "--exclude",
                    self.helper.EXCLUDE,
                    "-o",
                    "syft-json",
                ],
                self.state,
                self.state,
            )
        )
        shared = next(
            p for p in raw["artifacts"] if p["type"] == "npm" and p["name"] == "shared"
        )
        app = next(
            p for p in raw["artifacts"] if p["type"] == "npm" and p["name"] == "app"
        )
        app["purl"] += "?vcs_url=https%3A%2F%2Fexample.com%2Frepo"
        action = next(
            p
            for p in raw["artifacts"]
            if p["purl"].startswith("pkg:github/actions/checkout@")
        )
        raw["artifactRelationships"].extend(
            [
                {
                    "parent": shared["id"],
                    "child": action["id"],
                    "type": "dependency-of",
                },
                {"parent": action["id"], "child": app["id"], "type": "dependency-of"},
            ]
        )
        for name, value in (
            ("raw.json", raw),
            ("inventory.json", self.inventory(edges)),
            ("context.json", self.context),
        ):
            (self.state / name).write_text(json.dumps(value))
        (self.state / "inventory.stderr").write_bytes(b"")
        args = argparse.Namespace(
            state=str(self.state),
            project=str(self.project),
            source=str(self.project),
            syft=os.environ["SUBMISSION_TEST_SYFT"],
            raw=str(self.state / "raw.json"),
            inventory=str(self.state / "inventory.json"),
            context=str(self.state / "context.json"),
            inventory_stderr=str(self.state / "inventory.stderr"),
        )
        artifact = self.helper.finish(args)
        self.assertTrue((self.state / "published" / artifact).is_file())
        final = self.helper.load(self.state / "published/snapshot.json")
        self.assertEqual(final["sha"], self.context["sha"])
        self.assertIn("web/.github/workflows/first-party.yml", final["manifests"])
        self.assertFalse(any("bundled" in key for key in final["manifests"]))
        npm = final["manifests"]["web/bun.lock"]["resolved"]
        self.assertEqual(npm["pkg:npm/shared@1.0.0"]["relationship"], "direct")
        self.assertIn(action["purl"], npm["pkg:npm/app@1.0.0"]["dependencies"])
        self.assertEqual(npm["pkg:npm/app@1.0.0"]["package_url"], app["purl"])
        actions = final["manifests"]["web/.github/workflows/first-party.yml"][
            "resolved"
        ]
        self.assertEqual(
            actions[action["purl"]]["dependencies"], ["pkg:npm/shared@1.0.0"]
        )
        self.assertEqual(
            len(npm),
            len(
                {
                    (p["name"], p["version"])
                    for p in self.helper.load(self.state / "corrected.syft.json")[
                        "artifacts"
                    ]
                    if p["type"] == "npm"
                }
            ),
        )
        with self.assertRaisesRegex(ValueError, "stale publication"):
            self.helper.finish(args)
        failed = self.state / "failed-publication"
        failed.mkdir(mode=0o700)
        self.helper.configs(failed)
        args.state = str(failed)
        replace = os.replace

        def reject_publication(source, destination):
            if Path(destination).name == "published":
                raise OSError("publication rename failed")
            replace(source, destination)

        with (
            patch.object(self.helper.os, "replace", side_effect=reject_publication),
            self.assertRaisesRegex(OSError, "publication rename failed"),
        ):
            self.helper.finish(args)
        self.assertFalse((failed / "published").exists())
        self.assertFalse((failed / "publication-pending").exists())
        cli_state = self.state / "cli-run"
        cli_state.mkdir(mode=0o700)
        helper_path = cli_state / "helper.py"
        subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "--extract",
                str(helper_path),
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                str(helper_path),
                "finish",
                "--state",
                str(cli_state),
                "--project",
                str(self.project),
                "--source",
                str(self.project),
                "--raw",
                args.raw,
                "--inventory",
                args.inventory,
                "--inventory-stderr",
                args.inventory_stderr,
                "--context",
                args.context,
                "--syft",
                args.syft,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        cli_snapshot = self.helper.load(cli_state / "published/snapshot.json")
        self.assertEqual(cli_snapshot["manifests"]["web/bun.lock"]["resolved"], npm)

    def test_failed_conversion_and_missing_warning_file_never_publish(self):
        raw = self.fixture()
        _, _, edges = self.helper.graph(self.project)
        self.helper.configs(self.state)
        for name, value in (
            ("raw.json", raw),
            ("inventory.json", self.inventory(edges)),
            ("context.json", self.context),
        ):
            (self.state / name).write_text(json.dumps(value))
        args = argparse.Namespace(
            state=str(self.state),
            project=str(self.project),
            source=str(self.project),
            syft="not-used",
            raw=str(self.state / "raw.json"),
            inventory=str(self.state / "inventory.json"),
            context=str(self.state / "context.json"),
            inventory_stderr=str(self.state / "inventory.stderr"),
        )
        with self.assertRaises(FileNotFoundError):
            self.helper.finish(args)
        (self.state / "inventory.stderr").write_bytes(b"warning: missing package")
        with self.assertRaisesRegex(ValueError, "warning"):
            self.helper.finish(args)
        (self.state / "inventory.stderr").write_bytes(b"")
        with (
            patch.object(
                self.helper, "execute", side_effect=ValueError("conversion failed")
            ),
            self.assertRaisesRegex(ValueError, "conversion failed"),
        ):
            self.helper.finish(args)
        self.assertFalse((self.state / "published").exists())


def extract(destination):
    destination = Path(destination)
    with destination.open("x") as stream:
        stream.write(helper_source())


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--extract":
        extract(sys.argv[2])
    else:
        unittest.main()
