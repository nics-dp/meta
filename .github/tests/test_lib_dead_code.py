import contextlib
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "lib-dead-code.py"
spec = importlib.util.spec_from_file_location("lib_dead_code", SCRIPT)
dead = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dead)

LIB = "github.com/nics-dp/libdcf"


UTILS = f"{LIB}/utils"


class AggregateTests(unittest.TestCase):
    def test_function_unreached_by_every_run_is_reported(self):
        key = (UTILS, "Unused")
        runs = [
            ({key: ("/u/a.go", 1)}, {UTILS}, {"/u/a.go"}),
            ({key: ("/u/a.go", 1)}, {UTILS}, {"/u/a.go"}),
        ]
        found, _ = dead.aggregate(runs, [UTILS])
        self.assertEqual(list(found), [key])

    def test_function_reached_by_one_run_is_not_reported(self):
        key = (UTILS, "UsedByTests")
        runs = [
            ({key: ("/u/a.go", 1)}, {UTILS}, {"/u/a.go"}),
            ({}, {UTILS}, {"/u/a.go"}),
        ]
        found, _ = dead.aggregate(runs, [UTILS])
        self.assertEqual(found, {})

    def test_run_that_never_loaded_the_package_does_not_save_the_function(self):
        key = (UTILS, "Unused")
        runs = [
            ({key: ("/u/a.go", 1)}, {UTILS}, {"/u/a.go"}),
            ({}, {f"{LIB}/other"}, {"/o/b.go"}),
        ]
        found, _ = dead.aggregate(runs, [UTILS, f"{LIB}/other"])
        self.assertEqual(list(found), [key])

    def test_run_that_did_not_compile_the_file_does_not_save_the_function(self):
        # A production build loads the package but a test-only build tag keeps
        # testing.go out, so deadcode never judged the helper in that run.
        key = (UTILS, "TestHelper")
        runs = [
            ({key: ("/u/testing.go", 5)}, {UTILS}, {"/u/a.go", "/u/testing.go"}),
            ({}, {UTILS}, {"/u/a.go"}),
        ]
        found, _ = dead.aggregate(runs, [UTILS])
        self.assertEqual(list(found), [key])

    def test_package_no_run_loads_is_reported_as_a_whole(self):
        runs = [({}, {UTILS}, {"/u/a.go"})]
        _, unimported = dead.aggregate(runs, [UTILS, f"{LIB}/settle"])
        self.assertEqual(unimported, [f"{LIB}/settle"])


class ParseTests(unittest.TestCase):
    def test_null_output_means_nothing_unreachable(self):
        self.assertEqual(dead.parse_unreachable("null\n"), {})
        self.assertEqual(dead.parse_unreachable(""), {})

    def test_functions_are_keyed_by_package_and_name(self):
        out = '[{"Path":"p","Funcs":[{"Name":"F","Position":{"File":"/x/f.go","Line":3}}]}]'
        self.assertEqual(dead.parse_unreachable(out), {("p", "F"): ("/x/f.go", 3)})

    def test_only_http_404_counts_as_absent(self):
        self.assertTrue(dead.not_found("gh: Not Found (HTTP 404)"))
        self.assertTrue(dead.not_found("gh: This repository is empty. (HTTP 404)"))
        self.assertFalse(dead.not_found("gh: API rate limit exceeded (HTTP 403)"))
        self.assertFalse(dead.not_found("gh: Bad Gateway (HTTP 502)"))
        self.assertFalse(dead.not_found(None))


