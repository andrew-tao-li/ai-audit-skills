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

## v0.2.7 新增（可选）：`observed_at` — 记录时间

输入的消息表 / 日志表若含**记录时间**列，会被识别为 `observed_at`
（别名：`recorded_at`、`observed_at`、`record_time`、`记录时间`、`登记时间`、`录入时间`）。

- **`timestamp` = 事实发生时间**（这件事什么时候发生）
- **`observed_at` = 记录/登记时间**（我们什么时候知道这件事）

**只有输入里真的提供了该列时**，`timeline.csv` 才会多出 `observed_at` 一列（紧跟 `timestamp`）；
**没有该列 → 产出与旧版逐字节一致**。

> 为什么要分开：补录、事后导出的台账里，两者可能差很久。
> 把"发生时间"和"我们得知的时间"混成一个字段，会让时间线出现无法解释的顺序问题。
