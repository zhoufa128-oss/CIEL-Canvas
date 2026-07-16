#!/usr/bin/env python3
"""Three-layer sensitive scanner for CIEL release directories and ZIP names."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List


KEYWORDS = (
    ".env",
    "API/.env",
    "sk-",
    "Bearer",
    "Authorization:",
    "AIza",
    "AKIA",
    "ghp_",
    "hf_",
    "PRIVATE KEY",
    "auditfix",
    "candidate",
    "TEST_CIEL_SECRET_DO_NOT_SHIP_7341",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{12,}"),
    re.compile(r"\bhf_[A-Za-z0-9_-]{12,}"),
    re.compile(r"\bAKIA[A-Z0-9]{12,}"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def add(result: Dict[str, List[Dict]], category: str, layer: str, path: str, marker: str) -> None:
    item = {"layer": layer, "path": path, "marker": marker}
    if item not in result[category]:
        result[category].append(item)


def markers() -> tuple[str, str, str]:
    personal_root = os.environ.get("CIEL_FORBIDDEN_PERSONAL_ROOT", "").strip()
    username = Path(personal_root).name if personal_root else ""
    build_marker = "CIEL发行架构/build-env"
    return personal_root, username, build_marker


def classify_text(result: Dict[str, List[Dict]], layer: str, relative: str, text: str) -> None:
    personal_root, username, build_marker = markers()
    for marker in (personal_root, username, "Codex工作区", build_marker):
        if marker and marker in text:
            add(result, "absolute_paths", layer, relative, marker)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            add(result, "high_confidence_secrets", layer, relative, pattern.pattern)
    if "TEST_CIEL_SECRET_DO_NOT_SHIP_7341" in text:
        add(result, "test_strings", layer, relative, "TEST_CIEL_SECRET_DO_NOT_SHIP_7341")
    for keyword in KEYWORDS:
        if keyword in text and keyword != "TEST_CIEL_SECRET_DO_NOT_SHIP_7341":
            add(result, "ordinary_keyword_hits", layer, relative, keyword)


def scan_directory(root: Path) -> Dict:
    result: Dict[str, List[Dict]] = {
        "high_confidence_secrets": [],
        "absolute_paths": [],
        "ordinary_keyword_hits": [],
        "test_strings": [],
        "filename_hits": [],
    }
    file_count = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink() or not path.is_file():
            continue
        file_count += 1
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        is_text = b"\0" not in data[:8192]
        if is_text:
            classify_text(result, "text", relative, data.decode("utf-8", errors="replace"))
        else:
            strings = subprocess.run(
                ["/usr/bin/strings", "-a", str(path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            ).stdout.decode("utf-8", errors="replace")
            classify_text(result, "binary_strings", relative, strings)
        for keyword in KEYWORDS:
            if keyword.lower() in relative.lower():
                add(result, "filename_hits", "directory_name", relative, keyword)
    result["file_count"] = file_count
    return result


def scan_zip_names(zip_path: Path, result: Dict) -> int:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    personal_root, username, build_marker = markers()
    for name in names:
        for marker in (personal_root, username, "Codex工作区", build_marker):
            if marker and marker.lower() in name.lower():
                add(result, "absolute_paths", "zip_name", name, marker)
        for keyword in KEYWORDS:
            if keyword.lower() in name.lower():
                add(result, "filename_hits", "zip_name", name, keyword)
    return len(names)


def write_markdown(path: Path, directory: Path, zip_path: Path, result: Dict) -> None:
    lines = [
        "# CIEL Canvas 三层敏感扫描结果",
        "",
        "扫描层：文本文件、二进制 `strings`、ZIP 路径与文件名。扫描器未设置任何个人路径允许项。",
        "",
        f"- 目录文件数：{result['file_count']}",
        f"- ZIP 条目数：{result['zip_entry_count']}",
        f"- 高置信密钥：{len(result['high_confidence_secrets'])}",
        f"- 构建机绝对路径：{len(result['absolute_paths'])}",
        f"- 测试秘密：{len(result['test_strings'])}",
        f"- 文件名命中：{len(result['filename_hits'])}",
        f"- 普通依赖/代码关键词命中：{len(result['ordinary_keyword_hits'])}",
        "",
    ]
    for title, key in (
        ("高置信密钥", "high_confidence_secrets"),
        ("构建机绝对路径", "absolute_paths"),
        ("测试字符串", "test_strings"),
        ("文件名命中", "filename_hits"),
        ("普通依赖或代码关键词", "ordinary_keyword_hits"),
    ):
        lines.extend([f"## {title}", ""])
        items = result[key]
        if not items:
            lines.append("无。")
        else:
            for item in items:
                lines.append(f"- `{item['layer']}` / `{item['path']}` / `{item['marker']}`")
        lines.append("")
    lines.extend([
        "## 判定",
        "",
        "普通关键词命中只表示发行二进制中包含请求头或配置功能代码，不等于包含真实凭据；高置信密钥、个人绝对路径和测试秘密必须为零。",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    zip_path = args.zip_path.resolve()
    result = scan_directory(directory)
    result["zip_entry_count"] = scan_zip_names(zip_path, result)
    result["directory_sha256_inventory"] = hashlib.sha256(
        "\n".join(sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file())).encode("utf-8")
    ).hexdigest()
    result["passed"] = not result["high_confidence_secrets"] and not result["absolute_paths"] and not result["test_strings"]
    args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.markdown_output, directory, zip_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
