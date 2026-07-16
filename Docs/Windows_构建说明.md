# Windows x64 构建说明

## 环境

使用 Windows 10/11 x64、本地 NTFS 短路径、64 位 Python。无需管理员权限，不修改全局 Python；脚本在时间戳工作目录内创建独立 `build-env`。

## 构建

在普通 PowerShell 中进入 BuildKit：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Build\build_windows_release.ps1 -Python python
```

脚本固定依赖版本，分别构建 onedir server 与 windowed launcher，按白名单组装 `CIEL Canvas`，创建空 UserData，写 `release.json`/双层 SHA256SUMS，标记 Application 文件只读，执行路径、敏感信息、二进制字符串和结构校验，最后才把 `.partial.zip` 提升为正式 ZIP。

任何失败都不会生成或覆盖正式 ZIP。不要复制 `build-env`、PyInstaller work/dist、Source、测试缓存或 macOS 文件到正式包。

## 必须人工确认

检查 `CIEL_Canvas_1.0.0_Windows_x64_SHA256.txt`，再按 Tests 清单在 Windows 10 与 11 x64 真机执行。EXE 未签名，不得标记 ARM64 支持。
