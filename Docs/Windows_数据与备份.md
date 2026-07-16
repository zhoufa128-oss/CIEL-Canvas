# Windows 数据与备份

数据只保存在 `UserData`：画布、资产、缩略图、输出、配置、日志、运行状态、备份和诊断分别位于同名子目录。备份时先关闭已确认属于当前版本的服务，再完整复制 `UserData`。

恢复时使用相同 `data_schema_version` 的版本，把备份恢复到完整解压的发行根。不要把 `UserData` 放入 `Application/current`，不要把 API 配置发送给他人。
