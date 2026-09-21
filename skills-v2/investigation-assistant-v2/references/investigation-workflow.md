# Investigation workspace contract

## Timeline

字段：`timestamp`、`actor`、`event_type`、`object`、`source_file`、`source_row`、`evidence_id`、`confidence`。排序只使用成功解析的时间戳；每行必须能回到 evidence。

## Entity and relationship

实体只来自结构化字段或明确格式（员工编号、邮件地址、设备、文档），不猜同名关系。关系边至少包含 `source`、`target`、`type`、`evidence_refs`。

## Evidence matrix

每个 scope issue 一行：`issue_id`、`allegation_or_issue`、`supporting_evidence_refs`、`contradictory_evidence_refs`、`missing_evidence`、`alternative_explanations`、`status`。关键词命中只是候选证据，必须回到上下文确认。

## Hypothesis register

包含 hypothesis、支持证据、反证、缺失证据、可替代解释、下一步验证和状态。初始状态保持 `open`。不要把举报表述复制到 facts。

## Interview plan

按 scope 中 interviewees 生成：访谈对象、目标、已知事实、未知事实、问题、拟出示材料、触发追问条件。访谈前由有权人员确认次序、保密和劳动法/隐私要求。

## Findings

每个 issue 可形成一条 `investigation-lead`：facts 仅来自候选记录，inferences 只说明关键词检索连接，hypotheses 放待验证指控；没有最终 judgment。风险优先级沿用 scope 的人工设定或默认 medium，不由关键词数量自动升级。
