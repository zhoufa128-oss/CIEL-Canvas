#!/usr/bin/env python3
"""Build CIEL Canvas for Apple Silicon Macs (M1 through M5).

The application and web UI are shared with the Windows release.  This builder
only changes the packaging/runtime layer: PyInstaller targets macOS arm64,
the launcher is a native macOS .app, and all mutable data stays in UserData.
It intentionally refuses to build on Windows; a Mach-O binary cannot be
validated or produced honestly from this workstation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source"
TOOLS = SOURCE / "release_tools"
TEMPLATES = TOOLS / "templates"
BRAND = ROOT / "Brand"
WORK_ROOT = ROOT / "Build" / "_macos_work"
OUTPUT_ROOT = ROOT / "BuildOutput" / "macOS_arm64"
REQUIREMENTS = ROOT / "Build" / "requirements-build-macos-arm64.txt"
INTERNAL_BUILD = "2026.07.13.ciel-canvas-portable-release-rc1"
RELEASE_VERSION = "1.0.0"
PRODUCT_ID = "local.ciel.canvas"
PORT = "3015"


class BuildFailure(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None) -> str:
    process = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if process.returncode:
        raise BuildFailure(f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout[-12000:]}")
    return process.stdout


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise BuildFailure(f"missing source tree: {source}")
    if target.exists():
        raise BuildFailure(f"refusing to overwrite: {target}")
    shutil.copytree(source, target, symlinks=True)
    for item in target.rglob("*"):
        if item.is_symlink():
            link = os.readlink(item)
            if os.path.isabs(link):
                raise BuildFailure(f"absolute symlink in release: {item} -> {link}")
            resolved = item.resolve()
            try:
                resolved.relative_to(target.resolve())
            except ValueError as exc:
                raise BuildFailure(f"escaping symlink in release: {item} -> {link}") from exc


def copy_file(source: Path, target: Path, executable: bool = False) -> None:
    if not source.is_file() or source.is_symlink():
        raise BuildFailure(f"missing regular file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    os.chmod(target, 0o755 if executable else 0o644)


def tree_manifest(root: Path) -> str:
    lines: list[str] = []
    for item in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if item.is_file() and not item.is_symlink():
            lines.append(f"{sha256(item)}  {item.relative_to(root).as_posix()}")
    return "\n".join(lines) + "\n"


def static_self_check() -> dict:
    required = [
        SOURCE / "main.py",
        SOURCE / "ciel_paths.py",
        SOURCE / "ciel_diagnostics.py",
        SOURCE / "static" / "index.html",
        SOURCE / "static" / "brand" / "ciel" / "brand.json",
        SOURCE / "static" / "brand" / "ciel" / "CIEL_Canvas_Poster_Landscape.png",
        SOURCE / "static" / "brand" / "ciel" / "CIEL_Canvas_Poster_Portrait.png",
        SOURCE / "workflows",
        REQUIREMENTS,
        TOOLS / "ciel-server.spec",
        TEMPLATES / "launcher" / "start-ciel-release.sh",
        TEMPLATES / "launcher" / "CIEL Canvas Release.applescript",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise BuildFailure("missing macOS release inputs:\n" + "\n".join(missing))
    html = (SOURCE / "static" / "index.html").read_text(encoding="utf-8")
    markers = ("top-promo-toggle", "top-promo-banner", "https://pay.ldxp.cn/shop/128")
    missing_markers = [marker for marker in markers if marker not in html]
    if missing_markers:
        raise BuildFailure("shared UI markers missing: " + ", ".join(missing_markers))
    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(SOURCE)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPYCACHEPREFIX": str(WORK_ROOT / "_self_check_pycache")},
    )
    if compile_result.returncode:
        raise BuildFailure("Python syntax check failed:\n" + compile_result.stdout)
    launcher = (TEMPLATES / "launcher" / "start-ciel-release.sh").read_text(encoding="utf-8")
    for marker in ("CIEL_PORTABLE=1", "CIEL_DATA_ROOT", "api/app-info", "PORT_OCCUPIED", "json_raw"):
        if marker not in launcher:
            raise BuildFailure(f"macOS launcher contract missing: {marker}")
    requirements = REQUIREMENTS.read_text(encoding="utf-8")
    for marker in ("PyInstaller==6.15.0", "pydantic==2.13.4", "pydantic-core==2.46.4"):
        if marker not in requirements:
            raise BuildFailure(f"macOS dependency lock missing: {marker}")
    spec = (TOOLS / "ciel-server.spec").read_text(encoding="utf-8")
    if 'target_arch="arm64"' not in spec:
        raise BuildFailure("PyInstaller spec is not pinned to macOS arm64")
    return {
        "source": str(SOURCE),
        "python_compile": "PASS",
        "shared_ui": "PASS",
        "splash_assets": "PASS",
        "launcher_contract": "PASS",
        "target_architecture": "arm64",
        "supported_apple_silicon": ["M1", "M2", "M3", "M4", "M5"],
    }


def require_real_macos_arm64() -> None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise BuildFailure(
            "Mac release build requires a real macOS arm64 host (Apple Silicon M1-M5); "
            f"current host is {platform.system()} {platform.machine()}"
        )


def make_icns(session: Path) -> Path:
    source = BRAND / "CIEL_Mark_Approved_1024.png"
    if not source.is_file():
        raise BuildFailure(f"approved icon source missing: {source}")
    iconset = session / "CIEL_Canvas.iconset"
    iconset.mkdir(parents=True)
    for size in (16, 32, 128, 256, 512, 1024):
        for scale, suffix in ((1, ""), (2, "@2x")):
            pixel = size * scale
            if pixel > 1024:
                continue
            run(["/usr/bin/sips", "-z", str(pixel), str(pixel), str(source), "--out", str(iconset / f"icon_{size}x{size}{suffix}.png")])
    output = session / "AppIcon.icns"
    run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(output)])
    return output


def build_app(release_root: Path, icon: Path) -> Path:
    app = release_root / "CIEL Canvas.app"
    script = TEMPLATES / "launcher" / "CIEL Canvas Release.applescript"
    run(["/usr/bin/osacompile", "-o", str(app), str(script)])
    resources = app / "Contents" / "Resources"
    copy_file(icon, resources / "AppIcon.icns")
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        plist = plistlib.load(handle)
    plist.update({
        "CFBundleName": "CIEL Canvas",
        "CFBundleDisplayName": "CIEL Canvas",
        "CFBundleIdentifier": "local.ciel.canvas.release",
        "CFBundleIconFile": "AppIcon.icns",
        "CFBundleShortVersionString": RELEASE_VERSION,
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "11.0",
        "LSArchitecturePriority": ["arm64"],
    })
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle, fmt=plistlib.FMT_XML, sort_keys=True)
    run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(app)])
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
    return app


def smoke_runtime(server: Path, app_root: Path, user_data: Path, session: Path) -> dict:
    runtime_root = user_data / "runtime"
    for name in ("home", "temp", "cache"):
        (runtime_root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    env = os.environ.copy()
    env.update({
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "CIEL_PORTABLE": "1",
        "CIEL_INSTALL_ROOT": str(app_root.parent.parent),
        "CIEL_APP_ROOT": str(app_root),
        "CIEL_DATA_ROOT": str(user_data),
        "HOME": str(runtime_root / "home"),
        "TMPDIR": str(runtime_root / "temp"),
        "TMP": str(runtime_root / "temp"),
        "TEMP": str(runtime_root / "temp"),
        "XDG_CACHE_HOME": str(runtime_root / "cache"),
        "PYTHONPYCACHEPREFIX": str(runtime_root / "cache" / "pycache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PORT": "31415",
    })
    metadata = run([str(server), "--runtime-metadata-self-test"], env=env, cwd=app_root)
    log_path = session / "macos-runtime.log"
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen([str(server)], env=env, cwd=str(app_root), stdout=log_handle, stderr=subprocess.STDOUT, text=True)
    try:
        health = None
        for _ in range(120):
            if process.poll() is not None:
                break
            try:
                with urllib.request.urlopen("http://127.0.0.1:31415/api/app-info", timeout=1) as response:
                    health = json.loads(response.read().decode("utf-8"))
                if health.get("version") == INTERNAL_BUILD:
                    break
            except Exception:
                time.sleep(.5)
        if not health or health.get("version") != INTERNAL_BUILD:
            raise BuildFailure(f"macOS runtime health failed; exit={process.poll()}")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        log_handle.close()
    return {"metadata_self_test": "PASS", "health": health, "port": 31415, "log": str(log_path), "metadata_tail": metadata[-500:]}


def build_release(output_dir: Path) -> dict:
    require_real_macos_arm64()
    static_self_check()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    session = WORK_ROOT / f"release-{timestamp}-{os.getpid()}"
    session.mkdir(parents=True, exist_ok=False)
    venv = session / "build-env"
    run([sys.executable, "-m", "venv", str(venv)])
    python = venv / "bin" / "python"
    env = os.environ.copy()
    env.update({"CIEL_SOURCE_PROJECT": str(SOURCE), "CIEL_WINDOWS_BUILD": "", "TMPDIR": str(session / "tmp"), "PYTHONDONTWRITEBYTECODE": "1"})
    (session / "tmp").mkdir()
    run([str(python), "-m", "pip", "install", "--upgrade", "pip", "-r", str(REQUIREMENTS)], env=env)
    spec = TOOLS / "ciel-server.spec"
    run([str(venv / "bin" / "pyinstaller"), "--noconfirm", "--clean", "--distpath", str(session / "dist"), "--workpath", str(session / "work"), str(spec)], env=env, cwd=TOOLS)
    runtime = session / "dist" / "ciel-server"
    server = runtime / "ciel-server"
    if not server.is_file():
        raise BuildFailure("PyInstaller did not produce macOS arm64 ciel-server")
    package = session / f"CIEL_Canvas_{RELEASE_VERSION}_macOS_arm64" / "CIEL Canvas"
    app_root = package / "Application" / "current"
    user_data = package / "UserData"
    app_root.mkdir(parents=True)
    for name in ("canvases", "assets", "thumbnails", "outputs", "config", "logs", "runtime", "backups", "diagnostics"):
        (user_data / name).mkdir(parents=True)
    copy_tree(runtime, app_root / "bin" / "ciel-server")
    copy_tree(SOURCE / "static", app_root / "static")
    copy_tree(SOURCE / "static" / "brand", app_root / "brand")
    copy_tree(SOURCE / "workflows", app_root / "workflows")
    copy_tree(TEMPLATES / "defaults", app_root / "defaults")
    copy_tree(TEMPLATES / "help", package / "Help")
    copy_file(TEMPLATES / "launcher" / "start-ciel-release.sh", app_root / "bin" / "start-ciel-release.sh", executable=True)
    (app_root / "VERSION").write_text(INTERNAL_BUILD + "\n", encoding="utf-8")
    (app_root / "release.json").write_text(json.dumps({
        "product_id": PRODUCT_ID,
        "product_name": "CIEL Canvas",
        "release_version": RELEASE_VERSION,
        "display_version": "CIEL 1.0",
        "internal_build": INTERNAL_BUILD,
        "platform": "macos",
        "architecture": "arm64",
        "supported_apple_silicon": ["M1", "M2", "M3", "M4", "M5"],
        "minimum_macos": "11.0",
        "data_schema_version": 1,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (app_root / "SHA256SUMS.txt").write_text(tree_manifest(app_root), encoding="utf-8")
    icon = make_icns(session)
    app = build_app(package, icon)
    smoke = smoke_runtime(app_root / "bin" / "ciel-server" / "ciel-server", app_root, user_data, session)
    output_dir.mkdir(parents=True, exist_ok=False)
    final_dir = output_dir / package.parent.name
    shutil.copytree(package.parent, final_dir, symlinks=True)
    verification_path = session / "release-verification.json"
    verify_script = TOOLS / "verify_ciel_release.py"
    verify_env = {**env, "CIEL_FORBIDDEN_PERSONAL_ROOT": str(Path.home())}
    run([str(python), str(verify_script), "release", str(final_dir / "CIEL Canvas"), "--json-output", str(verification_path)], env=verify_env)
    zip_path = output_dir / f"{final_dir.name}.zip"
    run(["/usr/bin/ditto", "--norsrc", "--noextattr", "-c", "-k", "--keepParent", str(final_dir), str(zip_path)], env={**os.environ, "COPYFILE_DISABLE": "1"})
    result = {"release_directory": str(final_dir), "release_zip": str(zip_path), "release_zip_sha256": sha256(zip_path), "architecture": "arm64", "supported_apple_silicon": ["M1", "M2", "M3", "M4", "M5"], "runtime_smoke": smoke, "verification": json.loads(verification_path.read_text(encoding="utf-8")), "dependency_lock": str(REQUIREMENTS), "pydantic_core": "2.46.4"}
    (output_dir / "macos-arm64-build-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true", help="run portable checks without building")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    report = static_self_check()
    if args.self_check:
        report["host"] = {"system": platform.system(), "machine": platform.machine()}
        report["build"] = "BLOCKED_UNTIL_REAL_MACOS_ARM64"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    result = build_release(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildFailure as exc:
        print(f"BUILD_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(2)
