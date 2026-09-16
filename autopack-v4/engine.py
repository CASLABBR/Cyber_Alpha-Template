#!/usr/bin/env python3
"""AutoPack v4: conservative project detector and build-plan generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


IGNORED = {".git", ".venv", "venv", "node_modules", "bin", "obj", "dist", "build"}
KINDS = {"auto", "android", "dotnet", "python", "python-library", "rust", "go", "node",
         "static-web", "pwa", "hta", "tauri", "docker", "docker-compose",
         "chrome-extension", "mcp", "plugin"}


def files(root: Path) -> Iterable[Path]:
    """Yield regular, non-symlink files deterministically, pruning generated trees."""
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in IGNORED and not (Path(current) / d).is_symlink())
        for name in sorted(names):
            path = Path(current) / name
            if not path.is_symlink() and path.is_file():
                yield path


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def first_from(paths: list[str], names: list[str]) -> str:
    wanted = [name.lower() for name in names]
    # Prefer a root-level file, then the shallowest and lexicographically first one.
    matches = [p for p in paths if Path(p).name.lower() in wanted]
    return min(matches, key=lambda p: (p.count("/"), p.lower())) if matches else ""


def git_value(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL, timeout=10
        ).strip() or "unknown"
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value[:80] or "AutoPack-Application"


def safe_version(value: str) -> str:
    """Return a portable SemVer-ish source version, never executable text."""
    value = re.sub(r"[^0-9A-Za-z.+_-]+", "-", str(value)).strip("-.")
    return value[:64]


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def project_metadata(root: Path, paths: list[str], detection: dict) -> dict:
    """Read declarative metadata only; README and build scripts are never executed."""
    name = root.name
    version = ""
    package = detection.get("package_json")
    if package:
        data = _load_json(root / package)
        name, version = data.get("productName") or data.get("name") or name, data.get("version") or ""

    pyproject = first_from(paths, ["pyproject.toml"])
    if pyproject:
        try:
            data = tomllib.loads((root / pyproject).read_text(encoding="utf-8"))
            project = data.get("project", {})
            poetry = data.get("tool", {}).get("poetry", {})
            name = project.get("name") or poetry.get("name") or name
            version = project.get("version") or poetry.get("version") or version
        except (OSError, UnicodeError, tomllib.TOMLDecodeError, AttributeError):
            pass

    csproj = detection.get("dotnet_project")
    if csproj:
        try:
            xml = ET.parse(root / csproj).getroot()
            name = xml.findtext(".//AssemblyName") or name
            version = xml.findtext(".//Version") or xml.findtext(".//VersionPrefix") or version
        except (OSError, ET.ParseError):
            pass
    return {"name": safe_name(str(name)), "source_version": safe_version(str(version))}


def validate_relative_file(root: Path, value: str) -> str:
    if not value:
        return ""
    candidate = Path(value)
    if candidate.is_absolute():
        raise ValueError("Python entry must be relative to the source directory")
    resolved = (root / candidate).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Python entry escapes the source directory") from exc
    if not resolved.is_file() or resolved.is_symlink() or resolved.suffix.lower() != ".py":
        raise ValueError(f"Python entry is not a regular .py file: {value}")
    return rel.as_posix()


def detect(root: Path, requested: str, python_entry: str) -> dict:
    if requested not in KINDS:
        raise ValueError(f"Unsupported project type: {requested}")
    paths = [relative(path, root) for path in files(root)]
    lower = {path.lower() for path in paths}
    evidence: list[str] = []
    candidates: list[tuple[str, int]] = []

    gradlew = first_from(paths, ["gradlew", "gradlew.bat"])
    manifests = [p for p in paths if p.lower().endswith("androidmanifest.xml")]
    android = bool(manifests and gradlew)
    csprojects = sorted((p for p in paths if p.lower().endswith(".csproj")), key=lambda p: (p.count("/"), p.lower()))
    csproj = csprojects[0] if csprojects else ""
    cargo = first_from(paths, ["Cargo.toml"])
    gomod = first_from(paths, ["go.mod"])
    package = first_from(paths, ["package.json"])
    compose = first_from(paths, ["compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"])
    dockerfile = first_from(paths, ["Dockerfile"])
    html = first_from(paths, ["index.html"])
    web_manifest = first_from(paths, ["manifest.webmanifest", "manifest.json"])
    service_worker = first_from(paths, ["service-worker.js", "serviceworker.js", "sw.js"])
    tauri_config = first_from(paths, ["tauri.conf.json", "tauri.conf.json5", "Tauri.toml"])
    plugin_manifest = first_from(paths, ["plugin.json"])
    extension_manifest = ""
    mcp_manifest = ""

    for manifest_path in sorted(
        (p for p in paths if Path(p).name.lower() == "manifest.json"),
        key=lambda p: (p.count("/"), p.lower()),
    ):
        manifest_data = _load_json(root / manifest_path)
        if manifest_data.get("manifest_version") in {2, 3} and manifest_data.get("name"):
            extension_manifest = manifest_path
            break

    if package:
        package_data = _load_json(root / package)
        dependencies = {
            **(package_data.get("dependencies") or {}),
            **(package_data.get("devDependencies") or {}),
        }
        scripts = package_data.get("scripts") or {}
        if "@modelcontextprotocol/sdk" in dependencies or any("mcp" in str(v).lower() for v in scripts.values()):
            mcp_manifest = package
    if not mcp_manifest:
        pyproject = first_from(paths, ["pyproject.toml"])
        if pyproject:
            try:
                pyproject_text = (root / pyproject).read_text(encoding="utf-8").lower()
                if re.search(r"(^|[^a-z])mcp([^a-z]|$)|modelcontextprotocol", pyproject_text):
                    mcp_manifest = pyproject
            except (OSError, UnicodeError):
                pass

    python_entry = validate_relative_file(root, python_entry) if python_entry else ""
    if not python_entry:
        python_entry = first_from(paths, ["main.py", "app.py", "run.py", "start.py", "__main__.py"])
    yt_entry = next((p for p in paths if p.lower() == "yt_dlp/__main__.py"), "")
    if yt_entry:
        python_entry = yt_entry

    if android:
        candidates.append(("android", 98)); evidence += [manifests[0], gradlew]
    if csproj:
        candidates.append(("dotnet", 95)); evidence.append(csproj)
    if python_entry:
        candidates.append(("python", 90)); evidence.append(python_entry)
    else:
        python_manifest = first_from(paths, ["pyproject.toml", "requirements.txt", "setup.py"])
        if python_manifest:
            candidates.append(("python-library", 55)); evidence.append(python_manifest)
    if cargo:
        candidates.append(("rust", 92)); evidence.append(cargo)
    if gomod:
        candidates.append(("go", 92)); evidence.append(gomod)
    if package:
        candidates.append(("node", 82)); evidence.append(package)
    if tauri_config and cargo:
        candidates.append(("tauri", 99)); evidence += [tauri_config, cargo]
    if extension_manifest:
        candidates.append(("chrome-extension", 99)); evidence.append(extension_manifest)
    if mcp_manifest:
        candidates.append(("mcp", 97)); evidence.append(mcp_manifest)
    if plugin_manifest and ".codex-plugin/" in plugin_manifest.lower():
        candidates.append(("plugin", 99)); evidence.append(plugin_manifest)
    if html and web_manifest and service_worker:
        candidates.append(("pwa", 91)); evidence += [html, web_manifest, service_worker]
    if html and not package:
        candidates.append(("static-web", 88)); evidence.append(html)
    if compose:
        # A root Compose file normally defines the product. Nested Compose
        # files are commonly development helpers and must not override a
        # detectable native application.
        compose_score = 97 if "/" not in compose else 60
        candidates.append(("docker-compose", compose_score)); evidence.append(compose)
    elif dockerfile:
        # Docker is usually an additional distribution option. When a native
        # application is detectable, package that application as the primary
        # result and keep Docker as a secondary compatible target.
        candidates.append(("docker", 65)); evidence.append(dockerfile)

    candidates.sort(key=lambda item: (-item[1], item[0]))
    kind = requested if requested != "auto" else (candidates[0][0] if candidates else "unknown")
    confidence = next((score for name, score in candidates if name == kind), 40 if requested != "auto" else 0)
    return {"kind": kind, "confidence": confidence,
            "candidates": [{"kind": name, "confidence": score} for name, score in candidates],
            "evidence": sorted(set(evidence)), "python_entry": python_entry, "dotnet_project": csproj,
            "gradle_root": str(Path(gradlew).parent).replace("\\", "/") if gradlew else "",
            "package_json": package, "compose_file": compose, "dockerfile": dockerfile, "index_html": html,
            "web_manifest": web_manifest, "service_worker": service_worker,
            "tauri_config": tauri_config, "extension_manifest": extension_manifest,
            "mcp_manifest": mcp_manifest, "plugin_manifest": plugin_manifest}


def positive_build_number(raw: str) -> int:
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def write_github_output(path: str, values: dict) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        for key, raw in values.items():
            value = str(raw)
            marker = f"AUTOPACK_{hashlib.sha256((key + value).encode()).hexdigest()[:16]}"
            handle.write(f"{key}<<{marker}\n{value}\n{marker}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--type", default="auto", choices=sorted(KINDS))
    parser.add_argument("--python-entry", default="")
    parser.add_argument("--repository", default="")
    parser.add_argument("--output", type=Path, default=Path("autopack-plan.json"))
    args = parser.parse_args()
    root = args.source.resolve()
    if not root.is_dir():
        raise SystemExit(f"Source directory not found: {root}")
    try:
        result = detect(root, args.type, args.python_entry)
    except ValueError as exc:
        parser.error(str(exc))

    build_number = positive_build_number(os.environ.get("GITHUB_RUN_NUMBER", "0"))
    now = datetime.now(timezone.utc)
    version = f"{now.year}.{now.month:02d}.{now.day:02d}.{build_number}"
    repo_name = args.repository.rstrip("/").removesuffix(".git").split("/")[-1] or root.name
    metadata = project_metadata(root, [relative(p, root) for p in files(root)], result)
    # Repository name remains the fallback, but a declared package/product name is authoritative.
    product = metadata["name"] if metadata["name"] != safe_name(root.name) else safe_name(repo_name)
    plan = {
        "schema": "https://caslabbr.github.io/autopack/plan/v4", "engine": "AutoPack v4",
        "product": product, "version": version, "source_version": metadata["source_version"],
        "build_number": build_number, "created_at": now.isoformat(),
        "source": {"repository": args.repository, "commit": git_value(root, "rev-parse", "HEAD"),
                   "branch": git_value(root, "rev-parse", "--abbrev-ref", "HEAD"),
                   "tag": git_value(root, "describe", "--tags", "--exact-match")},
        "detection": result, "outputs": ["report", "checksums"], "warnings": [],
    }
    if result["kind"] in {"python", "dotnet"}: plan["outputs"] += ["windows-portable", "windows-msi"]
    if result["kind"] == "android": plan["outputs"] += ["apk", "aab"]
    if result["kind"] in {"docker", "docker-compose"}: plan["outputs"] += ["docker-image", "docker-portable"]
    if result["kind"] == "chrome-extension": plan["outputs"] += ["chrome-extension-zip"]
    if result["kind"] == "mcp": plan["outputs"] += ["mcp-bundle", "launcher", "config-example"]
    if result["kind"] == "plugin": plan["outputs"] += ["plugin-bundle", "install-instructions"]
    if result["confidence"] < 70: plan["warnings"].append("Low detection confidence; explicit configuration is recommended.")

    encoded = json.dumps(plan, ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded + "\n", encoding="utf-8")
    digest = hashlib.sha256((encoded + "\n").encode()).hexdigest()
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        write_github_output(github_output, {
            "kind": result["kind"], "confidence": result["confidence"], "version": version,
            "product": plan["product"], "plan_sha256": digest, "python_entry": result["python_entry"],
            "dotnet_project": result["dotnet_project"], "gradle_root": result["gradle_root"],
            "compose_file": result["compose_file"]})
    print(encoded)
    return 0 if result["kind"] != "unknown" else 2


if __name__ == "__main__":
    raise SystemExit(main())
