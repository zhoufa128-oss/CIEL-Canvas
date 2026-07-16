# Windows 离线更新说明

更新包只替换 `Application/current`，绝不覆盖 `UserData`。构建者使用 `build_windows_update.ps1` 生成包；包内 `update.json` 校验 product、Windows x64、来源版本范围与目标版本。

用户完整解压更新 ZIP，运行 `CIEL Canvas Update.exe`，选择现有 `CIEL Canvas` 根目录。更新器先校验全部哈希，只终止 PID、端口、产品与可执行路径都确认归属当前 Application 的服务；随后 staging、保存 previous、替换 current、在 3016 健康检查，失败自动回滚。不要在 ZIP 内运行更新器。

更新 EXE 同样未签名，必须先核对 SHA-256。
