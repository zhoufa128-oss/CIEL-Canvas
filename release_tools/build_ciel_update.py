#!/usr/bin/env python3
"""Build a data-free, offline CIEL Canvas Application/current update package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import shutil
import stat
import subprocess
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
TEMPLATES = TOOLS / "templates" / "update"
PRODUCT_ID = "local.ciel.canvas"


class UpdateBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    if result.returncode:
        raise UpdateBuildError(f"命令失败({result.returncode})：{' '.join(command)}\n{result.stdout[-8000:]}")


def ensure_inside(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise UpdateBuildError(f"路径逃逸：{path}") from exc


def copy_tree_without_symlinks(source: Path, destination: Path) -> None:
    """Copy a runtime tree while dereferencing only internal symlinks."""
    destination.mkdir(parents=True, exist_ok=False)
    source_resolved = source.resolve()
    for current, dirs, files in os.walk(source, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(source)
        target_dir = destination / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        for name in list(dirs):
            item = current_path / name
            target = target_dir / name
            if item.is_symlink():
                dirs.remove(name)
                resolved = item.resolve(strict=True)
                ensure_inside(resolved, source_resolved)
                shutil.copytree(resolved, target, symlinks=False, copy_function=shutil.copyfile)
            else:
                target.mkdir(parents=True, exist_ok=True)

        for name in files:
            item = current_path / name
            relative = item.relative_to(source)
            if relative == Path("SHA256SUMS.txt"):
                continue
            target = target_dir / name
            if item.is_symlink():
                resolved = item.resolve(strict=True)
                ensure_inside(resolved, source_resolved)
                if not resolved.is_file():
                    raise UpdateBuildError(f"未知软链接类型：{item}")
                shutil.copyfile(resolved, target)
                source_mode = resolved.stat().st_mode
            else:
                shutil.copyfile(item, target)
                source_mode = item.stat().st_mode
            os.chmod(target, 0o755 if source_mode & stat.S_IXUSR else 0o644)


def manifest_lines(root: Path, *, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise UpdateBuildError(f"更新 payload 禁止软链接：{path}")
        relative = path.relative_to(root).as_posix()
        if relative == "SHA256SUMS.txt":
            continue
        if "\n" in relative or "\r" in relative:
            raise UpdateBuildError(f"文件名包含换行：{relative!r}")
        lines.append(f"{sha256(path)}  {prefix}{relative}")
    return lines


def assert_no_private_payload(root: Path) -> None:
    forbidden_names = {"UserData", ".env", "API", "data", "assets", "output", "logs", "runtime"}
    for path in root.rglob("*"):
        relative_parts = path.relative_to(root).parts
        if "UserData" in relative_parts:
            raise UpdateBuildError(f"更新包包含 UserData：{path}")
        if path.name == ".env" or path.name == "API.env":
            raise UpdateBuildError(f"更新包包含密钥文件：{path}")
    personal_root = os.environ.get("CIEL_FORBIDDEN_PERSONAL_ROOT", "").strip()
    if not personal_root and len(TOOLS.parents) > 3:
        personal_root = str(TOOLS.parents[3])
    markers = [b"TEST_CIEL_SECRET_DO_NOT_SHIP_7341", "Codex工作区".encode("utf-8")]
    if personal_root:
        markers.append(personal_root.encode("utf-8"))
    for path in (item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        for marker in markers:
            if marker in payload:
                raise UpdateBuildError(f"更新包命中禁止内容 {marker!r}：{path}")


def compile_installer(package_root: Path, icon: Path) -> None:
    source = TEMPLATES / "Install CIEL Update.applescript"
    shell = TEMPLATES / "install-ciel-update.sh"
    app = package_root / "安装 CIEL 更新.app"
    run(["/usr/bin/osacompile", "-o", str(app), str(source)])
    resources = app / "Contents" / "Resources"
    shutil.copyfile(shell, resources / "install-ciel-update.sh")
    os.chmod(resources / "install-ciel-update.sh", 0o755)
    if icon.exists():
        shutil.copyfile(icon, resources / "AppIcon.icns")
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    plist.update(
        {
            "CFBundleName": "安装 CIEL 更新",
            "CFBundleDisplayName": "安装 CIEL 更新",
            "CFBundleIdentifier": "local.ciel.canvas.updater",
            "CFBundleIconFile": "AppIcon.icns",
            "CFBundleExecutable": "applet",
            "CFBundlePackageType": "APPL",
        }
    )
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle, fmt=plistlib.FMT_XML, sort_keys=True)
    run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)])
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])


def build(args: argparse.Namespace) -> dict[str, object]:
    source = Path(args.application).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not source.is_dir() or not (source / "release.json").is_file():
        raise UpdateBuildError(f"Application/current 来源无效：{source}")
    source_release = json.loads((source / "release.json").read_text(encoding="utf-8"))
    if source_release.get("product_id") != PRODUCT_ID:
        raise UpdateBuildError("来源 product_id 不匹配")
    if args.to_version in {args.from_min, args.from_max}:
        raise UpdateBuildError("正式构建不允许目标版本等于来源版本")
    architecture = args.architecture or source_release.get("architecture") or os.uname().machine
    package_name = args.name or f"CIEL_Canvas_{args.to_version}_macOS_{architecture}_Update"
    package_root = output_dir / package_name / "CIEL Canvas Update"
    package_parent = package_root.parent
    zip_path = output_dir / f"{package_name}.zip"
    sha_path = output_dir / f"{package_name}_SHA256.txt"
    for target in (package_parent, zip_path, sha_path):
        if target.exists():
            raise UpdateBuildError(f"拒绝覆盖现有输出：{target}")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_current = package_root / "payload" / "Application" / "current"
    payload_current.parent.mkdir(parents=True, exist_ok=True)
    copy_tree_without_symlinks(source, payload_current)

    release_path = payload_current / "release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release.update(
        {
            "release_version": args.to_version,
            "internal_build": args.to_internal_build,
            "package_type": "application-update",
            "architecture": architecture,
            "platform": "macos",
        }
    )
    release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (payload_current / "VERSION").write_text(args.to_internal_build + "\n", encoding="utf-8")
    current_manifest = manifest_lines(payload_current)
    (payload_current / "SHA256SUMS.txt").write_text("\n".join(current_manifest) + "\n", encoding="utf-8")

    icon = payload_current / "brand" / "ciel" / "AppIcon.icns"
    compile_installer(package_root, icon)
    package_manifest = manifest_lines(payload_current, prefix="payload/Application/current/")
    manifest_path = package_root / "SHA256SUMS.txt"
    manifest_path.write_text("\n".join(package_manifest) + "\n", encoding="utf-8")
    update_metadata = {
        "product_id": PRODUCT_ID,
        "from_version_min": args.from_min,
        "from_version_max": args.from_max,
        "to_version": args.to_version,
        "to_internal_build": args.to_internal_build,
        "platform": "macos",
        "architecture": architecture,
        "data_schema_version": int(source_release.get("data_schema_version", 1)),
        "package_type": "application-update",
        "payload_hash": sha256(manifest_path),
    }
    with (package_root / "update.plist").open("wb") as handle:
        plistlib.dump(update_metadata, handle, fmt=plistlib.FMT_XML, sort_keys=True)
    (package_root / "更新说明.md").write_text(
        f"# CIEL Canvas {args.to_version} 离线更新\n\n"
        "双击“安装 CIEL 更新.app”。更新只替换 Application/current；UserData 不进入更新包，也不会被覆盖。\n",
        encoding="utf-8",
    )
    assert_no_private_payload(package_root)
    run(["/usr/bin/ditto", "--norsrc", "--noextattr", "-c", "-k", "--keepParent", str(package_root), str(zip_path)])
    zip_hash = sha256(zip_path)
    sha_path.write_text(f"{zip_hash}  {zip_path.name}\n", encoding="utf-8")
    return {
        "package_directory": str(package_parent),
        "zip": str(zip_path),
        "zip_sha256": zip_hash,
        "sha256_file": str(sha_path),
        "to_version": args.to_version,
        "to_internal_build": args.to_internal_build,
        "architecture": architecture,
        "payload_manifest_sha256": update_metadata["payload_hash"],
        "contains_user_data": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--application", required=True, help="已构建发行版的 Application/current")
    parser.add_argument("--from-min", required=True)
    parser.add_argument("--from-max", required=True)
    parser.add_argument("--to-version", required=True)
    parser.add_argument("--to-internal-build", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--architecture")
    parser.add_argument("--name")
    return parser.parse_args()


def main() -> int:
    try:
        result = build(parse_args())
    except Exception as exc:
        print(f"BUILD_FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
