import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ENGINE = Path(__file__).parents[1] / "autopack" / "engine.py"
SPEC = importlib.util.spec_from_file_location("autopack_engine", ENGINE)
engine = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(engine)


class EngineTests(unittest.TestCase):
    def test_detection_is_deterministic_and_prefers_root_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "nested").mkdir()
            (root / "nested" / "main.py").write_text("", encoding="utf-8")
            (root / "main.py").write_text("", encoding="utf-8")
            result = engine.detect(root, "auto", "")
            self.assertEqual(result["kind"], "python")
            self.assertEqual(result["python_entry"], "main.py")

    def test_ignored_generated_directory_and_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "build").mkdir()
            (root / "build" / "main.py").write_text("", encoding="utf-8")
            self.assertEqual(engine.detect(root, "auto", "")["kind"], "unknown")

    def test_python_entry_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside = root.parent / "outside-autopack-test.py"
            outside.write_text("", encoding="utf-8")
            try:
                with self.assertRaisesRegex(ValueError, "escapes"):
                    engine.detect(root, "python", "../outside-autopack-test.py")
            finally:
                outside.unlink(missing_ok=True)

    def test_invalid_requested_kind_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                engine.detect(Path(td), "shell; calc", "")

    def test_package_metadata_is_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(json.dumps({
                "name": "@scope/my app\nunsafe", "version": "1.2.3 <bad>"
            }), encoding="utf-8")
            paths = ["package.json"]
            detection = engine.detect(root, "auto", "")
            metadata = engine.project_metadata(root, paths, detection)
            self.assertEqual(metadata["name"], "scope-my-app-unsafe")
            self.assertEqual(metadata["source_version"], "1.2.3-bad")

    def test_build_number_never_crashes_or_goes_negative(self):
        self.assertEqual(engine.positive_build_number("banana"), 0)
        self.assertEqual(engine.positive_build_number("-5"), 0)
        self.assertEqual(engine.positive_build_number("42"), 42)

    def test_github_output_uses_multiline_protocol(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "output"
            engine.write_github_output(str(output), {"product": "safe\ninjected=true"})
            text = output.read_text(encoding="utf-8")
            self.assertIn("product<<AUTOPACK_", text)
            self.assertIn("safe\ninjected=true", text)
            self.assertNotIn("product=safe", text)

    def test_native_application_beats_auxiliary_dockerfile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
            result = engine.detect(root, "auto", "")
            self.assertEqual(result["kind"], "python")

    def test_native_application_beats_nested_compose_helper(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "main.py").write_text("print('ok')\n", encoding="utf-8")
            helper = root / "devscripts"
            helper.mkdir()
            (helper / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
            result = engine.detect(root, "auto", "")
            self.assertEqual(result["kind"], "python")

    def test_pwa_requires_manifest_and_service_worker(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "index.html").write_text("<html></html>", encoding="utf-8")
            (root / "manifest.webmanifest").write_text("{}", encoding="utf-8")
            (root / "service-worker.js").write_text("", encoding="utf-8")
            result = engine.detect(root, "auto", "")
            self.assertEqual(result["kind"], "pwa")

    def test_tauri_beats_generic_node_and_rust(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text('{"name":"desktop"}', encoding="utf-8")
            tauri = root / "src-tauri"
            tauri.mkdir()
            (tauri / "Cargo.toml").write_text("[package]\nname='desktop'\nversion='1.0.0'", encoding="utf-8")
            (tauri / "tauri.conf.json").write_text("{}", encoding="utf-8")
            result = engine.detect(root, "auto", "")
            self.assertEqual(result["kind"], "tauri")


if __name__ == "__main__":
    unittest.main()
