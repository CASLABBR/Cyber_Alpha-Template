#!/usr/bin/env python3
"""Create a safe, reproducible source bundle for MCP servers and Codex plugins."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path

EXCLUDED = {".git", ".github", "node_modules", ".venv", "venv", "dist", "build", "artifacts", "__pycache__"}
MAX_FILES = 20_000
MAX_BYTES = 512 * 1024 * 1024
ZIP_TIME = (2020, 1, 1, 0, 0, 0)


def safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned[:80] or fallback


def files_under(root: Path):
    total = 0
    count = 0
    seen = set()
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix().casefold()):
        rel = path.relative_to(root)
        if any(part in EXCLUDED for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Symlink recusado: {rel.as_posix()}")
        if not path.is_file():
            continue
        key = rel.as_posix().casefold()
        if key in seen:
            raise ValueError(f"Colisao de nome sem diferenca de caixa: {rel.as_posix()}")
        seen.add(key)
        count += 1
        total += path.stat().st_size
        if count > MAX_FILES or total > MAX_BYTES:
            raise ValueError("Projeto excede o limite seguro do empacotador")
        yield path, rel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("mcp", "plugin"))
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("product")
    parser.add_argument("version")
    args = parser.parse_args()

    source = args.source.resolve(strict=True)
    product = safe_name(args.product, "app")
    version = safe_name(args.version, "0")
    args.output.mkdir(parents=True, exist_ok=True)
    archive = args.output / f"{product}-{version}-{args.kind}.zip"
    inventory = []
    generated: dict[str, bytes] = {}
    if args.kind == "mcp":
        package_json = source / "package.json"
        if package_json.is_file():
            package = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = package.get("scripts") or {}
            if "start" not in scripts:
                raise ValueError("Servidor MCP Node precisa declarar scripts.start")
            if (source / "pnpm-lock.yaml").is_file():
                install, start = "corepack pnpm install --frozen-lockfile", "corepack pnpm start"
            elif (source / "yarn.lock").is_file():
                install, start = "corepack yarn install --immutable", "corepack yarn start"
            elif (source / "package-lock.json").is_file() or (source / "npm-shrinkwrap.json").is_file():
                install, start = "npm ci", "npm start"
            else:
                install, start = "npm install", "npm start"
            generated["start-autopack.cmd"] = (f"@echo off\r\ncd /d %~dp0\r\n{install} || exit /b 1\r\n{start}\r\n").encode()
            generated["start-autopack.sh"] = (f"#!/usr/bin/env sh\nset -eu\ncd \"$(dirname \"$0\")\"\n{install}\nexec {start}\n").encode()
            generated["mcp-config.example.json"] = json.dumps({"mcpServers": {product: {"command": "start-autopack.cmd", "args": []}}}, indent=2).encode() + b"\n"
        else:
            generated["MCP-CONFIGURATION.txt"] = b"Configure o comando MCP conforme o entry point declarado no pyproject.toml.\n"
    else:
        generated["PLUGIN-INSTALL.txt"] = b"Copie esta pasta para um diretorio de plugins confiavel e valide .codex-plugin/plugin.json antes de ativar.\n"

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path, rel in files_under(source):
            data = path.read_bytes()
            info = zipfile.ZipInfo(rel.as_posix(), ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(info, data)
            inventory.append({"path": rel.as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})

        for name, data in sorted(generated.items()):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if name.endswith(".sh") else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            zf.writestr(info, data)
            inventory.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "generated": True})

        readme = (
            f"AutoPack v4 {args.kind} bundle\n"
            "Extraia o ZIP. Leia README e o manifesto antes de executar.\n"
            "Dependencias nao sao executadas automaticamente por seguranca.\n"
        ).encode()
        info = zipfile.ZipInfo("AUTOPACK-INSTALL.txt", ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        zf.writestr(info, readme)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    metadata = {"schema": "autopack.bundle.v1", "kind": args.kind, "product": product, "version": version,
                "archive": archive.name, "sha256": digest, "files": inventory}
    (args.output / f"{archive.name}.manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (args.output / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
