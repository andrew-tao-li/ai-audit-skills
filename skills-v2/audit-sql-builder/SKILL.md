---
name: audit-sql-builder
description: "把审计需求翻译成可在业务系统上执行的 SQL：读数据字典（表名/字段名/中文名），建议字段映射（带候选与置信度，不硬猜），按需渲染多方言 SQL，缺字段时明确报出。Use when the user knows only the business system name and needs to pull data out — asks for 取数/写 SQL/查询语句/数据字典/从 XX 系统导数据, or wants to turn audit needs into SELECT statements before running an audit skill. Do not use for analyzing data, writing findings, or connecting to a database — this skill only produces SQL text."
version: 0.1.0
metadata:
  author: "andrew-tao-li"
  aiaudit_compatibility: "Agent Skills hosts; offline; Python 3.10+; openpyxl optional for XLSX schema"
  changelog: "v0.1.0: 首个版本——数据字典 → 字段映射建议 → 按需求渲染多方言 SQL（sqlite/mysql/postgres/sqlserver/oracle）；缺字段不硬凑；完全离线。"
---

# Audit SQL Builder（审计取数）

## 联网与风险（必读）

> 我们对外的说法是「**完全离线、不上传数据**」。这里把边界一次说清。

**会联网吗？** **不会。** 本技能只读你给的数据字典、只写 SQL 文本，**不连接任何数据库、不发起任何网络请求**
（`run_manifest.json` 记录 `network_access: false`）。代码里不含任何服务器地址、webhook 或密钥。

**最大的风险与边界（不藏着）**

- 它产出的是**取数 SQL 文本**，**不是审计结论**；SQL 跑出来的数据要交给 `expense-audit-v2` 等技能分析。
- **字段语义必须与 IT 确认**：技能只给**候选 + 置信度**，不替你确认"这一列到底是不是工号"。
- SQL 会**直接在你们的生产库上执行**——请交给 DBA、在只读/从库上跑，并自行判断权限与性能。
- **缺字段绝不硬凑**：会明确列出"这个需求需要哪些字段、你的字典里没有"，让你回 IT 要。

## Purpose

补上审计最常卡住的那一环：**"只知道业务系统名 → 拿到能分析的数据"**，中间那一步是 **SQL**。

## Use this skill when

- 用户知道系统名，但不知道怎么把数据变成可分析的表格；
- 要把审计需求（重复报销 / 发票号重复 / 自审自批 / 周末消费 …）翻译成 **SELECT 语句**；
- 手上有（或能要来）一份**数据字典**（表名 / 字段名 / 中文名）。

## Do not use this skill when

- 要做数据分析、出审计结论（用 `expense-audit-v2` 等）；
- 要连接数据库执行查询（本技能**不连库**，只产出 SQL 文本）；
- 没有数据字典、也不打算向 IT 要（无字段信息时无法可靠生成）。

## Workflow

1. **要一份数据字典**：告诉用户找 IT 要「表名 / 字段名 / 类型 / 中文名」清单，**CSV 就行**。
2. **建议字段映射**：`python3 scripts/run_sql_builder.py --schema <字典> --output <新目录>`
   → 产出 `mapping.suggested.json`（每个标准字段的**候选 + 置信度**）。
3. **人工确认**：把候选拿给 IT 对一遍（**这一步必须人工**，技能不替用户确认）。
4. **按需求生成 SQL**：可加 `--need duplicate-claim,self-approval` 只生成部分；`--dialect oracle` 选方言。
5. **交给 DBA 执行**：`sql/*.sql` 在只读/从库上跑，导出 CSV。
6. **闭环**：把 CSV 交给 `expense-audit-v2` 做审计。

> 缺字段时不会硬凑：`missing_fields.csv` 明确列出"哪些需求需要哪些字段"。

## Parameters

| 参数 | 说明 |
|---|---|
| `--schema` | 数据字典（CSV/XLSX）：`表名, 字段名, 类型, 中文名, 备注`（最少前两列） |
| `--map`（可选） | 与 IT 确认后的字段映射 JSON（不给则先产出建议映射） |
| `--need`（可选） | 只生成这些需求（逗号分隔）；默认全部 |
| `--dialect` | `sqlite`（默认）/ `mysql` / `postgres` / `sqlserver` / `oracle` |
| `--output` | 输出目录（须为空） |

## Output contract

```
out/
├── sql/*.sql                # 给 DBA 跑（带注释：依赖字段 / 注意事项）
├── mapping.suggested.json   # 字段映射建议（候选 + 置信度）——拿去跟 IT 确认
├── missing_fields.csv       # 还缺哪些字段（回 IT 要）
├── summary.md               # 几步走指引
├── data_quality.md          # 数据字典体检（映射结果 / 未映射字段）
├── run_manifest.json        # 哈希 / 参数 / network_access: false
└── dashboard.html           # 全景图
```

## References

- 需求与模板目录：[references/sql-catalog.md](references/sql-catalog.md)
