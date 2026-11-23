import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "lib-dead-code.py"
spec = importlib.util.spec_from_file_location("lib_dead_code", SCRIPT)
dead = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dead)

LIB = "github.com/nics-dp/libdcf"


class AggregateTests(unittest.TestCase):
    def test_function_unreached_by_every_run_is_reported(self):
        key = (f"{LIB}/utils", "Unused")
        runs = [
            ({key: ("a.go", 1)}, {f"{LIB}/utils"}),
            ({key: ("a.go", 1)}, {f"{LIB}/utils"}),
        ]
        found, _ = dead.aggregate(runs, [f"{LIB}/utils"])
        self.assertEqual(list(found), [key])

    def test_function_reached_by_one_run_is_not_reported(self):
        key = (f"{LIB}/utils", "UsedByTests")
        runs = [({key: ("a.go", 1)}, {f"{LIB}/utils"}), ({}, {f"{LIB}/utils"})]
        found, _ = dead.aggregate(runs, [f"{LIB}/utils"])
        self.assertEqual(found, {})

    def test_run_that_never_loaded_the_package_does_not_save_the_function(self):
        key = (f"{LIB}/utils", "Unused")
        runs = [({key: ("a.go", 1)}, {f"{LIB}/utils"}), ({}, {f"{LIB}/other"})]
        found, _ = dead.aggregate(runs, [f"{LIB}/utils", f"{LIB}/other"])
        self.assertEqual(list(found), [key])

    def test_package_no_run_loads_is_reported_as_a_whole(self):
        runs = [({}, {f"{LIB}/utils"})]
        _, unimported = dead.aggregate(runs, [f"{LIB}/utils", f"{LIB}/settle"])
        self.assertEqual(unimported, [f"{LIB}/settle"])


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
            text, "go 1.27.0\n\ntoolchain go1.27.4\n\nuse (\n\t/src/a\n\t/src/b\n)\n"
        )


class ReportTests(unittest.TestCase):
    def test_long_report_is_truncated_below_the_issue_body_limit(self):
        dead_funcs = {(f"{LIB}/p{i}", f"F{i}"): ("", 0) for i in range(5000)}
        body, full = dead.report(
            "nics-dp", pathlib.Path("/src"), {}, [LIB], [], dead_funcs, [], []
        )
        self.assertLessEqual(len(body), dead.BODY_LIMIT + 200)
        self.assertIn("已截斷", body)
        self.assertGreater(len(full), len(body))


if __name__ == "__main__":
    unittest.main()
