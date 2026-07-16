# Windows 构建交接说明

本 BuildKit 已完成 macOS 上的源码语法、结构、来源、路径和敏感信息静态检查；没有执行 Windows PyInstaller，也没有 Windows EXE 或双击结果。

交接顺序：核对 BuildKit SHA-256 → 在 Windows 10/11 x64 短路径解压 → 普通权限运行完整构建脚本 → 核对正式 ZIP SHA-256 → 运行 Tests 真机清单 → 保存构建日志与验证输出 → 仅在全部通过后提供给一位朋友试用。

Windows ARM64、代码签名、SmartScreen 无提示、所有 Windows 电脑兼容均不在本交接结论内。
