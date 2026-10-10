# audit-sql-builder（审计取数 SQL 生成器）

**定位：审计的第 0 步——取数。** 它把「审计需求」翻译成可在业务系统上执行的 **SQL 文本**；
不分析数据、不下审计结论。跑完导出的 CSV，交给 `expense-audit-v2` 等审计技能。

## 进 → 中间 → 出

```
进：数据字典（CSV/XLSX，IT 真能导出：表名/字段名/中文名）
 ↓
中间：生成的 .sql 文件（贴给 DBA 跑）
 ↓
出：查询结果 CSV（喂给 expense-audit-v2）
```

## 用法

```bash
python3 scripts/run_sql_builder.py --schema 数据字典.csv --dialect sqlite --output out/
# 与 IT 确认 mapping.suggested.json 后，用 --map 回填再生成：
python3 scripts/run_sql_builder.py --schema 数据字典.csv --map 确认后的映射.json --dialect oracle --output out2/
```

- `--dialect`：`sqlite`（默认，便于本地验证）/ `mysql` / `postgres` / `sqlserver` / `oracle`。
- **离线、确定性**：不调模型、不连数据库；同一输入结果可复现。
- **缺字段不硬凑**：会明确告诉你"这个需求需要『发票号』，你的字典里没有"。

## 边界

- 它只生成**取数 SQL**，**不是审计结论**；SQL 的字段语义要**和 IT 确认**（技能只给候选 + 置信度）。
- 不连接任何数据库、不上传任何数据。
