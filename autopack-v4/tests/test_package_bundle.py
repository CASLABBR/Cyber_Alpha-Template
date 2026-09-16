import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "autopack" / "package-bundle.py"
if not SCRIPT.is_file():
    SCRIPT = ROOT / "package-bundle.py"


class BundleTests(unittest.TestCase):
    def run_bundle(self, root, out, product="Demo", version="1.0"):
        return subprocess.run([sys.executable, str(SCRIPT), "mcp", str(root), str(out), product, version], capture_output=True, text=True)

    def test_bundle_is_reproducible_and_has_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"; root.mkdir()
            (root / "server.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "package.json").write_text('{"scripts":{"start":"node server.py"}}', encoding="utf-8")
            out1 = Path(tmp) / "one"; out2 = Path(tmp) / "two"
            self.assertEqual(self.run_bundle(root, out1).returncode, 0)
            self.assertEqual(self.run_bundle(root, out2).returncode, 0)
            zip1 = next(out1.glob("*.zip")); zip2 = next(out2.glob("*.zip"))
            self.assertEqual(zip1.read_bytes(), zip2.read_bytes())
            with zipfile.ZipFile(zip1) as archive:
                self.assertIn("AUTOPACK-INSTALL.txt", archive.namelist())
                self.assertIn("start-autopack.cmd", archive.namelist())
                self.assertIn("start-autopack.sh", archive.namelist())
                self.assertIn("mcp-config.example.json", archive.namelist())
            manifest = json.loads(next(out1.glob("*.manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "mcp")

    def test_product_cannot_escape_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"; root.mkdir(); (root / "x").write_text("x")
            out = Path(tmp) / "out"
            result = self.run_bundle(root, out, "../../escape")
            self.assertEqual(result.returncode, 0)
            self.assertTrue(all(p.parent == out for p in out.iterdir()))

    def test_node_mcp_requires_start_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"; root.mkdir()
            (root / "package.json").write_text('{"name":"missing-start"}', encoding="utf-8")
            result = self.run_bundle(root, Path(tmp) / "out")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