class GoEnvTests(unittest.TestCase):
    def test_owner_modules_are_private_and_existing_patterns_kept(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            env = dead.go_env({}, "nics-dp", "example.com/x")
        self.assertEqual(env, {"GOPRIVATE": "example.com/x,github.com/nics-dp"})

    def test_owner_pattern_is_not_added_twice(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            env = dead.go_env({}, "nics-dp", "github.com/nics-dp")
        self.assertEqual(env["GOPRIVATE"], "github.com/nics-dp")

    def test_go_git_calls_get_the_token_after_existing_config(self):
        with mock.patch.dict(os.environ, {"GH_TOKEN": "t"}, clear=True):
            env = dead.go_env({"GIT_CONFIG_COUNT": "1"}, "nics-dp", "")
            key, value = dead.auth_header()
        self.assertEqual(env["GIT_CONFIG_COUNT"], "2")
        self.assertEqual(env["GIT_CONFIG_KEY_1"], key)
        self.assertEqual(env["GIT_CONFIG_VALUE_1"], value)
        self.assertNotIn("GIT_CONFIG_KEY_0", env)


class PlanTests(unittest.TestCase):
    def test_library_repo_modules_are_not_consumers(self):
        src = pathlib.Path("/src")
        mods = {
            src / "libdcf": (LIB, set(), (), ()),
            src / "libdcf/test/integration": (f"{LIB}/test/integration", {LIB}, (), ()),
            src / "dcf-platform": ("dcf-platform", {LIB}, (), ()),
            src / "otel-bundle": ("otel-bundle", {"github.com/jackc/pgx/v5"}, (), ()),
        }
        lib_dirs, consumers, _ = dead.plan(mods, src, [LIB])
        self.assertEqual(lib_dirs, {LIB: src / "libdcf"})
        self.assertEqual(consumers, {"dcf-platform": src / "dcf-platform"})

    def test_library_test_support_is_left_out(self):
        self.assertTrue(dead.is_lib_test(f"{LIB}/test/mocks", [LIB]))
        self.assertTrue(dead.is_lib_test(f"{LIB}/test", [LIB]))
        self.assertFalse(dead.is_lib_test(f"{LIB}/testing", [LIB]))
        self.assertFalse(dead.is_lib_test(f"{LIB}/monitor/test", [LIB]))


class GoModTests(unittest.TestCase):
    def test_reads_module_requires_go_and_toolchain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "go.mod"
            path.write_text(
                "module dcf-platform\n\ngo 1.27.0\n\ntoolchain go1.27.4\n\n"
                f"require {LIB} v0.3.3\n\nrequire (\n\tgithub.com/nics-dp/ZenQuery v1.0.0 // indirect\n)\n",
                encoding="utf-8",
            )
            module, requires, go, toolchain = dead.read_go_mod(path)
        self.assertEqual(module, "dcf-platform")
        self.assertEqual(requires, {LIB, "github.com/nics-dp/ZenQuery"})
        self.assertEqual(go, (1, 27, 0))
        self.assertEqual(toolchain, (1, 27, 4))

    def test_workspace_takes_the_highest_go_line_and_toolchain(self):
        mods = {
            "a": ("a", set(), (1, 26, 0), (1, 26, 3)),
            "b": ("b", set(), (1, 27, 0), (1, 27, 4)),
        }
        self.assertEqual(
            dead.workspace_versions(mods, ["a", "b"]), ((1, 27, 0), (1, 27, 4))
        )

    def test_go_work_lists_members_with_go_and_toolchain_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = dead.write_go_work(
                ["/src/b", "/src/a"], pathlib.Path(tmp), (1, 27, 0), (1, 27, 4)
            )
            text = target.read_text(encoding="utf-8")
        self.assertEqual(
            text,
            'go 1.27.0\n\ntoolchain go1.27.4\n\nuse (\n\t"/src/a"\n\t"/src/b"\n)\n',
        )

    def test_go_work_keeps_a_path_with_spaces_as_one_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = dead.write_go_work(
                ["/tmp/dead code/src/libdcf"], pathlib.Path(tmp), (1, 27, 0), (1, 27, 0)
            )
            text = target.read_text(encoding="utf-8")
        self.assertIn('\t"/tmp/dead code/src/libdcf"\n', text)


class UncompiledTests(unittest.TestCase):
    def test_file_no_build_compiled_is_listed(self):
        packages = {UTILS: {"/u/a.go", "/u/cgroup_linux.go"}}
        runs = [({}, {UTILS}, {"/u/a.go"}), ({}, {UTILS}, {"/u/a.go"})]
        self.assertEqual(dead.uncompiled(packages, runs, []), ["/u/cgroup_linux.go"])

    def test_unimported_package_files_are_not_listed_again(self):
        packages = {f"{LIB}/settle": {"/s/s.go"}}
        self.assertEqual(dead.uncompiled(packages, [], [f"{LIB}/settle"]), [])


class ReportTests(unittest.TestCase):
    def test_long_report_is_truncated_below_the_issue_body_limit(self):
        dead_funcs = {(f"{LIB}/p{i}", f"F{i}"): ("", 0) for i in range(5000)}
        body, full = dead.report(
            "nics-dp", pathlib.Path("/src"), {}, [LIB], [], dead_funcs, [], []
        )
        self.assertLessEqual(len(body), dead.BODY_LIMIT + 200)
        self.assertIn("已截斷", body)
        self.assertGreater(len(full), len(body))

    def test_empty_result_with_skips_does_not_claim_every_function_is_used(self):
        skipped = [("`dcf-service` test build", "x.go:1: missing method")]
        body, _ = dead.report(
            "nics-dp", pathlib.Path("/src"), {}, [LIB], [], {}, [], skipped
        )
        self.assertNotIn("每個 library 函式都有 consumer 用到", body)
        self.assertIn("成功分析的 build", body)

    def test_empty_result_without_skips_says_every_function_is_used(self):
        body, _ = dead.report(
            "nics-dp", pathlib.Path("/src"), {}, [LIB], [], {}, [], []
        )
        self.assertIn("每個 library 函式都有 consumer 用到", body)

    def test_other_platform_files_are_listed_with_a_qualified_conclusion(self):
        body, _ = dead.report(
            "nics-dp", pathlib.Path("/src"), {}, [LIB], [], {}, [], [],
            ["`libdcf/utils/cgroup_cpu_other.go`"],
        )  # fmt: skip
        self.assertIn("只在其他平台編譯的檔案", body)
        self.assertIn("cgroup_cpu_other.go", body)
        self.assertNotIn("## 未分析", body)
        self.assertIn("其他平台編譯的檔案除外", body)


class TestHookTests(unittest.TestCase):
    def test_for_test_functions_and_methods_are_test_hooks(self):
        self.assertTrue(dead.is_test_hook("SetNatsDisabledForTest"))
        self.assertTrue(dead.is_test_hook("UploadRegistry.ReleaseFileForTest"))
        self.assertFalse(dead.is_test_hook("ForTestOnly"))
        self.assertFalse(dead.is_test_hook("Compiler.SetAutoID"))


class PlatformFilesTests(unittest.TestCase):
    @staticmethod
    def ok(stdout):
        return mock.Mock(returncode=0, stdout=stdout)

    def test_only_files_the_host_never_compiles_are_platform_files(self):
        host = self.ok("/l/utils\tcgroup_cpu_linux.go,hash.go\t\n")
        other = self.ok("/l/utils\tcgroup_cpu_other.go,hash.go\t\n")
        failed = mock.Mock(returncode=1, stdout="", stderr="boom")
        # host and host with cgo (plain, -tags each), then linux, darwin
        # (fails), windows.
        effects = [
            host, self.ok(""), host, self.ok(""),
            host, self.ok(""), failed, other, self.ok(""),
        ]  # fmt: skip
        with mock.patch.object(dead, "run", side_effect=effects) as run:
            files = dead.platform_files([LIB], {}, ".", "test")
        self.assertEqual(files, {os.path.realpath("/l/utils/cgroup_cpu_other.go")})
        envs = [call.args[1] for call in run.call_args_list]
        self.assertEqual(
            [e.get("GOOS") for e in envs],
            [None, None, None, None, "linux", "linux", "darwin", "windows", "windows"],
        )
        self.assertEqual(
            [e.get("CGO_ENABLED") for e in envs[:4]], [None, None, "1", "1"]
        )
        self.assertIn("-tags", run.call_args_list[1].args[0])

    def test_host_cgo_files_are_not_platform_files_under_cgo_disabled(self):
        # CGO_ENABLED=0 on the host drops cgo_linux.go from its own listing;
        # the host-with-cgo listing and the linux listing both carry it.
        host = self.ok("/l/db\tdb.go\t\n")
        host_cgo = self.ok("/l/db\tdb.go\tcgo_linux.go\n")
        effects = [
            host, self.ok(""), host_cgo, self.ok(""),
            host_cgo, self.ok(""), self.ok(""), self.ok(""), self.ok(""), self.ok(""),
        ]  # fmt: skip
        env = {"CGO_ENABLED": "0"}
        with mock.patch.object(dead, "run", side_effect=effects):
            self.assertEqual(dead.platform_files([LIB], env, ".", "test"), set())

    def test_failed_host_listing_classifies_nothing(self):
        failed = mock.Mock(returncode=1, stdout="", stderr="boom")
        with mock.patch.object(dead, "run", return_value=failed):
            self.assertEqual(dead.platform_files([LIB], {}, ".", "test"), set())

    def test_failed_host_cgo_listing_classifies_nothing(self):
        other = self.ok("/l/utils\tcgroup_cpu_other.go\t\n")
        failed = mock.Mock(returncode=1, stdout="", stderr="boom")
        effects = [self.ok(""), self.ok(""), failed] + [other] * 6
        with mock.patch.object(dead, "run", side_effect=effects):
            self.assertEqual(dead.platform_files([LIB], {}, ".", "test"), set())


class MissingLibraryTests(unittest.TestCase):
    def test_unfetchable_library_writes_a_skipped_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = pathlib.Path(tmp) / "report.md"
            argv = [
                "lib-dead-code.py", "--owner", "nics-dp", "--libs", LIB,
                "--work", str(pathlib.Path(tmp) / "w"), "--report", str(report),
                "--repos", "libdcf",
            ]  # fmt: skip
            out = io.StringIO()
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    dead,
                    "fetch",
                    return_value=({}, [("libdcf", "gh: Bad Gateway (HTTP 502)")]),
                ),
                contextlib.redirect_stdout(out),
            ):
                dead.main()
            body = report.read_text(encoding="utf-8")
        self.assertEqual(
            out.getvalue().split(), ["functions=0", "packages=0", "skipped=2"]
        )
        self.assertIn("HTTP 502", body)
        self.assertIn(f"library `{LIB}`", body)
        self.assertNotIn("每個 library 函式都有 consumer 用到", body)

    def test_unlistable_installation_repositories_write_a_skipped_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = pathlib.Path(tmp) / "report.md"
            argv = [
                "lib-dead-code.py", "--owner", "nics-dp", "--libs", LIB,
                "--work", str(pathlib.Path(tmp) / "w"), "--report", str(report),
            ]  # fmt: skip
            out = io.StringIO()
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    dead,
                    "list_repositories",
                    return_value=([], "gh: Bad Gateway (HTTP 502)"),
                ),
                contextlib.redirect_stdout(out),
            ):
                dead.main()
            body = report.read_text(encoding="utf-8")
        self.assertEqual(
            out.getvalue().split(), ["functions=0", "packages=0", "skipped=2"]
        )
        self.assertIn("installation repositories", body)
        self.assertIn("HTTP 502", body)


