# Windows 首次启动说明

完整解压后双击 `CIEL Canvas.exe`。启动器从自身位置定位 `Application/current` 和 `UserData`，检查 3015，启动自带服务并打开默认浏览器。首次启动不写注册表、Program Files 或 AppData。

若 3015 已是同一版本，启动器只打开浏览器；若是旧 CIEL 版本或无关程序，会明确提示且不会终止对方。若启动失败，按提示打开 `UserData/logs`。
