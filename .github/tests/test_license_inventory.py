import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "license-inventory.py"
spec = importlib.util.spec_from_file_location("license_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)

DENY = {"GPL-2.0-only", "SSPL-1.0"}


class AllowedTests(unittest.TestCase):
    def test_single_licenses(self):
        self.assertTrue(inventory.allowed("MIT", DENY))
        self.assertFalse(inventory.allowed("GPL-2.0-only", DENY))
        self.assertTrue(inventory.allowed("GPL-2.0-or-later", DENY))

    def test_deprecated_bare_id_counts_as_only(self):
        self.assertFalse(inventory.allowed("GPL-2.0", DENY))
        self.assertFalse(inventory.allowed("MIT AND GPL-2.0", DENY))
        self.assertTrue(inventory.allowed("GPL-2.0+", DENY))
        self.assertTrue(inventory.allowed("GPL-3.0", DENY))

    def test_identifiers_match_without_regard_to_case(self):
        self.assertFalse(inventory.allowed("MIT AND sspl-1.0", DENY))
        self.assertFalse(inventory.allowed("gpl-2.0", DENY))
        self.assertFalse(inventory.allowed("MIT", {"mit"}))
        self.assertTrue(inventory.allowed("gpl-2.0-or-later", DENY))

    def test_unknown_values_are_not_denied(self):
        for value in ("", "NOASSERTION", "LicenseRef-NVIDIA-Proprietary", None):
            self.assertTrue(inventory.allowed(value, DENY), value)

    def test_or_passes_when_any_operand_is_allowed(self):
        self.assertTrue(inventory.allowed("MIT OR GPL-2.0-only", DENY))
        self.assertTrue(inventory.allowed("(GPL-2.0-only OR Apache-2.0)", DENY))
        self.assertFalse(inventory.allowed("GPL-2.0-only OR SSPL-1.0", DENY))

    def test_and_fails_when_any_operand_is_denied(self):
        self.assertFalse(inventory.allowed("MIT AND GPL-2.0-only", DENY))
        self.assertTrue(inventory.allowed("MIT AND Apache-2.0 AND BSD-3-Clause", DENY))

    def test_precedence_and_parentheses(self):
        # AND binds tighter than OR: MIT OR (GPL AND SSPL) -> allowed via MIT.
        self.assertTrue(inventory.allowed("MIT OR GPL-2.0-only AND SSPL-1.0", DENY))
        self.assertFalse(inventory.allowed("(MIT OR GPL-2.0-only) AND SSPL-1.0", DENY))

    def test_with_exception_follows_base_license(self):
        self.assertFalse(inventory.allowed("GPL-2.0-only WITH Classpath-exception-2.0", DENY))
        self.assertTrue(inventory.allowed("Apache-2.0 WITH LLVM-exception", DENY))

    def test_truncated_expression_does_not_raise(self):
        self.assertTrue(inventory.allowed("MIT AND", DENY))


class ParseListTests(unittest.TestCase):
    def test_trims_and_drops_empty(self):
        self.assertEqual(inventory.parse_list(" A, B ,,C "), {"A", "B", "C"})


if __name__ == "__main__":
    unittest.main()