class LibPackagesTests(unittest.TestCase):
    def test_listing_failure_is_returned_not_fatal(self):
        failed = mock.Mock(
            returncode=1, stderr="go: cannot find module providing package\n"
        )
        with mock.patch.object(dead, "run", return_value=failed):
            packages, err = dead.lib_packages([LIB], {}, ".")
        self.assertEqual(packages, {})
        self.assertIn("cannot find module", err)

    def test_walk_finds_packages_go_list_drops(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            files = {
                "go.mod": f"module {LIB}\n",
                "a/a.go": "package a\n",
                "a/a_test.go": "package a\n",
                "onlytest/h.go": "//go:build test\n\npackage onlytest\n",
                "gen/main.go": "package main\n",
                "tool/gen.go": "//go:build ignore\n\npackage main\n",
                "test/integration/go.mod": "module x\n",
                "test/integration/i.go": "package integration\n",
                "_scratch/s.go": "package s\n",
                "a/_old.go": "package a\n",
                "a/.hidden.go": "package a\n",
                "onlyignored/_x.go": "package onlyignored\n",
                "a/mock_gen.go": (
                    "// Code generated by MockGen. DO NOT EDIT.\n\n"
                    "//go:build integration\n\npackage a\n"
                ),
                "testdata/t.go": "package t\n",
            }
            for name, body in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(body, encoding="utf-8")
            found = dead.walk_packages({LIB: root})
            real = pathlib.Path(os.path.realpath(root))
        self.assertEqual(
            found,
            {
                f"{LIB}/a": {str(real / "a/a.go")},
                f"{LIB}/onlytest": {str(real / "onlytest/h.go")},
            },
        )


if __name__ == "__main__":
    unittest.main()
