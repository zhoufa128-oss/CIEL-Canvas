# Windows 启动器设计

`windows_launcher.py` 只负责发行根定位、环境变量、3015/进程归属、PID/日志、启动自带 server、健康检查、默认浏览器与错误消息框，不实现任何画布业务。

归属链为 `current.pid`、进程存活、3015 listener PID、可执行路径属于 `Application/current`、`/api/app-info` 的 product/release/internal build/platform/architecture/portable 全匹配。任何一项不明确都不终止进程。server 使用 `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`、隐藏窗口、stdin DEVNULL、stdout/stderr 日志，启动器退出后继续运行。
