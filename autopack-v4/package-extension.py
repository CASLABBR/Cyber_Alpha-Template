#!/usr/bin/env python3
"""Validate and deterministically package a Chromium extension."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

IGNORED = {".git", "node_modules", "dist", "build", "__pycache__"}
SAFE_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_FILES = 10_000
MAX_FILE_SIZE = 100 * 1024 * 1024
MAX_TOTAL_SIZE = 500 * 1024 * 1024


def _safe_label(value: str, field: str) -> str:
    if not SAFE_LABEL.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"{field} inseguro; use apenas letras, numeros, ponto, hifen e sublinhado")
    return value


def _local_reference(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError(f"Referencia local invalida em {field}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith(("/", "\\")):
        raise ValueError(f"Referencia fora da extensao em {field}: {value}")
    return path.as_posix()


def _manifest_references(manifest: dict[str, object]) -> Iterable[tuple[str, str]]:
    icons = manifest.get("icons", {})
    if isinstance(icons, dict):
        for size, value in icons.items():
            yield f"icons.{size}", _local_reference(value, f"icons.{size}")

    for section_name in ("action", "browser_action", "page_action"):
        section = manifest.get(section_name, {})
        if not isinstance(section, dict):
            continue
        icon = section.get("default_icon")
        if isinstance(icon, str):
            yield f"{section_name}.default_icon", _local_reference(icon, f"{section_name}.default_icon")
        elif isinstance(icon, dict):
            for size, value in icon.items():
                field = f"{section_name}.default_icon.{size}"
                yield field, _local_reference(value, field)
        if section.get("default_popup"):
            field = f"{section_name}.default_popup"
            yield field, _local_reference(section["default_popup"], field)

    background = manifest.get("background", {})
    if isinstance(background, dict):
        if background.get("service_worker"):
            yield "background.service_worker", _local_reference(background["service_worker"], "background.service_worker")
        scripts = background.get("scripts", [])
        if isinstance(scripts, list):
            for index, value in enumerate(scripts):
                field = f"background.scripts[{index}]"
                yield field, _local_reference(value, field)

    content_scripts = manifest.get("content_scripts", [])
    if isinstance(content_scripts, list):
        for index, entry in enumerate(content_scripts):
            if not isinstance(entry, dict):
                continue
            for kind in ("js", "css"):
                values = entry.get(kind, [])
                if isinstance(values, list):
                    for item_index, value in enumerate(values):
                        field = f"content_scripts[{index}].{kind}[{item_index}]"
                        yield field, _local_reference(value, field)


def _collect_files(source: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    case_names: dict[str, str] = {}
    total_size = 0
    for path in source.rglob("*"):
        rel = path.relative_to(source)
        if path.is_symlink():
            raise ValueError(f"Links simbolicos nao sao permitidos: {rel.as_posix()}")
        if any(part in IGNORED for part in rel.parts):
            continue
        if not path.is_file():
            continue
        name = rel.as_posix()
        folded = name.casefold()
        previous = case_names.get(folded)
        if previous is not None and previous != name:
            raise ValueError(f"Colisao de maiusculas/minusculas: {previous} e {name}")
        case_names[folded] = name
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            raise ValueError(f"Arquivo excede o limite de {MAX_FILE_SIZE} bytes: {name}")
        total_size += size
        if total_size > MAX_TOTAL_SIZE:
            raise ValueError(f"Extensao excede o limite total de {MAX_TOTAL_SIZE} bytes")
        files.append((path, name))
        if len(files) > MAX_FILES:
            raise ValueError(f"Extensao excede o limite de {MAX_FILES} arquivos")
    return sorted(files, key=lambda item: (item[1].casefold(), item[1]))


def package(source: Path, output: Path, product: str, version: str) -> Path:
    if source.is_symlink():
        raise ValueError("Diretorio da extensao nao pode ser link simbolico")
    source = source.resolve()
    product = _safe_label(product, "produto")
    version = _safe_label(version, "versao")
    if not source.is_dir():
        raise ValueError("Diretorio da extensao inexistente")
    manifest_path = source / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("manifest.json ausente ou inseguro")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("manifest.json invalido") from exc
    if not isinstance(manifest, dict) or manifest.get("manifest_version") not in {2, 3}:
        raise ValueError("manifest.json nao e uma extensao Chromium MV2/MV3")
    for required in ("name", "version"):
        if not isinstance(manifest.get(required), str) or not manifest[required].strip():
            raise ValueError(f"manifest.json sem campo obrigatorio: {required}")

    files = _collect_files(source)
    names = {name for _, name in files}
    names_casefold = {name.casefold(): name for name in names}
    for field, reference in _manifest_references(manifest):
        actual = names_casefold.get(reference.casefold())
        if actual != reference:
            reason = "capitalizacao diferente" if actual else "arquivo ausente"
            raise ValueError(f"Referencia invalida ({reason}) em {field}: {reference}")

    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{product}-Chrome-{version}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path, name in files:
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    (output / "INSTALL.txt").write_text(
        "Extraia o ZIP, abra chrome://extensions, ative o Modo do desenvolvedor e use Carregar sem compactacao.\n"
        "Para publicar na Chrome Web Store, use uma conta de desenvolvedor e assinatura proprias.\n",
        encoding="utf-8",
    )
    return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("product")
    parser.add_argument("version")
    args = parser.parse_args()
    package(args.source, args.output, args.product, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
