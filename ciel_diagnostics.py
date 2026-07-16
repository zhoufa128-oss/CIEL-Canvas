"""Privacy-minimized diagnostic export for portable CIEL Canvas installs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Tuple

from ciel_paths import PATHS


SAFE_RELEASE_FIELDS = {
    "product_id",
    "product_name",
    "release_version",
    "display_version",
    "internal_build",
    "data_schema_version",
    "platform",
    "architecture",
    "package_type",
    "minimum_macos",
}
SAFE_INSTALL_FIELDS = {
    "product_id",
    "product_name",
    "installed_release",
    "data_schema_version",
    "platform",
    "architecture",
    "initialized",
}
SAFE_LOG_MARKERS = {
    "START",
    "FINAL_RESULT",
    "VERSION",
    "HEALTH",
    "LAUNCHER",
    "UPDATE",
    "ROLLBACK",
    "PORT",
    "PID",
    "PROCESS",
    "ERROR",
}
SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization|api[_-]?key|access[_-]?key|secret[_-]?key|token|cookie)\s*[:=]\s*\S+"),
    re.compile(r"\b(sk-|ghp_|hf_|AIza|AKIA)[A-Za-z0-9_\-]{6,}"),
]


def runtime_metadata_self_test() -> Dict:
    """Exercise metadata APIs and core frozen imports without exposing paths."""
    from pydantic import BaseModel
    import fastapi
    import uvicorn
    import websockets
    import websockets.server

    class Probe(BaseModel):
        name: str
        count: int

    model = Probe(name="ciel", count=1)
    packages = {}
    for distribution_name in ("importlib-metadata", "pydantic", "websockets"):
        dist = importlib.metadata.distribution(distribution_name)
        metadata = importlib.metadata.metadata(distribution_name)
        files = dist.files
        packages[distribution_name] = {
            "version": importlib.metadata.version(distribution_name),
            "metadata_name": metadata.get("Name", ""),
            "files_available": files is not None,
        }
    return {
        "ok": model.name == "ciel" and model.count == 1,
        "pydantic_model_validation": True,
        "fastapi_import": bool(fastapi.__version__),
        "uvicorn_import": bool(uvicorn.__version__),
        "websockets_import": bool(websockets.__version__),
        "websockets_server_import": True,
        "packages": packages,
        "record_required_by_ciel": False,
    }


def _safe_json(path: Path, fields: Iterable[str]) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return {key: raw.get(key) for key in fields if key in raw}
    except Exception as exc:
        return {"read_error": type(exc).__name__}


def _count_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file() and not item.is_symlink())


def _health() -> Dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:3015/api/app-info", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        return {"reachable": True, "version": payload.get("version", "")}
    except Exception as exc:
        return {"reachable": False, "error": type(exc).__name__}


def _verify_manifest() -> Dict:
    manifest = PATHS.app_root / "SHA256SUMS.txt"
    if not manifest.is_file():
        return {"present": False, "checked": 0, "failed": 0}
    checked = 0
    failed = 0
    for raw in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip() or "  " not in raw:
            continue
        expected, rel = raw.split("  ", 1)
        target = (PATHS.app_root / rel).resolve()
        if PATHS.app_root != target and PATHS.app_root not in target.parents:
            failed += 1
            continue
        checked += 1
        try:
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != expected:
                failed += 1
        except Exception:
            failed += 1
    return {"present": True, "checked": checked, "failed": failed}


def _safe_log_tail(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    except Exception:
        return ""
    output = []
    for line in lines:
        upper = line.upper()
        if not any(marker in upper for marker in SAFE_LOG_MARKERS):
            continue
        for pattern in SECRET_PATTERNS:
            line = pattern.sub("[REDACTED]", line)
        output.append(line[:1000])
    return "\n".join(output) + ("\n" if output else "")


def export_diagnostics() -> Path:
    if not PATHS.portable:
        raise RuntimeError("诊断导出只用于 Portable 发行版")
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output = PATHS.diagnostics_dir / f"CIEL_Diagnostics_{timestamp}.zip"
    suffix = 1
    while output.exists() or output.with_suffix(".zip.partial").exists():
        output = PATHS.diagnostics_dir / f"CIEL_Diagnostics_{timestamp}-{suffix}.zip"
        suffix += 1
    partial = output.with_suffix(".zip.partial")
    release = _safe_json(PATHS.app_root / "release.json", SAFE_RELEASE_FIELDS)
    install = _safe_json(PATHS.install_file, SAFE_INSTALL_FIELDS)
    summary = {
        "product": "CIEL Canvas",
        "macos": platform.mac_ver()[0],
        "architecture": platform.machine(),
        "health": _health(),
        "counts": {
            "canvases": _count_files(PATHS.canvases_dir),
            "assets": _count_files(PATHS.assets_dir),
            "outputs": _count_files(PATHS.generated_output_dir),
        },
        "application_integrity": _verify_manifest(),
    }
    log_candidates: Tuple[Tuple[str, Path], ...] = (
        ("logs/launcher.log", PATHS.logs_dir / "ciel-canvas-launcher.log"),
        ("logs/server.log", PATHS.logs_dir / "ciel-server.log"),
        ("logs/update.log", PATHS.logs_dir / "update.log"),
    )
    with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("release.json", json.dumps(release, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("install.json", json.dumps(install, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        for archive_name, source in log_candidates:
            safe_text = _safe_log_tail(source)
            if safe_text:
                archive.writestr(archive_name, safe_text)
    partial.replace(output)
    return output
