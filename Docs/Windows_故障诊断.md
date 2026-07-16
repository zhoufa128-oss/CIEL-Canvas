# Windows 故障诊断

- 启动无响应：确认已完整解压，查看 `UserData/logs`。
- 3015 被占用：关闭明确占用该端口的应用；CIEL 不会终止无关程序。
- 浏览器未打开：手动访问 `http://127.0.0.1:3015`。
- API 不可用：在应用设置中填写自己的配置，不要共享 `.env` 或密钥。
- 更新失败：保留 `Updates`、`UserData/logs/windows-update-health.log` 和 `Application/previous`，不要手工删除。
- 需要求助：提供诊断包、Windows 版本、发行 ZIP SHA-256 和复现步骤，不要发送 API 密钥或整个 UserData。
