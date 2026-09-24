---
name: expense-audit-v2
description: "用于清洗、体检和审计员工费用、报销、发票、差旅或相关付款台账；分离坏行与标准化结果，识别重复、制度例外、拆分、统计离群、自审自批、发票跨人复用、提交日期倒挂、未来日期等。Use when the user asks to examine, clean, normalize, or audit expense/reimbursement/invoice/travel/meal CSV, XLSX, or pasted records; mentions duplicate claims, policy exceptions, split reimbursements, weekend signals, robust outliers, MAD outlier, self-approval, cross-employee invoice reuse, missing expense type, large amount without proper approval, or asks for findings.jsonl/evidence.jsonl/data_quality reports. Do not use for policy drafting, procurement payments, vendor screening, fraud determinations, reimbursement rejection, disciplinary decisions, secret monitoring, archiving, translation, or summarization."
version: 0.2.1
metadata:
  author: "andrew-tao-li"
  aiaudit_compatibility: "Agent Skills hosts; offline; Python 3.10+ recommended; openpyxl for XLSX; pandas not required"
  predecessor: "expense-audit 0.1.1"
  changelog: "v0.2.1: 新增时空冲突/跨期入账/高频小额三条规则 + 城市字段（出发/目的城市）别名；修复缺费用类型规则 max→min 误用（多限额时漏报）；由真实审计师 16 场景带答案数据驱动。v0.2.0: 配置契约校验（未知键拒绝）/ 中文表头扩展 / 严重度按金额×置信度分级 / 自审自批 / 发票跨人复用 / 提交日期倒挂 / 未来日期（as_of_date 可配置）/ 缺类型按最严格处理 / 发票连号 / 发票号格式异常 / 大额低层级审批 / 节假日（holidays 配置）/ split-expense 月度去重 / SKILL.md 必查项清单 / 四层标记"
---

# Expense Audit

## Purpose

对费用、报销、发票、差旅或付款台账执行可解释的全量风险扫描，生成能回到原始行的 `finding`、`evidence`、数据质量报告和运行清单。输出是复核优先级，不是舞弊或拒付结论。

用户的明确指示优先于本 skill 的默认流程。不得因本 skill 擅自扩大数据范围、联网、上传数据或做处置决定。

兼容 Agent Skills 宿主；离线优先，建议 Python 3.10+。CSV 使用标准库，XLSX 另需 `openpyxl`。

## Use this skill when

- 用户要求检查 CSV/XLSX 报销、费用、发票或差旅数据中的重复、超标、拆单或离群记录。
- 用户需要把大量报销压缩为带证据的优先复核清单。
- 用户只粘贴少量记录时，也可按 Reasoning Only profile 做局部分析。

## Do not use this skill when

- 用户主要是在起草或修订费用制度，而不是分析交易。
- 任务要求直接批准、拒绝、追回、处分或认定舞弊。
- 输入是采购主数据或调查案卷；分别使用 `procurement-fraud` 或 `investigation-assistant`。

## Operating principles

1. 默认离线、只读和最小权限。所有输出写入新目录，不覆盖源文件。
2. 先做数据体检和字段映射，再跑规则。保留 clean、bad rows 和转换日志。
3. 确定性规则和稳健统计先行；宿主 Agent 负责解释、补证问题和沟通草稿。
4. 异常不等于舞弊。把事实、推断、假设和最终判断分开；本 skill 不形成最终判断。
5. 金额阈值只能来自用户制度或配置。未提供制度时，明确跳过制度超标和基于审批阈值的拆单规则。
6. **数据匹配 ≠ 业务实质**。本 skill 只验证「数据之间对得上」，不验证「业务真实发生」。未发现问题不等于没有问题；交付时必须在 `summary.md` 明确划清这条边界，并给出「补充佐证深入核查」的下一步（见 [references/business-substance.md](references/business-substance.md)）。

## Inputs and profile selection

先盘点用户在当前任务中明确提供的文件和分析范围，不要假设目录里的所有文件都获准处理。若当前任务没有附件、准确路径或粘贴记录，只列出所需输入并请用户提供；不得搜索工作目录、复用其他任务的历史输出，或把包内合成样例当作用户数据，除非用户明确要求运行样例。

- Full Execution：有本地 Python 时运行脚本。输入支持 CSV 和 XLSX。
- Host Native：不能运行脚本时，用表格/SQL 工具复现 [规则目录](references/rule-catalog.md)，输出仍遵循 [输出协议](references/output-contract.md)。
- Reasoning Only：只有少量粘贴数据时，说明样本行数、缺失字段和不能执行的规则；不得声称完成全量检查或计算总体异常率。

字段要求与中英文别名见 [数据合同](references/data-contract.md)。若自动映射存在歧义，先输出候选映射；只有影响核心计算且无法合理判断时才向用户确认。制度配置见 [policy-template.json](examples/input/policy.json)。

## Workflow

