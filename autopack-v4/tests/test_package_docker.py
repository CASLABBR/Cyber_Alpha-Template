import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "autopack" / "package-docker.sh"
if not SCRIPT.is_file():
    SCRIPT = ROOT / "package-docker.sh"
BASH = shutil.which("bash")
if os.name == "nt":
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        BASH = str(git_bash)


@unittest.skipUnless(BASH, "bash is required")
class DockerPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        self.bin = self.root / "bin"
        self.source.mkdir()
        self.bin.mkdir()
        python_command = Path(sys.executable).as_posix()
        for command in ("python", "python3"):
            shim = self.bin / command
            shim.write_text(f"#!/usr/bin/env sh\nexec '{python_command}' \"$@\"\n", encoding="utf-8")
            shim.chmod(0o755)
        (self.source / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
        (self.source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        fake = self.bin / "docker"
        fake.write_text(
            """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ['compose', '-f']:
    command = args[3:]
    if command[:3] == ['config', '--format', 'json']:
        print(os.environ['FAKE_COMPOSE_CONFIG'])
    elif command == ['config', '--quiet'] or command == ['build']:
        pass
    elif command == ['images', '--format', 'json']:
        print(os.environ.get('FAKE_COMPOSE_IMAGES', '[]'))
    else:
        raise SystemExit('unexpected compose command: ' + repr(command))
elif args and args[0] == 'save':
    sys.stdout.buffer.write(b'fake docker image archive')
elif args[:2] == ['image', 'inspect']:
    image = args[2]
    print(json.dumps([{'Id': 'sha256:abc123', 'RepoDigests': [image + '@sha256:def456']}]))
elif args and args[0] == 'build':
    pass
else:
    raise SystemExit('unexpected docker command: ' + repr(args))
""",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        (self.bin / "docker.cmd").write_text(
            f'@"{sys.executable}" "{fake}" %*\r\n', encoding="utf-8"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def run_package(self, config, *, expect_success=True):
        environment = os.environ.copy()
        environment["PATH"] = str(self.bin) + os.pathsep + environment["PATH"]
        environment["FAKE_COMPOSE_CONFIG"] = json.dumps(config)
        environment["FAKE_COMPOSE_IMAGES"] = json.dumps([
            {"Service": "web", "Repository": "demo/web", "Tag": "1.0", "ID": "sha256:abc123"}
        ])
        environment["AUTOPACK_DOCKER_BIN"] = str(self.bin / ("docker.cmd" if os.name == "nt" else "docker"))
        def bash_path(path):
            value = Path(path).resolve().as_posix()
            if os.name == "nt" and len(value) > 2 and value[1] == ":":
                value = f"/{value[0].lower()}{value[2:]}"
            return value
        result = subprocess.run(
            [BASH, bash_path(SCRIPT), bash_path(self.source), bash_path(self.output), "../Demo App", "1.2.3", "compose.yaml"],
            text=True,
            capture_output=True,
            env=environment,
        )
        if expect_success and result.returncode:
            self.fail(f"package failed: stdout={result.stdout!r} stderr={result.stderr!r}")
        return result

    def valid_config(self):
        return {
            "name": "demo",
            "services": {
                "web": {
                    "build": {"context": str(self.source), "dockerfile": "Dockerfile"},
                    "restart": "unless-stopped",
                }
            },
        }

    def test_compose_package_is_offline_and_traceable(self):
        self.run_package(self.valid_config())
        package = self.output / "docker-package"
        self.assertGreater((package / "images.tar.gz").stat().st_size, 0)
        portable = json.loads((package / "compose.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("build", portable["services"]["web"])
        self.assertEqual(portable["services"]["web"]["image"], "demo/web:1.0")
        inventory = json.loads((package / "images.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory[0]["id"], "sha256:abc123")
        self.assertIn("sha256:def456", inventory[0]["repo_digests"][0])
        for required in ("Carregar-Imagens.sh", "Carregar-Imagens.ps1", "Iniciar.sh", "Iniciar.cmd", "SHA256SUMS.txt"):
            self.assertTrue((package / required).is_file(), required)
        self.assertTrue((self.output / "Demo-App-1.2.3-Docker.tar.gz").is_file())

    def test_rejects_context_outside_source(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        config = self.valid_config()
        config["services"]["web"]["build"]["context"] = str(outside)
        result = self.run_package(config, expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fora da raiz", result.stderr)

    def test_rejects_additional_contexts_and_entitlements(self):
        for field, value in (("additional_contexts", {"other": "../other"}), ("entitlements", ["network.host"])):
            with self.subTest(field=field):
                config = self.valid_config()
                config["services"]["web"]["build"][field] = value
                result = self.run_package(config, expect_success=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(field, result.stderr)

    def test_rejects_external_and_build_secrets(self):
        config = self.valid_config()
        config["secrets"] = {"token": {"external": True}}
        result = self.run_package(config, expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("secret externo", result.stderr)

        config = self.valid_config()
        config["services"]["web"]["build"]["secrets"] = ["token"]
        result = self.run_package(config, expect_success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("build secrets", result.stderr)


if __name__ == "__main__":
    unittest.main()
