"""CIEL Canvas development and portable-release path policy.

Development mode is the default and preserves the historical project-relative
paths. Portable mode is opt-in and requires the exact Application/UserData
layout supplied by the release launcher.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


PRODUCT_ID = "local.ciel.canvas"
PRODUCT_NAME = "CIEL Canvas"
RELEASE_VERSION = "1.0.0"
DATA_SCHEMA_VERSION = 1


def _portable_enabled() -> bool:
    return os.environ.get("CIEL_PORTABLE", "").strip().lower() in {"1", "true", "yes", "on"}


def _absolute_env(name: str) -> Path:
    raw = os.environ.get(name, "").strip()
    if not raw:
        raise RuntimeError(f"Portable 模式缺少环境变量：{name}")
    path = Path(raw)
    if not path.is_absolute():
        raise RuntimeError(f"Portable 路径必须为绝对路径：{name}")
    return path.resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _ensure_private_directory(path: Path, data_root: Path) -> None:
    if path.exists() and path.is_symlink():
        raise RuntimeError(f"Portable 数据目录不能是软链接：{path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    resolved = path.resolve()
    if resolved != data_root and not _is_relative_to(resolved, data_root):
        raise RuntimeError(f"Portable 数据目录越界：{path}")
    if os.name == "posix":
        os.chmod(path, 0o700)


def _atomic_json(path: Path, payload: Dict) -> None:
    temp = path.with_name(f".{path.name}.new-{os.getpid()}")
    if temp.exists():
        raise RuntimeError(f"初始化暂存文件已存在：{temp}")
    with temp.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if os.name == "posix":
        os.chmod(temp, 0o600)
    os.replace(temp, path)


@dataclass(frozen=True)
class CielPaths:
    portable: bool
    install_root: Path
    app_root: Path
    user_data_root: Path
    static_dir: Path
    workflows_dir: Path
    user_workflow_root: Path
    output_dir: Path
    assets_dir: Path
    input_dir: Path
    generated_output_dir: Path
    asset_library_dir: Path
    data_dir: Path
    thumbnails_dir: Path
    conversations_dir: Path
    canvases_dir: Path
    config_dir: Path
    logs_dir: Path
    runtime_dir: Path
    backups_dir: Path
    diagnostics_dir: Path
    temp_dir: Path
    history_file: Path
    api_env_file: Path
    asset_library_file: Path
    prompt_library_file: Path
    api_providers_file: Path
    runninghub_workflows_file: Path
    global_config_file: Path
    install_file: Path

    @classmethod
    def from_environment(cls, development_root: Path) -> "CielPaths":
        development_root = development_root.resolve()
        if not _portable_enabled():
            data_dir = development_root / "data"
            assets_dir = development_root / "assets"
            return cls(
                portable=False,
                install_root=development_root,
                app_root=development_root,
                user_data_root=development_root,
                static_dir=development_root / "static",
                workflows_dir=development_root / "workflows",
                user_workflow_root=development_root / "workflows",
                output_dir=development_root / "output",
                assets_dir=assets_dir,
                input_dir=assets_dir / "input",
                generated_output_dir=assets_dir / "output",
                asset_library_dir=assets_dir / "library",
                data_dir=data_dir,
                thumbnails_dir=data_dir / "thumbs",
                conversations_dir=data_dir / "conversations",
                canvases_dir=data_dir / "canvases",
                config_dir=development_root / "API",
                logs_dir=development_root / ".run",
                runtime_dir=development_root / ".run",
                backups_dir=data_dir / "update_backups",
                diagnostics_dir=development_root / "diagnostics",
                temp_dir=Path(),
                history_file=development_root / "history.json",
                api_env_file=development_root / "API" / ".env",
                asset_library_file=data_dir / "asset_library.json",
                prompt_library_file=data_dir / "prompt_libraries.json",
                api_providers_file=data_dir / "api_providers.json",
                runninghub_workflows_file=data_dir / "runninghub_workflows.json",
                global_config_file=development_root / "global_config.json",
                install_file=development_root / "install.json",
            )

        install_root = _absolute_env("CIEL_INSTALL_ROOT")
        app_root = _absolute_env("CIEL_APP_ROOT")
        data_root = _absolute_env("CIEL_DATA_ROOT")
        expected_app = (install_root / "Application" / "current").resolve()
        expected_data = (install_root / "UserData").resolve()
        if app_root != expected_app:
            raise RuntimeError("CIEL_APP_ROOT 必须指向 <发行根>/Application/current")
        if data_root != expected_data:
            raise RuntimeError("CIEL_DATA_ROOT 必须指向 <发行根>/UserData")
        if not app_root.is_dir():
            raise RuntimeError(f"Portable Application 不存在：{app_root}")
        if app_root.is_symlink() or install_root.is_symlink():
            raise RuntimeError("Portable Application 与安装根不能是软链接")

        config_dir = data_root / "config"
        assets_dir = data_root / "assets"
        outputs_dir = data_root / "outputs"
        runtime_dir = data_root / "runtime"
        paths = cls(
            portable=True,
            install_root=install_root,
            app_root=app_root,
            user_data_root=data_root,
            static_dir=app_root / "static",
            workflows_dir=app_root / "workflows",
            user_workflow_root=config_dir / "workflows",
            output_dir=outputs_dir / "legacy",
            assets_dir=assets_dir,
            input_dir=assets_dir / "input",
            generated_output_dir=outputs_dir,
            asset_library_dir=assets_dir / "library",
            data_dir=config_dir,
            thumbnails_dir=data_root / "thumbnails",
            conversations_dir=config_dir / "conversations",
            canvases_dir=data_root / "canvases",
            config_dir=config_dir,
            logs_dir=data_root / "logs",
            runtime_dir=runtime_dir,
            backups_dir=data_root / "backups",
            diagnostics_dir=data_root / "diagnostics",
            temp_dir=runtime_dir / "temp",
            history_file=config_dir / "history.json",
            api_env_file=config_dir / ".env",
            asset_library_file=config_dir / "asset_library.json",
            prompt_library_file=config_dir / "prompt_libraries.json",
            api_providers_file=config_dir / "api_providers.json",
            runninghub_workflows_file=config_dir / "runninghub_workflows.json",
            global_config_file=config_dir / "global_config.json",
            install_file=data_root / "install.json",
        )
        paths.initialize_portable_user_data()
        return paths

    def managed_directories(self) -> Iterable[Path]:
        return (
            self.user_data_root,
            self.canvases_dir,
            self.assets_dir,
            self.input_dir,
            self.asset_library_dir,
            self.thumbnails_dir,
            self.generated_output_dir,
            self.output_dir,
            self.config_dir,
            self.conversations_dir,
            self.user_workflow_root,
            self.user_workflow_root / "custom",
            self.logs_dir,
            self.runtime_dir,
            self.temp_dir,
            self.backups_dir,
            self.diagnostics_dir,
        )

    def initialize_portable_user_data(self) -> None:
        if not self.portable:
            return
        for directory in self.managed_directories():
            _ensure_private_directory(directory, self.user_data_root)

        if self.api_env_file.exists() and self.api_env_file.is_symlink():
            raise RuntimeError("Portable API 配置不能是软链接")
        self.api_env_file.touch(mode=0o600, exist_ok=True)
        if os.name == "posix":
            os.chmod(self.api_env_file, 0o600)

        if self.install_file.exists():
            with self.install_file.open("r", encoding="utf-8") as handle:
                current = json.load(handle)
            if current.get("product_id") != PRODUCT_ID:
                raise RuntimeError("UserData/install.json product_id 不匹配")
            if int(current.get("data_schema_version") or 0) != DATA_SCHEMA_VERSION:
                raise RuntimeError("UserData 数据结构版本不兼容")
            return

        if not any(self.canvases_dir.glob("*.json")):
            template_path = self.app_root / "defaults" / "user-data" / "welcome-canvas.json"
            if not template_path.is_file() or not _is_relative_to(template_path.resolve(), self.app_root):
                raise RuntimeError("Portable 欢迎画布模板缺失或路径不安全")
            with template_path.open("r", encoding="utf-8") as handle:
                welcome = json.load(handle)
            timestamp = int(time.time() * 1000)
            welcome["id"] = "welcome-ciel-canvas"
            welcome["title"] = "欢迎使用 CIEL Canvas"
            welcome["kind"] = "smart"
            welcome["created_at"] = timestamp
            welcome["updated_at"] = timestamp
            welcome["nodes"] = list(welcome.get("nodes") or [])
            welcome["connections"] = list(welcome.get("connections") or [])
            welcome["viewport"] = dict(welcome.get("viewport") or {"x": 0, "y": 0, "scale": 1})
            _atomic_json(self.canvases_dir / "welcome-ciel-canvas.json", welcome)

        payload = {
            "product_id": PRODUCT_ID,
            "product_name": PRODUCT_NAME,
            "installed_release": RELEASE_VERSION,
            "data_schema_version": DATA_SCHEMA_VERSION,
            "platform": "macos" if sys.platform == "darwin" else sys.platform,
            "architecture": platform.machine(),
            "initialized": True,
        }
        _atomic_json(self.install_file, payload)

    def secure_data_child(self, root: Path, *parts: str) -> Path:
        if not self.portable:
            return root.joinpath(*parts)
        if root.is_symlink() or not _is_relative_to(root.resolve(), self.user_data_root):
            raise RuntimeError("Portable 写入根目录不安全")
        candidate = root.joinpath(*parts)
        if candidate.is_absolute() and not _is_relative_to(candidate.resolve(strict=False), root.resolve()):
            raise RuntimeError("Portable 数据路径越界")
        if any(part in {"", ".", ".."} for part in parts):
            raise RuntimeError("Portable 数据路径包含非法片段")
        parent = candidate.parent.resolve(strict=False)
        if not _is_relative_to(parent, root.resolve()):
            raise RuntimeError("Portable 数据路径或软链接越界")
        return candidate


PATHS = CielPaths.from_environment(Path(__file__).resolve().parent)
