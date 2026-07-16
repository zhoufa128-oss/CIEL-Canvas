#!/usr/bin/env python3
"""Fail-closed verifier for CIEL Canvas full and update packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple


PRODUCT_ID = "local.ciel.canvas"
EXPECTED_INTERNAL_BUILD = "2026.07.13.ciel-canvas-portable-release-rc1"
FORBIDDEN_NAMES = {".DS_Store", "__pycache__", ".env", "API", "data", "assets", "output", ".run", ".venv"}
FORBIDDEN_PATH_PARTS = {"UserData"}
STATIC_HIGH_CONFIDENCE_BYTES = (
    b"TEST_CIEL_SECRET_DO_NOT_SHIP_7341",
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
)
TOKEN_PATTERNS = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(rb"\bghp_[A-Za-z0-9]{12,}"),
    re.compile(rb"\bhf_[A-Za-z0-9_-]{12,}"),
    re.compile(rb"\bAKIA[A-Z0-9]{12,}"),
    re.compile(rb"\bAIza[A-Za-z0-9_-]{20,}"),
    re.compile(rb"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~-]{10,}"),
)
DEVELOPMENT_MARKERS = (
    b"Codex\xe5\xb7\xa5\xe4\xbd\x9c\xe5\x8c\xba",
    b"/Desktop/\xe6\x97\xa0\xe9\x99\x90\xe7\x94\xbb\xe5\xb8\x83/02_\xe5\xbd\x93\xe5\x89\x8d\xe4\xbd\xbf\xe7\x94\xa8/",
)


def high_confidence_bytes() -> Tuple[bytes, ...]:
    dynamic_root = os.environ.get("CIEL_FORBIDDEN_PERSONAL_ROOT", "").strip()
    markers = list(STATIC_HIGH_CONFIDENCE_BYTES)
    if dynamic_root:
        markers.append(dynamic_root.encode("utf-8"))
        username = Path(dynamic_root).name
        if username:
            markers.append(username.encode("utf-8"))
    return tuple(markers)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            link_text = os.readlink(path)
            if os.path.isabs(link_text):
                raise RuntimeError(f"发行内容含绝对软链接：{path} -> {link_text}")
            resolved = path.resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                raise RuntimeError(f"发行内容软链接越界：{path} -> {link_text}")
            continue
        if path.is_file():
            yield path


def scan_file(path: Path) -> List[str]:
    findings: List[str] = []
    with path.open("rb") as handle:
        tail = b""
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            data = tail + block
            for marker in high_confidence_bytes() + DEVELOPMENT_MARKERS:
                if marker in data:
                    findings.append(marker.decode("utf-8", errors="replace"))
            for pattern in TOKEN_PATTERNS:
                if pattern.search(data):
                    findings.append(pattern.pattern.decode("ascii", errors="replace"))
            tail = data[-512:]
    if path.stat().st_size >= 4096:
        strings = subprocess.run(
            ["/usr/bin/strings", "-a", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        ).stdout
        for marker in high_confidence_bytes() + DEVELOPMENT_MARKERS:
            if marker in strings and marker.decode("utf-8", errors="replace") not in findings:
                findings.append(marker.decode("utf-8", errors="replace"))
    return findings


def verify_no_metadata(root: Path) -> None:
    bad = []
    for item in root.rglob("*"):
        if item.name == ".DS_Store" or item.name.startswith("._") or "__MACOSX" in item.parts:
            bad.append(str(item))
    if bad:
        raise RuntimeError("发现禁止的文件系统元数据：\n" + "\n".join(bad[:20]))


def verify_release(root: Path) -> dict:
    app_root = root / "Application" / "current"
    user_data = root / "UserData"
    required = [
        root / "CIEL Canvas.app",
        app_root / "bin" / "ciel-server" / "ciel-server",
        app_root / "bin" / "start-ciel-release.sh",
        app_root / "static",
        app_root / "brand" / "ciel" / "brand.json",
        app_root / "defaults" / "user-data" / "welcome-canvas.json",
        app_root / "VERSION",
        app_root / "release.json",
        app_root / "SHA256SUMS.txt",
        root / "Help",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("发行目录缺少必要内容：\n" + "\n".join(missing))
    release = json.loads((app_root / "release.json").read_text(encoding="utf-8"))
    if release.get("product_id") != PRODUCT_ID:
        raise RuntimeError("release.json product_id 不匹配")
    if release.get("internal_build") != EXPECTED_INTERNAL_BUILD:
        raise RuntimeError("release.json internal_build 不匹配")
    if (user_data / "install.json").exists():
        raise RuntimeError("正式包不得预置 UserData/install.json")
    for private_name in ("canvases", "assets", "thumbnails", "outputs", "config", "logs", "runtime", "backups", "diagnostics"):
        private_dir = user_data / private_name
        if not private_dir.is_dir():
            raise RuntimeError(f"UserData 空目录缺失：{private_name}")
        if any(private_dir.iterdir()):
            raise RuntimeError(f"UserData 必须为空：{private_name}")
    manifest_failures = []
    for line in (app_root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = (app_root / relative).resolve()
        if app_root.resolve() not in target.parents or not target.is_file() or sha256_file(target) != expected:
            manifest_failures.append(relative)
    if manifest_failures:
        raise RuntimeError("Application 文件清单校验失败：" + ", ".join(manifest_failures[:20]))
    verify_no_metadata(root)
    findings = []
    for path in iter_files(root):
        for finding in scan_file(path):
            findings.append(f"{path.relative_to(root)} :: {finding}")
    if findings:
        raise RuntimeError("发现高置信敏感信息或开发绝对路径：\n" + "\n".join(findings[:50]))
    return {"files": sum(1 for _ in iter_files(root)), "release": release, "sensitive_findings": 0}


def verify_update(root: Path) -> dict:
    payload = root / "payload" / "Application" / "current"
    plist_path = root / "update.plist"
    sums = root / "SHA256SUMS.txt"
    if not payload.is_dir() or not plist_path.is_file() or not sums.is_file():
        raise RuntimeError("升级包结构不完整")
    if any("UserData" in path.parts for path in root.rglob("*")):
        raise RuntimeError("升级包不得包含 UserData")
    with plist_path.open("rb") as handle:
        metadata = plistlib.load(handle)
    if metadata.get("product_id") != PRODUCT_ID:
        raise RuntimeError("update.plist product_id 不匹配")
    verify_no_metadata(root)
    findings = []
    for path in iter_files(root):
        for finding in scan_file(path):
            findings.append(f"{path.relative_to(root)} :: {finding}")
    if findings:
        raise RuntimeError("升级包发现敏感信息：\n" + "\n".join(findings[:50]))
    return {"files": sum(1 for _ in iter_files(root)), "metadata": metadata, "sensitive_findings": 0}


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    bad = [name for name in names if "__MACOSX" in name or "/.DS_Store" in name or "/._" in name]
    if bad:
        raise RuntimeError("ZIP 包含禁止元数据：" + ", ".join(bad[:20]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("release", "update", "zip"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    path = args.path.resolve()
    if args.kind == "release":
        result = verify_release(path)
    elif args.kind == "update":
        result = verify_update(path)
    else:
        verify_zip(path)
        result = {"zip": str(path), "metadata_clean": True}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
