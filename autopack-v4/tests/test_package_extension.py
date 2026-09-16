import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "autopack" / "package-extension.py"
if not SCRIPT.is_file():
    SCRIPT = ROOT / "package-extension.py"
SPEC = importlib.util.spec_from_file_location("package_extension", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(module)


class ExtensionPackageTests(unittest.TestCase):
    def make_extension(self, root, manifest=None):
        source, output = root / "source", root / "output"
        source.mkdir()
        manifest = manifest or {"manifest_version": 3, "name": "Demo", "version": "1.0.0"}
        (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return source, output

    def test_packages_manifest_and_excludes_generated_trees(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output = root / "source", root / "output"
            source.mkdir()
            (source / "manifest.json").write_text(json.dumps({
                "manifest_version": 3, "name": "Demo", "version": "1.0.0"
            }), encoding="utf-8")
            (source / "background.js").write_text("", encoding="utf-8")
            (source / "node_modules").mkdir()
            (source / "node_modules" / "secret.js").write_text("", encoding="utf-8")
            archive = module.package(source, output, "Demo", "1.0.0")
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(sorted(bundle.namelist()), ["background.js", "manifest.json"])
            self.assertTrue((output / "SHA256SUMS.txt").is_file())

    def test_zip_is_deterministic_despite_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td))
            script = source / "worker.js"
            script.write_text("console.log('ok')", encoding="utf-8")
            first = module.package(source, output, "Demo", "1.2.3").read_bytes()
            os.utime(script, (2_000_000_000, 2_000_000_000))
            second = module.package(source, output, "Demo", "1.2.3").read_bytes()
            self.assertEqual(first, second)

    def test_rejects_unsafe_product_and_version(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td))
            for product, version in (("../escape", "1"), ("Demo", "../1"), ("A/B", "1")):
                with self.subTest(product=product, version=version):
                    with self.assertRaisesRegex(ValueError, "inseguro"):
                        module.package(source, output, product, version)

    def test_validates_local_manifest_references(self):
        manifest = {
            "manifest_version": 3, "name": "Demo", "version": "1.0.0",
            "icons": {"16": "icons/icon.png"},
            "action": {"default_popup": "popup.html"},
            "background": {"service_worker": "worker.js"},
            "content_scripts": [{"matches": ["https://example.com/*"], "js": ["content.js"], "css": ["style.css"]}],
        }
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td), manifest)
            (source / "icons").mkdir()
            for name in ("icons/icon.png", "popup.html", "worker.js", "content.js", "style.css"):
                (source / name).write_bytes(b"x")
            self.assertTrue(module.package(source, output, "Demo", "1.0.0").is_file())
            (source / "worker.js").unlink()
            with self.assertRaisesRegex(ValueError, "arquivo ausente"):
                module.package(source, output, "Demo", "1.0.0")

    def test_rejects_reference_traversal_and_case_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td), {
                "manifest_version": 3, "name": "Demo", "version": "1", "icons": {"16": "../icon.png"}
            })
            with self.assertRaisesRegex(ValueError, "fora da extensao"):
                module.package(source, output, "Demo", "1")
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td), {
                "manifest_version": 3, "name": "Demo", "version": "1", "background": {"service_worker": "Worker.js"}
            })
            (source / "worker.js").write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "capitalizacao diferente"):
                module.package(source, output, "Demo", "1")

    def test_rejects_case_collision(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td))
            (source / "Foo.js").write_text("", encoding="utf-8")
            (source / "foo.js").write_text("", encoding="utf-8")
            if (source / "Foo.js").samefile(source / "foo.js"):
                self.skipTest("filesystem nao diferencia maiusculas")
            with self.assertRaisesRegex(ValueError, "Colisao"):
                module.package(source, output, "Demo", "1")

    def test_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td))
            target = source / "real.js"
            target.write_text("", encoding="utf-8")
            try:
                (source / "link.js").symlink_to(target)
            except OSError:
                self.skipTest("symlinks indisponiveis")
            with self.assertRaisesRegex(ValueError, "Links simbolicos"):
                module.package(source, output, "Demo", "1")

    def test_enforces_file_size_limit(self):
        with tempfile.TemporaryDirectory() as td:
            source, output = self.make_extension(Path(td))
            (source / "big.bin").write_bytes(b"x" * 9)
            previous = module.MAX_FILE_SIZE
            module.MAX_FILE_SIZE = 8
            try:
                with self.assertRaisesRegex(ValueError, "excede o limite"):
                    module.package(source, output, "Demo", "1")
            finally:
                module.MAX_FILE_SIZE = previous

    def test_rejects_web_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source, output = root / "source", root / "output"
            source.mkdir()
            (source / "manifest.json").write_text('{"name":"PWA"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Chromium"):
                module.package(source, output, "Demo", "1.0.0")


if __name__ == "__main__":
    unittest.main()
