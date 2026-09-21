# 区域销售经理通过拆单、跨员工复用发票规避差旅费审批上限

**难度**: 困难

**场景描述**: 华东区销售经理张某在2024年Q2频繁出差，利用其下属3名销售代表的身份证和发票信息，多次将单次差旅产生的酒店住宿发票拆分至不同员工名下提交报销，并将一张金额为6800元的酒店发票通过PS修改为6500元和300元两张提交以规避5000元单笔审批上限。同时，他利用周末出差的合理性，对一段实际发生于周五晚至周日的行程，故意将酒店入住日期标注为下周一至周三，配合一套连号餐饮发票（票号连号5张，单张金额均在4800元以下）一并提交，全部由其本人作为部门负责人审批通过。审计师在抽查中发现金额微调痕迹、跨员工发票抬头重复、连号发票及自审自批的多重异常信号。

**预期 finding**: split-expense, cross-employee-invoice, near-duplicate, sequential-invoice, self-approval, policy-threshold, weekend-signal

**不应触发**: exact-duplicate-invoice, future-date, missing-expense-type, submit-before-expense, large-amount-low-level-approval

**数据预览**:
```json
{
  "employee_id": "EMP-2018",
  "employee_name": "张某",
  "department": "华东大区销售部",
  "role": "区域销售经理",
  "expense_period": "2024-Q2",
  "total_claimed_amount": 47800,
  "number_of_invoices": 23,
  "number_of_employees_involved_as_submitters": 4,
  "approval_level": "部门负责人自批",
  "weekend_expense_ratio": "62%",
  "consecutive_invoice_numbers_detected": "INV-20240518-0321 至 0325"
}
```
