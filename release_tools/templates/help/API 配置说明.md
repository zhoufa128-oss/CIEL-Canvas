# API 配置说明

- 发行包不包含开发者的 API Key。
- 请在页面的 API 设置中填写自己的 Key。
- Key 只写入 `UserData/config/.env`，权限在 macOS 上设置为 600。
- 没有 Key 时可以正常创建、编辑和保存画布；调用生成时会提示尚未配置 API。
- 不要把 `UserData/config/` 发送给其他人。
