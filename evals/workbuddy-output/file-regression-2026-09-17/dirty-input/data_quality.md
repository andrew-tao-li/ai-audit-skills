# 数据质量报告

- 源文件：`expenses.csv`
- 工作表：`CSV`
- 源数据行数：5
- 有效行数：2
- Bad rows：3
- 字段映射：`{"expense_id": "expense_id", "employee_id": "employee_id", "department": "department", "expense_type": "expense_type", "expense_date": "expense_date", "submit_date": "submit_date", "amount": "amount", "currency": "currency", "vendor_name": "vendor_name", "invoice_number": "invoice_number", "project_code": "project_code", "approver": "approver", "business_purpose": "business_purpose"}`
- 标准化计数：`{"trimmed_or_normalized_text_values": 0, "parsed_amount_values": 2, "parsed_date_values": 2}`

## 源字段空值率

- `expense_id`: 0.00%
- `employee_id`: 20.00%
- `department`: 0.00%
- `expense_type`: 0.00%
- `expense_date`: 0.00%
- `submit_date`: 0.00%
- `amount`: 0.00%
- `currency`: 20.00%
- `vendor_name`: 0.00%
- `invoice_number`: 0.00%
- `project_code`: 0.00%
- `approver`: 0.00%
- `business_purpose`: 0.00%

## 警告与跳过规则

- policy-threshold：未提供 limits
- split-expense：未提供 approval_thresholds
- weekend-signal：weekend_check 未启用
- robust-outlier：没有达到最小样本且 MAD 非零的 peer group
