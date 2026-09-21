# 公共数据协议 v0.1.0

## Finding

必填字段：

```json
{
  "finding_id": "EXP-000001",
  "skill": "expense-audit",
  "finding_type": "exact-duplicate",
  "title": "可能的重复报销",
  "risk_priority": "high",
  "evidence_strength": "strong",
  "risk_score": 4,
  "risk_factors": [{"factor": "same_invoice_and_amount", "points": 4}],
  "entities": [{"type": "employee", "id": "E001"}],
  "facts": ["两条记录的发票号和金额相同"],
  "inferences": ["可能存在重复报销"],
  "hypotheses": [],
  "open_questions": ["是否为冲销或重新提交？"],
  "evidence_refs": ["EV-000001", "EV-000002"],
  "recommended_next_steps": ["核对发票影像和付款流水"],
  "human_review_required": true
}
```

`risk_priority` 只能是 `low|medium|high|critical`；`evidence_strength` 只能是 `weak|moderate|strong`。`facts` 只写源数据直接支持的内容；`inferences` 写基于规则的解释；`hypotheses` 必须可被后续证据证伪。v0.1.0 不输出最终 judgment。

## Evidence

```json
{
  "evidence_id": "EV-000001",
  "source_file": "expenses.csv",
  "source_hash": "sha256:...",
  "sheet": null,
  "row": 3,
  "field": "invoice_number",
  "value": "INV-1001",
  "extraction_method": "direct",
  "confidence": 1.0
}
```

CSV/XLSX 的 `row` 使用人可见的一基行号（表头为第 1 行）；纯文本可使用 `line`；文档可增加 `page`、`paragraph`、`bounding_box`。输出中可保留完整值，但对外分享前需要脱敏。

## Run Manifest

必须记录：`run_id`、skill 名称和版本、UTC 开始/结束时间、输入文件相对路径及 SHA-256、参数、脚本文件及 SHA-256、警告、输出文件、`network_access:false`。

## Handoff

```json
{
  "schema_version": "0.1.0",
  "source_skill": "procurement-fraud",
  "finding_ids": ["PROC-000001"],
  "entities": [],
  "reason_for_handoff": "多类独立红旗指向同一供应商",
  "known_facts": [],
  "hypotheses": [],
  "recommended_scope": [],
  "human_approval_required": true
}
```

生成 handoff 只表示建议复核；不得自动扩大调查或调用调查 skill。
