# Investigation normalization

## Messages

Canonical fields：`message_id`、`timestamp`、`sender`、`recipient`、`channel`、`content`。常见别名包括 `from/to`、`发件人/收件人`、`发送时间`、`聊天内容`。

## Logs

Canonical fields：`event_id`、`timestamp`、`actor`、`event_type`、`object`、`device`、`ip`、`result`。常见别名包括 `user/action/resource`、`用户/操作/对象/设备/IP/结果`。

## Rules

- 标识符始终按字符串；文本做 NFKC 和空白压缩，但 raw 不改。
- 时间戳必须包含时区；没有时区时使用 scope 的 `assumed_timezone`，并写入 manifest。
- 只把人员范围内、时间范围内的结构化行放入 derived 和 timeline；其他行进入 out-of-scope 清单。
- 文本文件按非空行登记行级 evidence；关键词匹配不改变原文。
- 不从自由文本自动推断亲属、主观动机或责任。
