#!/usr/bin/env python3
"""Machine-verifiable catalog of the 600 AutoPack requirements."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


AUTOPACK_ROOT = Path(__file__).parent.parent if Path(__file__).parent.name == "autopack" else Path(__file__).parent


EPICS = (
    "language, manifest and entry-point detection", "confidence scoring, evidence and reproducible plans",
    "Python CLI, GUI and virtual environments", ".NET desktop, services and self-contained publishing",
    "Android, Gradle, APK, AAB and signing", "Node.js, npm, pnpm, Yarn and desktop applications",
    "static sites, SPAs and local servers", "PWA offline support, service workers and TWA",
    "Docker, Compose, OCI and GPU environments", "Windows EXE, portable launchers and CLI arguments",
    "MSI, MSIX, Inno Setup and optional components", "updates, release channels, rollback and repair",
    "metadata, SemVer, icons and branding", "hashes, signatures, SBOM and provenance",
    "ISO media, offline distribution and HTML catalogs", "multi-target selection and format matrices",
    "queues, batch input, CSV and concurrency limits", "monorepos, workspaces and dependency graphs",
    "frontend, backend, databases and combined launchers", "health checks, ports, logs and local dashboards",
    "Chrome extensions and Manifest V2/V3", "MCP servers, handshake, tools and configuration",
    "plugins, skills, resources and isolated installation", "GitHub Releases, Pages and application stores",
    "WinGet, Chocolatey, Scoop and App Installer", "unit, integration and smoke testing",
    "installation, upgrade, repair and removal", "caches, lockfiles, toolchains and mirrors",
    "timeouts, resources, cost and large queues", "secret safety, licenses and vulnerabilities",
    "isolation, containers and disposable runners", "reports, diagnostics and classified failures",
    "observability, metrics and trends", "API, webhooks, callbacks and idempotency",
    "drag-and-drop UI and saved profiles", "receipts, tutorials and offline documentation",
    "macOS DMG, PKG and universal binaries", "Linux AppImage, DEB, RPM and Flatpak",
    "Rust, Go, Java and Kotlin multiplatform builds", "PHP, Ruby, Swift and additional ecosystems",
    "HTA, WebView, Electron and Tauri", "legacy migration and discontinued runtimes",
    "data and configuration compatibility", "WCAG accessibility, keyboard and contrast",
    "translation, RTL, local formats and time zones", "governance, RBAC and dual approval",
    "privacy, retention and data residency", "multi-tenancy, quotas and cache isolation",
    "deterministic builds and independent comparison", "chaos tests, network failures and recovery",
    "AI-assisted planning and causal graphs", "Erlang, Haskell, OCaml, Julia, R, Nim, Zig and WASI",
    "Arduino, ESP, Zephyr, UF2 and firmware", "advanced accessibility and localization audits",
    "modernization, contracts and future compatibility", "fuzzing, properties and semantic regression",
    "Intune, GPO, MST, Server Core and Windows services", "air-gap, USB media, volumes and verified transfer",
    "drivers, DPAPI, local databases and backups", "SIEM, policies, secure APIs and analytics",
)

CONTROLS = (
    ("detect", "Detect {epic} from bounded declarative evidence and record the matched rule.", "A fixture is classified deterministically and reports its evidence paths."),
    ("plan", "Represent {epic} in the versioned build-plan schema without executing source instructions.", "Schema validation accepts the fixture and rejects missing required fields."),
    ("configure", "Expose validated configuration for {epic} with safe defaults and explicit overrides.", "Tests cover the default, one valid override and rejection of unsafe input."),
    ("execute", "Provide an isolated adapter that performs the supported {epic} operation reproducibly.", "An integration fixture runs the adapter using pinned inputs and exits successfully."),
    ("package", "Normalize outputs for {epic} into named, versioned artifacts and a manifest.", "The fixture produces non-empty artifacts whose names and manifest match the plan."),
    ("verify", "Verify the usable result of {epic} with an automated format-specific smoke test.", "The smoke test checks the produced artifact rather than only the build command."),
    ("secure", "Apply least-privilege, path-safety and secret-handling policy to {epic}.", "Negative tests block traversal, injection and accidental secret publication."),
    ("diagnose", "Emit structured diagnostics and remediation guidance for failures in {epic}.", "A forced failure yields a stable error code, stage and actionable message."),
    ("recover", "Define retry, cleanup and rollback behavior for interrupted {epic} operations.", "An interruption test leaves no falsely successful artifact and can be retried safely."),
    ("document", "Document support boundaries, commands, evidence and external prerequisites for {epic}.", "Documentation links implementation, tests and immutable real-build evidence."),
)

STATUSES = {"planned", "implemented", "verified", "external-blocked", "not-applicable"}


@dataclass(frozen=True)
class Item:
    id: str
    epic: str
    control: str
    requirement: str
    status: str
    acceptance: tuple[str, ...]
    code_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    dependencies: tuple[str, ...]
    external_requirements: tuple[str, ...]


# Promotions are intentionally narrow.  A whole epic is never promoted because
# one adapter exists: every status is supported by item-specific references.
IMPLEMENTED: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "AP-001": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-002": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-003": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-007": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-011": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-012": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-017": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-201": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-203": (("autopack/package-extension.py",), ("tests/test_package_extension.py",)),
    "AP-204": (("autopack/package-extension.py", ".github/workflows/autopack-v4.yml"), ("tests/test_package_extension.py",)),
    "AP-205": (("autopack/package-extension.py",), ("tests/test_package_extension.py",)),
    "AP-206": (("autopack/package-extension.py",), ("tests/test_package_extension.py",)),
    "AP-207": (("autopack/package-extension.py",), ("tests/test_package_extension.py",)),
    "AP-211": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-214": (("autopack/package-bundle.py", ".github/workflows/autopack-v4.yml"), ("tests/test_package_bundle.py",)),
    "AP-215": (("autopack/package-bundle.py",), ("tests/test_package_bundle.py",)),
    "AP-217": (("autopack/package-bundle.py",), ("tests/test_package_bundle.py",)),
    "AP-221": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-254": ((".github/workflows/autopack-v4-ci.yml",), ("tests/test_engine.py", "tests/test_package_extension.py", "tests/test_package_bundle.py")),
    "AP-297": ((".github/workflows/autopack-v4.yml", ".github/workflows/autopack-v4-ci.yml"), (".github/workflows/autopack-v4-ci.yml",)),
    "AP-481": (("autopack/engine.py",), ("tests/test_engine.py",)),
    "AP-485": (("autopack/package-extension.py", "autopack/package-bundle.py"), ("tests/test_package_extension.py", "tests/test_package_bundle.py")),
    "AP-486": (("autopack/package-extension.py", "autopack/package-bundle.py"), ("tests/test_package_extension.py", "tests/test_package_bundle.py")),
}

EXTERNAL_BLOCKED = {
    "AP-044": ("Android release keystore and its protected passwords",),
    "AP-137": ("Trusted code-signing identity or certificate and protected private key",),
    "AP-234": ("Developer/store account and publication credentials for the selected application store",),
    "AP-246": ("Publisher accounts and tokens for external package repositories",),
    "AP-526": ("Representative physical firmware target and controlled flashing fixture",),
    "AP-566": ("Managed Windows/Intune tenant and representative enrolled endpoint",),
    "AP-576": ("Representative removable media and an isolated air-gap verification environment",),
    "AP-586": ("Compatible hardware plus a trusted Windows driver-signing identity",),
}


def build_catalog() -> tuple[Item, ...]:
    items: list[Item] = []
    for epic_index, epic in enumerate(EPICS):
        for control_index, (control, requirement, acceptance) in enumerate(CONTROLS):
            number = epic_index * len(CONTROLS) + control_index + 1
            dependencies = () if control_index == 0 else (f"AP-{number - 1:03d}",)
            item_id = f"AP-{number:03d}"
            code_refs, test_refs = IMPLEMENTED.get(item_id, ((), ()))
            external = EXTERNAL_BLOCKED.get(item_id, ())
            status = "implemented" if item_id in IMPLEMENTED else "external-blocked" if external else "planned"
            items.append(Item(item_id, epic, control, requirement.format(epic=epic), status,
                              (acceptance,), code_refs, test_refs, (), dependencies, external))
    return tuple(items)


def validate(items: tuple[Item, ...]) -> list[str]:
    errors: list[str] = []
    expected = [f"AP-{number:03d}" for number in range(1, 601)]
    ids = [item.id for item in items]
    if len(items) != 600:
        errors.append(f"expected 600 items, found {len(items)}")
    if ids != expected:
        errors.append("IDs must be unique, contiguous and ordered AP-001..AP-600")
    known = set(ids)
    for item in items:
        if item.status not in STATUSES:
            errors.append(f"{item.id}: invalid status {item.status}")
        if not item.requirement.strip() or not item.acceptance:
            errors.append(f"{item.id}: requirement and acceptance are mandatory")
        if any(dep not in known or dep >= item.id for dep in item.dependencies):
            errors.append(f"{item.id}: dependencies must reference preceding catalog items")
        if item.status in {"implemented", "verified"} and (not item.code_refs or not item.test_refs):
            errors.append(f"{item.id}: {item.status} requires code_refs and test_refs")
        if item.status == "verified" and not any("/actions/runs/" in value for value in item.evidence_urls):
            errors.append(f"{item.id}: verified requires an immutable workflow-run URL")
        if item.status != "verified" and item.evidence_urls:
            errors.append(f"{item.id}: evidence_urls are reserved for verified items")
        if item.status == "external-blocked" and not item.external_requirements:
            errors.append(f"{item.id}: external-blocked requires named external requirements")
        if item.status != "external-blocked" and item.external_requirements:
            errors.append(f"{item.id}: external requirements require external-blocked status")
        for reference in (*item.code_refs, *item.test_refs):
            candidate = (AUTOPACK_ROOT / reference).resolve()
            if not candidate.is_file() and reference.startswith("autopack/"):
                candidate = (AUTOPACK_ROOT / reference.removeprefix("autopack/")).resolve()
            if not candidate.is_file() and reference.startswith(".github/"):
                candidate = (AUTOPACK_ROOT.parent / reference).resolve()
            root = AUTOPACK_ROOT.resolve()
            permitted_roots = (root, root.parent)
            if not any(permitted in candidate.parents for permitted in permitted_roots) or not candidate.is_file():
                errors.append(f"{item.id}: missing local reference {reference}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    items = build_catalog()
    errors = validate(items)
    if errors:
        print("\n".join(errors))
        return 1
    encoded = json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    elif not args.check:
        print(encoded, end="")
    if args.check:
        print(f"catalog valid: {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
