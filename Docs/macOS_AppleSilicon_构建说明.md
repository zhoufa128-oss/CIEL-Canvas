# CIEL Canvas macOS Apple Silicon 构建说明

本 BuildKit 为 CIEL Canvas 1.0.0 的 macOS arm64 发行构建入口，覆盖 Apple Silicon M1、M2、M3、M4、M5。业务源码、画布 schema、Provider 和共享 Web UI 与 Windows 版本共用；macOS 差异只存在于 PyInstaller 目标架构、`.app` 启动器和 `UserData` 运行时目录。

## 真实构建条件

- 必须在真实 macOS arm64（Apple Silicon）电脑执行；当前 Windows 电脑只能完成静态自检，不能生成可运行 Mach-O。
- macOS 11.0 或更高版本。
- Python 3.11–3.14（建议使用系统外的 python.org/Homebrew arm64 Python）。
- Xcode Command Line Tools（提供 `sips`、`iconutil`、`osacompile`、`codesign`、`ditto`）。

## 构建命令

```zsh
cd CIEL_Canvas_1.0.0_macOS_arm64_BuildKit
python3 Build/build_macos_arm64_release.py --self-check
python3 Build/build_macos_arm64_release.py
```

依赖锁定在 `Build/requirements-build-macos-arm64.txt`，其中 `pydantic-core==2.46.4` 不得变更。构建器会创建隔离虚拟环境、生成 arm64 PyInstaller 服务、生成签名（ad-hoc）`.app`、执行运行时健康检查、扫描敏感路径并输出 ZIP SHA-256。

## 迁移和首次启动

解压 `BuildOutput/macOS_arm64/CIEL_Canvas_1.0.0_macOS_arm64.zip` 后，将整个 `CIEL Canvas` 文件夹放在可写位置，右键 `CIEL Canvas.app` 选择“打开”。首次启动会在同级创建 `UserData/`，端口为 `3015`，浏览器打开 `http://127.0.0.1:3015/`。

该包是 arm64、未经过 Apple Developer ID 签名和公证；SmartScreen/ Gatekeeper 的人工确认属于外部步骤。Intel Mac 不在支持范围内。
