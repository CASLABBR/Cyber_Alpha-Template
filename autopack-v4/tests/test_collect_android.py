import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "autopack" / "collect-android.sh"
if not SCRIPT.is_file():
    SCRIPT = ROOT / "collect-android.sh"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe") if os.name == "nt" else Path(shutil.which("bash") or "bash")


class AndroidCollectorTests(unittest.TestCase):
    def setUp(self):
        if not BASH.exists() and shutil.which(str(BASH)) is None:
            self.skipTest("bash indisponivel")
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() if os.name == "nt" else None)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.output = self.root / "artifacts"
        self.source.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def run_collector(self, product="Demo", version="1.2.3"):
        def shell_path(path):
            value = str(Path(path).resolve())
            if os.name == "nt":
                drive, tail = os.path.splitdrive(value)
                return f"/{drive[0].lower()}{tail.replace(os.sep, '/')}"
            return value
        command = [
            str(BASH), shell_path(SCRIPT), shell_path(self.source), shell_path(self.output), product, version,
        ]
        environment = os.environ.copy()
        if os.name == "nt":
            environment["PATH"] = os.pathsep.join([
                r"C:\Program Files\Git\usr\bin", r"C:\Program Files\Git\mingw64\bin",
                environment.get("PATH", ""),
            ])
        return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)

    def artifact(self, relative, content):
        path = self.source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_preserves_module_flavor_and_abi_without_overwrite(self):
        self.artifact("app/build/outputs/apk/free/release/app-free-arm64-v8a.apk", b"apk-one")
        self.artifact("feature/build/outputs/apk/free/release/feature-free-arm64-v8a.apk", b"apk-two")
        self.artifact("app/build/outputs/bundle/release/app-release.aab", b"bundle")
        result = self.run_collector()
        self.assertEqual(result.returncode, 0, result.stderr)

        inventory = json.loads((self.output / "android-artifacts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory["artifacts"]), 3)
        names = [item["file"] for item in inventory["artifacts"]]
        self.assertEqual(len(names), len(set(name.casefold() for name in names)))
        self.assertTrue(any("app-build-outputs-apk-free-release" in name for name in names))
        self.assertTrue(any("feature-build-outputs-apk-free-release" in name for name in names))
        for item in inventory["artifacts"]:
            payload = (self.output / item["file"]).read_bytes()
            self.assertEqual(item["bytes"], len(payload))
            self.assertEqual(item["sha256"], hashlib.sha256(payload).hexdigest())
        sums = (self.output / "SHA256SUMS.txt").read_text(encoding="ascii")
        self.assertEqual(len(sums.strip().splitlines()), 3)

    def test_fails_when_sanitized_destinations_collide(self):
        self.artifact("module a/build/outputs/apk/release/app.apk", b"one")
        self.artifact("module-a/build/outputs/apk/release/app.apk", b"two")
        result = self.run_collector()
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("Colisao de artefatos", result.stderr)

    def test_rejects_symlink_in_output_tree(self):
        target = self.artifact("real.apk", b"outside")
        link = self.source / "app/build/outputs/apk/release/app.apk"
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlinks indisponiveis")
        result = self.run_collector()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("Links simbolicos", result.stderr)

    def test_rejects_unsafe_labels(self):
        self.artifact("app/build/outputs/apk/release/app.apk", b"apk")
        result = self.run_collector(product="../escape")
        self.assertEqual(result.returncode, 2)
        self.assertIn("produto inseguro", result.stderr)

    def test_fails_without_artifacts(self):
        result = self.run_collector()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Nenhum APK ou AAB", result.stderr)


if __name__ == "__main__":
    unittest.main()