1. 确认输入文件、期间、币种、制度版本和允许使用的可选主数据。不得默认联网补数据。
2. 计算输入 SHA-256；记录 sheet、行数、字段、空值率、类型失败和重复率。
3. 映射并标准化分析需要的字段。无效关键行进入 `bad_rows.csv`，不得静默删除。
4. 运行 exact duplicate、near duplicate、policy threshold、split expense、周末弱信号和 robust outlier。跳过条件和参数必须进入 manifest。
5. 每个正式 finding 建立行级 evidence；校验所有 `evidence_refs` 都存在。
6. 宿主 Agent 阅读 `summary.md`、`findings.jsonl` 和 `data_quality.md`，合并同主体的模式，列出合理解释、开放问题和需要补充的发票、审批或付款证据。
7. 向用户交付覆盖范围、数据质量、发现数量、最高优先级线索、限制和人工复核边界。

## Full Execution command

```bash
python3 scripts/run_expense_audit.py \
  --input /path/to/expenses.csv \
  --policy /path/to/policy.json \
  --output /path/to/new-output-directory
```

可选参数：`--field-map` 提供 JSON 字段映射，`--sheet` 指定 XLSX 工作表。先用 `python3 scripts/run_expense_audit.py --check-env` 查看环境。

## v0.2.0 新增 policy.json 字段（可选）

```json
{
  "policy_version": "...",
  "limits": [...],
  "approval_thresholds": [...],
  // ↓ 以下为 v0.2.0 新增可选字段
  "holidays": ["2026-10-01", "2026-10-02", "2026-10-03"],
  "large_amount_threshold": 5000,
  "low_level_approver_keywords": ["助理", "实习生", "A901"],
  "as_of_date": "2026-12-31"
}
```

| 字段 | 用途 | 默认值 |
|---|---|---|
| `holidays` | 法定节假日列表；命中后触发 `holiday-signal` finding | `[]`（不启用） |
| `large_amount_threshold` | 超过此值的金额 + 强证据时，risk_score 提升至 ≥4 | `5000` |
| `low_level_approver_keywords` | 审批人字段包含任一关键词 + 大额 → 触发 `large-amount-low-level-approval` | `[]`（不启用） |
| `as_of_date` | `future-date` 规则的基准日 | 系统当前日期 |

## Output contract

完整执行应生成：`clean_expenses.csv`、`bad_rows.csv`、`findings.csv`、`findings.jsonl`、`evidence.jsonl`、`summary.md`、`data_quality.md`、`run_manifest.json`。字段和语言边界见 [输出协议](references/output-contract.md)。

## Failure and fallback

- 缺核心字段：停止正式规则运行，交付字段盘点和建议映射，不伪造结果。
- XLSX 缺 `openpyxl`：告知精确依赖，并建议另存为 UTF-8 CSV；不要自动联网安装。
- 制度缺失：继续做重复和统计规则，明确跳过制度阈值与审批拆单。
- 小样本或 MAD 为零：跳过相应统计组并记录原因，不把算法失败包装成“无异常”。
- 输出目录已有文件：换用新目录；不要覆盖历史运行。

## Final quality checks

- 运行结束返回码为 0，manifest 的 `network_access` 为 `false`。
- 每个 finding 至少有一个存在的 evidence，且 source hash、sheet/row 可回源。
- 所有金额阈值和统计参数可在 manifest 中找到。
- 没有把周末、离群、相似或重复直接写成舞弊、虚假或有罪结论。
- 明确列出未执行规则、缺失数据和人工复核事项。

## 人工复核必查项（v0.2.0 新增）

**以下检查项需要审计师人工核对，脚本不覆盖或覆盖有限**。它们是审计常识必查项，建议纳入每月审计流程。

| # | 检查项 | 必要性 | 原因 |
|---|---|---|---|
| 1 | 发票真伪（票面 OCR / 发票查验平台） | 必查 | 脚本无法验证发票真伪 |
| 2 | 关联交易与利益冲突申报 | 必查 | 需要 HR/合规系统配合 |
| 3 | 票据与原始凭证（合同、行程、签收单） | 必查 | 脚本不持有原始凭证 |
| 4 | 报销与业务实质（是否真实发生） | 必查 | 脚本只能识别异常，无法判定真伪；见 [业务实质性声明](references/business-substance.md) |
| 5 | 关联方资金往来与回扣嫌疑 | 必查 | 需要银行流水等外部数据 |
| 6 | 审批层级匹配（金额是否超出审批人权限） | 抽查 | v0.2.0 已支持 large_amount_threshold + low_level_approver_keywords 配置 |
| 7 | 频繁小额累计（高频套现模式） | 抽查 | v0.2.1 已支持 high-frequency-small-amount（high_frequency_min_count 等配置） |
| 8 | 月度预算执行率 | 抽查 | 需要预算系统数据 |
| 9 | 跨部门代报销（销售帮研发报销） | 抽查 | 需要结合组织架构判断 |
| 10 | 跨期入账（费用期间与报销期间不一致） | 抽查 | v0.2.1 已支持 cross-period（cross_period_months 配置） |

> 上表中的"必查"项**必须**由人工在脚本结果之上独立验证；"抽查"项可作为扩展审计清单。

## References

- 字段映射与质量门槛：[references/data-contract.md](references/data-contract.md)
- 规则、参数与合理解释：[references/rule-catalog.md](references/rule-catalog.md)
- 输出 Schema 与 Agent 解读顺序：[references/output-contract.md](references/output-contract.md)
- 业务实质性声明与深入核查佐证清单：[references/business-substance.md](references/business-substance.md)
