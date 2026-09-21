# 采购员与供应商串通重复报销同一笔办公用品发票

**难度**: 简单

**场景描述**: 华东区某民营家具制造企业（员工约320人），2024年5月内审中发现采购专员张某在5月8日、5月19日、6月2日三次提交了抬头为本公司、税号一致、金额均为8,650.00元、发票号码完全相同的'办公耗材及打印纸'增值税普通发票，供应商为本地长期合作的小型办公用品店。初步核查发现该门店并不具备大批量耗材库存能力，且发票备注栏'品名规格'字段与历史采购目录不匹配。张某负责办公用品采购，月度报销额度未触发财务总监审批阈值（5万元），三笔均由其直接主管——采购主管李某在系统中一键审批通过。动机层面，张某与该门店老板存在亲属关系，疑似通过虚开发票套取现金后再与供应商分赃，属于典型的'一张发票重复贴现'舞弊手法。

**预期 finding**: exact-duplicate-invoice, self-approval

**不应触发**: near-duplicate, split-expense, weekend-signal, robust-outlier

**数据预览**:
```json
{
  "expense_id": "EX-20240508-0371",
  "employee_id": "EMP-ZHANG-0823",
  "employee_name": "张某",
  "department": "采购部",
  "submit_date": "2024-05-08",
  "expense_date": "2024-05-06",
  "amount_cny": 8650.0,
  "invoice_number": "04425820",
  "vendor_name": "鑫达办公用品经营部",
  "expense_type": "办公用品",
  "approver_id": "EMP-LI-0315",
  "approver_name": "李某",
  "approval_level": "主管",
  "approval_threshold_cny": 50000
}
```
