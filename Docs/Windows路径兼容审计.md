# Windows 路径兼容审计

## 结论

源码可以进入 Windows x64 真机构建阶段；本轮没有在 macOS 生成 EXE。仅对 BuildKit Source 的 `/api/app-info` 增加启动归属字段，没有改画布 schema、UI、Logo、Provider 或业务函数。

## 审计结果

- 运行时根由 `ciel_paths.py` 的 `pathlib.Path` 与 `CIEL_INSTALL_ROOT/CIEL_APP_ROOT/CIEL_DATA_ROOT` 决定，没有 `/Users/` 或开发者绝对路径。
- `chmod 700/600` 仅在 `os.name == "posix"` 执行；Windows 不走该分支。
- macOS 的 `osascript/open/Finder/iconutil/codesign/xattr` 只存在于 `Source/release_tools` 的 macOS 构建/更新源码；Windows 白名单不把这些文件装入 `Application/current`。
- `main.py` 的开发在线更新在 portable 模式被 `require_development_update_mode()` 拒绝；其中 macOS shell 分支不会进入 Windows 正式运行路径。
- Windows 启动器与更新器使用 `Path`、参数数组和 Python API，不拼接 CMD/PowerShell 命令；中文与空格路径没有 shell 引号依赖。
- 本地图片导入先复制到受控 `UserData` 资产目录，画布保存受控 URL；不把导入源的开发者绝对路径写入画布 JSON。
- `UserData` schema 与 macOS portable schema 相同，`data_schema_version` 为 1；画布 JSON 不作平台变更。
- 盘符与本地 NTFS 路径由 `Path.resolve()` 处理。建议在短路径（如 `C:\CIELBuild`）构建，降低 PyInstaller/传统 MAX_PATH 风险。
- UNC 路径未做真机认证；首版构建与使用应放在本地磁盘。不要宣称 UNC 已通过。

## 仍需 Windows 真机覆盖

中文/空格目录、长路径、重复双击、3015 三种占用场景、休眠恢复、默认浏览器、SmartScreen、更新成功与自动回滚都必须在 Windows 10/11 x64 上实测。
