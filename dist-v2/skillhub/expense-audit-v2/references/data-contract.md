# Expense data contract

## Canonical fields

核心字段：`expense_id`、`employee_id`、`amount`、`expense_date`。缺任一核心字段时不得形成正式全量结论。

推荐字段：`department`、`expense_type`、`currency`、`vendor_name`、`invoice_number`、`invoice_date`、`submit_date`、`project_code`、`approver`、`payment_date`、`business_purpose`。

自动识别常见别名，例如 `id/单据号/报销单号`、`emp_id/员工编号`、`date/发生日期`、`金额`、`商户/供应商`、`发票号`。自动映射只在一个源字段唯一对应一个 canonical field 时生效；用 `--field-map` 明确覆盖歧义：

```json
{"expense_id": "报销单号", "employee_id": "工号", "amount": "报销金额", "expense_date": "发生日期"}
```

## Normalization

- 标识符按字符串读取，保留前导零。
- 金额去除币种符号和千位分隔符后转为十进制；负数保留，不擅自解释为退款。
- 日期统一为 `YYYY-MM-DD`；无法解析的核心日期进入 bad rows。
- 文本执行 Unicode NFKC、去首尾空格、压缩连续空白；匹配键另做大小写和标点归一化。
- 默认币种为配置的 `default_currency`；未配置时为 `CNY` 并写入警告。

## Quality output

记录源行数、有效行数、bad row 数、各列空值率、字段映射、未识别字段、重复业务主键和所有跳过规则。不要用填充后的值掩盖原始缺失。
