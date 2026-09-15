"""Run meta's configured OpenGrep policy against temporary regression fixtures.

Run with: python3 .github/tests/test_opengrep_renovate.py
The scanner and registry pack are resolved exactly as in the meta mise task.
"""

import copy
import json
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGE = "meta-renovate-minimum-release-age"
DEFAULT = "meta-renovate-missing-default-age"
ESCAPED = "meta-renovate-escaped-key"
INJECTION = "yaml.github-actions.security.run-shell-injection.run-shell-injection"
UPSTREAM = (
    "package_managers.renovate.renovate-missing-minimum-release-age."
    "renovate-missing-minimum-release-age"
)
PRESET = "github>nics-dp/meta:renovate-preset"


def task_info(name):
    return json.loads(
        subprocess.check_output(
            ["mise", "tasks", "info", name, "--json"], cwd=ROOT, text=True
        )
    )


class OpenGrepRenovateTests(unittest.TestCase):
    def test_meta_policy_and_remaining_baseline(self):
        task = task_info("ci:meta-semgrep")
        shared = task_info("ci:semgrep")
        self.assertEqual(task["tools"], shared["tools"], "Keep scanner pins aligned")
        self.assertIn("ci:meta-semgrep", task_info("ci")["depends"])
        command = shlex.split(task["run"][0])
        self.assertEqual(command.count("--exclude-rule"), 1)
        self.assertEqual(command[command.index("--exclude-rule") + 1], UPSTREAM)
        self.assertIn("p/ci", command)
        self.assertIn("--error", command)
        self.assertIn("--enable-nosem", command)
        self.assertEqual(command[-1], ".")
        command.remove(".")
        rules_index = command.index(".opengrep/renovate.yml")
        command[rules_index] = str(ROOT / command[rules_index])
        command += ["--json", "--no-rewrite-rule-ids", "--no-git-ignore"]
        tools = [f"{name}@{version}" for name, version in task["tools"].items()]

        config = json.loads((ROOT / "renovate.json").read_text())
        preset = json.loads((ROOT / "renovate-preset.json").read_text())
        self.assertEqual(config["extends"], [PRESET])
        self.assertEqual(preset["minimumReleaseAge"], "7 days")
        inherited = [r for r in config["packageRules"] if "minimumReleaseAge" not in r]
        self.assertEqual(
            {r["groupName"] for r in inherited}, {"go analysis tools", "parlay pins"}
        )
        self.assertTrue(all("minimumReleaseAge" not in r for r in inherited))

        with tempfile.TemporaryDirectory(prefix="meta-opengrep-") as directory:
            fixtures = Path(directory)
            expected = {}

            def add_raw(path, source, rules=()):
                target = fixtures / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
                expected[path] = set(rules)

            def add(path, document, rules=()):
                add_raw(path, json.dumps(document, indent=2) + "\n", rules)

            add("actual/renovate.json", config)
            add("actual/renovate-preset.json", preset)
            add(
                "actual/configs/renovate.json",
                json.loads((ROOT / "configs/renovate.json").read_text()),
            )
            for age in ("3 days", "4 days", "7 days", "30 days"):
                add(
                    f"accepted-{age}/renovate.json",
                    {
                        "minimumReleaseAge": age,
                        "packageRules": [
                            {"matchPackageNames": ["inherited"]},
                            {
                                "matchPackageNames": ["explicit"],
                                "minimumReleaseAge": age,
                            },
                        ],
                    },
                )
            for index, age in enumerate(
                (
                    "0 days",
                    "1 day",
                    "2 days",
                    False,
                    None,
                    0,
                    "",
                    "disabled",
                    "2.5 days",
                )
            ):
                add(
                    f"bad-default-{index}/renovate.json",
                    {"minimumReleaseAge": age},
                    (AGE,),
                )
                for field in ("packageRules", "npm"):
                    override = {"minimumReleaseAge": age}
                    add(
                        f"bad-{field}-{index}/renovate.json",
                        {
                            "minimumReleaseAge": "7 days",
                            field: [override] if field == "packageRules" else override,
                        },
                        (AGE,),
                    )
            add(
                "missing-default/renovate.json",
                {"packageRules": [{"matchPackageNames": ["example"]}]},
                (DEFAULT,),
            )
            add("empty/renovate.json", {}, (DEFAULT,))
            add(
                "unknown-preset/renovate.json",
                {"extends": ["config:recommended"]},
                (DEFAULT,),
            )
            no_preset = copy.deepcopy(config)
            del no_preset["extends"]
            add("removed-extends/renovate.json", no_preset, (DEFAULT,))
            ignored = copy.deepcopy(config)
            ignored["ignorePresets"] = [PRESET]
            add("ignored-preset/renovate.json", ignored, (DEFAULT,))
            add_raw(
                "escaped-ignore-presets/renovate.json",
                json.dumps(ignored).replace("ignorePresets", r"ignorePr\u0065sets"),
                (ESCAPED,),
            )
            add_raw(
                "escaped-description-value/renovate.json",
                r'{"minimumReleaseAge": "3 days", "description": "\u0041"}',
            )
            for index, extends in enumerate(
                ([PRESET, "github>example/other"], ["github>example/other", PRESET])
            ):
                changed = copy.deepcopy(config)
                changed["extends"] = extends
                add(f"additional-extends-{index}/renovate.json", changed, (DEFAULT,))
            for age in ("2 days", "3 days"):
                escaped = json.dumps({"minimumReleaseAge": age}).replace(
                    "minimumReleaseAge", r"minimumRelease\u0041ge"
                )
                self.assertEqual(json.loads(escaped)["minimumReleaseAge"], age)
                add_raw(
                    f"escaped-key-{age}/renovate.json",
                    escaped,
                    (DEFAULT, ESCAPED),
                )
                add_raw(
                    f"escaped-nested-key-{age}/renovate.json",
                    '{"minimumReleaseAge": "7 days", "packageRules": ['
                    + escaped
                    + "]}",
                    (ESCAPED,),
                )
            for age in (None, "2 days", False):
                changed = copy.deepcopy(preset)
                if age is None:
                    del changed["minimumReleaseAge"]
                else:
                    changed["minimumReleaseAge"] = age
                folder = f"bad-inherited-default-{age}"
                add(f"{folder}/renovate.json", config)
                add(
                    f"{folder}/renovate-preset.json",
                    changed,
                    (DEFAULT if age is None else AGE,),
                )
            for rule in inherited:
                for age in ("3 days", "2 days", False):
                    changed = copy.deepcopy(config)
                    for entry in changed["packageRules"]:
                        if entry.get("groupName") == rule["groupName"]:
                            entry["minimumReleaseAge"] = age
                    add(
                        f"override-{rule['groupName']}-{age}/renovate.json",
                        changed,
                        () if age == "3 days" else (AGE,),
                    )

            for filename in (
                "renovate.json",
                ".renovaterc.json",
                "renovate-preset.json",
            ):
                for index, prefix in enumerate(
                    (
                        "",
                        "// Renovate configuration\n",
                        "/* Renovate configuration */\n",
                    )
                ):
                    for age in ("2 days", "3 days"):
                        add_raw(
                            f"format-{index}-{age}/{filename}",
                            prefix + json.dumps({"minimumReleaseAge": age}),
                            (AGE,) if age == "2 days" else (),
                        )
                    add_raw(
                        f"format-missing-{index}/{filename}", prefix + "{}", (DEFAULT,)
                    )
                    add_raw(
                        f"format-inherited-{index}/{filename}",
                        prefix + json.dumps(config),
                    )

            workflow = fixtures / "injection/.github/workflows/test.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "on: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: echo '${{ github.event.pull_request.title }}'\n"
            )
            expected[str(workflow.relative_to(fixtures))] = {INJECTION}
            completed = subprocess.run(
                ["mise", "exec", *tools, "--", *command, str(fixtures)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
            details = completed.stdout + "\n" + completed.stderr
            self.assertEqual(completed.returncode, 1, details)
            report = json.loads(completed.stdout)
            self.assertEqual(report["errors"], [], details)
            scanned = {
                str(Path(path).relative_to(fixtures))
                for path in report["paths"]["scanned"]
            }
            self.assertEqual(scanned, set(expected), details)
            observed = {path: set() for path in expected}
            for finding in report["results"]:
                path = str(Path(finding["path"]).relative_to(fixtures))
                self.assertIn(path, expected, details)
                observed[path].add(finding["check_id"])
            for path, rules in expected.items():
                with self.subTest(path=path):
                    self.assertEqual(observed[path], rules, details)
            print(
                f"Checked {len(expected)} fixtures against meta's p/ci + local rules."
            )


if __name__ == "__main__":
    unittest.main()
