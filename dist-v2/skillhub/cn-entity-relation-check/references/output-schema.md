# 机器输出 Schema（output-schema）

## 最小字段

`status`、`display_status`、`entity_a`、`entity_b`、`relationship_temporality`、`paths`、`scope`、`sources`、`warnings`、`queried_at`。

## status 取值

只允许 `RELATED` / `NOT_RELATED_IN_SCOPE` / `NEEDS_VERIFICATION`。

**不要**增加 `LIKELY_RELATED`、`MAYBE_NOT_RELATED`、`80% RELATED` 之类的模糊状态。

## 示例

```json
{
  "status": "RELATED",
  "display_status": "关联",
  "relationship_temporality": "current",
  "entity_a": {"type": "company", "name": "上海甲科技有限公司", "canonical_id": "9131..."},
  "entity_b": {"type": "company", "name": "上海乙科技有限公司", "canonical_id": "9131..."},
  "paths": [
    {"length": 2, "nodes": ["上海甲科技有限公司", "张三", "上海乙科技有限公司"], "edges": ["董事", "股东35%"]}
  ],
  "scope": {"relation_types": ["股权", "法人", "董监高", "投资", "控制"], "max_depth": 3},
  "sources": [{"provider": "qcc", "retrieved_at": "..."}],
  "warnings": [],
  "queried_at": "..."
}
```

完整 JSON Schema 见 `assets/relation-result.schema.json`。
