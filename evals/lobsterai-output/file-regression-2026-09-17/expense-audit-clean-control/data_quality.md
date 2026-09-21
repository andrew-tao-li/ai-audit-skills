# 数据质量报告

- 源文件：`expenses.csv`
- 工作表：`CSV`
- 源数据行数：6
- 有效行数：6
- Bad rows：0
- 字段映射：`{"expense_id": "费用编号", "employee_id": "工号", "department": "部门", "expense_type": "费用类别", "expense_date": "费用日期", "submit_date": "提交日期", "amount": "报销金额", "currency": "币种", "vendor_name": "商户", "invoice_number": "发票号码", "project_code": "项目代码", "approver": "审批人", "business_purpose": "业务目的"}`
- 标准化计数：`{"trimmed_or_normalized_text_values": 0, "parsed_amount_values": 6, "parsed_date_values": 6}`

## 源字段空值率

- `费用编号`: 0.00%
- `工号`: 0.00%
- `部门`: 0.00%
- `费用类别`: 0.00%
- `费用日期`: 0.00%
- `提交日期`: 0.00%
- `报销金额`: 0.00%
- `币种`: 0.00%
- `商户`: 0.00%
- `发票号码`: 0.00%
- `项目代码`: 0.00%
- `审批人`: 0.00%
- `业务目的`: 0.00%

## 警告与跳过规则

- robust-outlier：没有达到最小样本且 MAD 非零的 peer group
