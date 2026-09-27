# Chain of custody

## Minimum sequence

1. 校验授权与范围，不读取未获准文件内容。
2. 对 allowed source 记录相对路径、文件大小、修改时间、SHA-256 和 Evidence ID。
3. 复制到新工作空间 `evidence/raw/<relative-path>`，保留时间戳。
4. 重新计算副本 SHA-256；不一致立即停止；验证后移除 raw 副本的写权限。
5. 所有解析结果写入 `derived/`，不修改 raw。
6. 在 `chain_of_custody.jsonl` 记录 `registered`、`copied_and_verified`、`derived`，包含 UTC 时间、操作者标识、源/目标和 hash。

文件系统“只读”只是防误改措施，不等于不可篡改存储或司法封存。该日志说明本工具做过什么，不替代法域或机构正式取证制度。若案件需要司法鉴定、电子数据封存、签名时间戳或专用镜像，必须按组织制度交给具备权限和资质的人员。
