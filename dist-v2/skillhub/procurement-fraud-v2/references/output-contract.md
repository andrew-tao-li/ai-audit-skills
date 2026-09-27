# Procurement output contract

`findings.jsonl` 与 `evidence.jsonl` 遵循公共 Schema。`relationship_graph.json` 使用：

```json
{"nodes": [{"id": "vendor:V001", "type": "vendor", "label": "V001"}], "edges": [{"source": "employee:E001", "target": "vendor:V001", "type": "shares_phone", "evidence_refs": ["EV-..."]}]}
```

`investigation_handoff.json` 即使没有建议移交也会生成，使用 `status: "not_recommended"`；有建议时包含 source finding IDs、已知事实、假设、推荐范围和 `human_approval_required:true`。它不是调查授权。

宿主 Agent 的解读顺序：先数据质量和跨表覆盖率，再 strong evidence，再看多模块是否指向同一主体，随后主动寻找白名单、业务例外、数据错误和反证，最后才形成补证计划。
