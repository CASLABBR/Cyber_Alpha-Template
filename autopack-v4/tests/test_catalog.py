import importlib.util
import sys
import unittest
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE = ROOT / "autopack" / "catalog.py"
if not MODULE.is_file():
    MODULE = ROOT / "catalog.py"
SPEC = importlib.util.spec_from_file_location("autopack_catalog", MODULE)
catalog = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = catalog
SPEC.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def test_catalog_has_exact_contiguous_600_items(self):
        items = catalog.build_catalog()
        self.assertEqual(len(items), 600)
        self.assertEqual((items[0].id, items[-1].id), ("AP-001", "AP-600"))
        self.assertEqual(catalog.validate(items), [])

    def test_every_item_is_actionable_and_honest(self):
        for item in catalog.build_catalog():
            self.assertTrue(item.requirement)
            self.assertTrue(item.acceptance)
            self.assertIn(item.status, catalog.STATUSES)
            if item.status == "implemented":
                self.assertTrue(item.code_refs)
                self.assertTrue(item.test_refs)
            self.assertNotEqual(item.status, "verified")

    def test_msi_controls_have_scoped_evidence(self):
        items = {item.id: item for item in catalog.build_catalog()}
        for item_id in ("AP-104", "AP-105"):
            item = items[item_id]
            self.assertEqual(item.status, "implemented")
            self.assertIn("package-msi.ps1", item.code_refs)
            self.assertIn("tests/test_package_msi.ps1", item.test_refs)
            self.assertIn("MSIX and Inno Setup remain planned", item.requirement)
        self.assertEqual(items["AP-106"].status, "planned")

    def test_implemented_item_requires_evidence(self):
        items = list(catalog.build_catalog())
        planned = next(index for index, item in enumerate(items) if item.status == "planned")
        items[planned] = replace(items[planned], status="implemented")
        item_id = items[planned].id
        self.assertIn(f"{item_id}: implemented requires code_refs and test_refs", catalog.validate(tuple(items)))

    def test_verified_item_requires_build_url(self):
        items = list(catalog.build_catalog())
        items[0] = replace(items[0], status="verified", evidence_urls=("https://example.com/report",))
        self.assertIn("AP-001: verified requires an immutable workflow-run URL", catalog.validate(tuple(items)))

    def test_external_blocker_must_be_named(self):
        items = list(catalog.build_catalog())
        blocked = next(index for index, item in enumerate(items) if item.status == "external-blocked")
        items[blocked] = replace(items[blocked], external_requirements=())
        item_id = items[blocked].id
        self.assertIn(f"{item_id}: external-blocked requires named external requirements", catalog.validate(tuple(items)))

    def test_implemented_reference_must_exist_inside_autopack(self):
        items = list(catalog.build_catalog())
        index = next(index for index, item in enumerate(items) if item.status == "implemented")
        items[index] = replace(items[index], code_refs=("outside/missing.py",))
        item_id = items[index].id
        self.assertIn(f"{item_id}: missing local reference outside/missing.py", catalog.validate(tuple(items)))

    def test_dependency_must_precede_item(self):
        items = list(catalog.build_catalog())
        items[0] = replace(items[0], dependencies=("AP-600",))
        self.assertIn("AP-001: dependencies must reference preceding catalog items", catalog.validate(tuple(items)))


if __name__ == "__main__":
    unittest.main()
