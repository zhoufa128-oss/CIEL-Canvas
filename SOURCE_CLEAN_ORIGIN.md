# Source Clean 来源与 V16 小补丁

- 来源 ZIP：`CIEL_Canvas_1.0.0_Source_Clean.zip`
- 来源 SHA-256：`2abe4bfeb62070873c62532b3cfa5c36845cc4bf16c073ed3c35776a7401a568`
- 来源内部清单：109/109 文件匹配；9 个非 ASCII 路径为 UTF-8。
- `SHA256SUMS_SOURCE_CLEAN_ORIGINAL.txt` 是来源 ZIP 内原始清单。
- V16 唯一源码兼容补丁：`main.py` 的 `/api/app-info` 增加 `product_id`、发行版本、内部构建号、schema、平台、架构和 portable 状态，供 Windows 启动器做进程/版本归属核验。

没有修改画布 schema、UI、Logo、Provider 或画布业务。`SHA256SUMS.txt` 是上述小补丁后的 BuildKit Source 清单。
