---
name: investigation-assistant
description: "在授权、人员、期间和数据来源已明确后，把举报、投诉、邮件、消息和日志整理为可追溯调查工作空间，包括证据清单与哈希、只读副本、时间线、关系、证据矩阵、反证、假设登记和访谈计划。必须先取得显式授权（authorization_confirmed=true）、明确范围（persons_in_scope/date_range/allowed_sources）和禁用联网（network_access=false）。Use when the user asks to organize an authorized internal investigation; mentions chain-of-custody, custody log, SHA-256 integrity check, scope filter, out-of-scope exclusion, entity index, evidence matrix, hypothesis register, interview plan, case memo, or authorized whistleblower case files. Do not use for initial expense/procurement screening, covert collection, secret monitoring, private chat scraping, social media lookups, contacting subjects directly, deleting evidence, expunging records, or automatic discipline/guilt decisions."
license: Apache-2.0
metadata:
  author: "aiaudit"
  version: "0.1.2"
  aiaudit_compatibility: "Agent Skills hosts; offline; Python 3.10+ recommended; CSV/TXT/MD core"
---

# Investigation Assistant

## Purpose

把已获授权的举报、投诉、邮件/IM 导出和访问日志整理为受控调查工作空间：原件清单与 hash、只读副本、标准化记录、时间线、实体索引、关系、证据矩阵、假设与反证登记、访谈计划。它辅助组织材料，不自动调查、联系人员、认定责任或处分。

用户的明确指示优先。不得借本 skill 扩大取证时间、人员、数据来源或联网范围。

兼容 Agent Skills 宿主；离线优先，建议 Python 3.10+。核心 CSV/TXT/MD 流程只使用 Python 标准库。

## Use this skill when

- 已有明确调查目的和授权，需要整理举报、投诉、邮件、聊天、系统或设备日志。
- `expense-audit` 或 `procurement-fraud` 的人工批准移交需要建立调查工作空间。
- 用户希望建立可追溯时间线、证据矩阵、反证清单或访谈计划。

## Do not use this skill when

- 授权、目的、时间、人员或数据来源尚未明确。
- 用户要求秘密扩大监控、绕过访问控制、自动联系被调查人、删除/修改原始证据或直接定罪。
- 用户只是做费用或采购的初筛，还没有人工决定进入调查。

## Scope gate

正式运行前必须取得 scope 文件，至少包含：`case_id`、`purpose`、`authorization_confirmed:true`、`date_range`、`persons_in_scope`、`allowed_sources`、`network_access:false`。模板见 [scope.json](examples/input/scope.json)。

输入来源限制必须先于任何文件系统探查：只使用用户在当前任务中明确附带、粘贴或给出准确路径的 scope 和案件材料。若当前任务没有这些输入，立即列出所需文件并请用户提供；不得先列目录、搜索工作区、读取本 skill 的 `examples/`，也不得复用其他任务或历史案卷。模板只用于解释格式，绝不能当作本次案件输入。

授权不明确时停止正式处理，并列出缺失字段；不要通过搜索其他目录来补齐。联网需求必须另行说明什么数据会离开设备、发送给谁、为什么，本核心脚本始终不联网。

## Operating principles

1. Chain of custody 先于总结：先盘点、SHA-256、登记 Evidence ID，再复制到 `evidence/raw`，之后只处理 working copy。
2. 输入目录只读，输出到新目录；复制后再次 hash，验证内容一致。
3. Facts、Inferences、Hypotheses、Judgment 分开。用户指控本身是待验证 allegation/hypothesis，不是事实。
4. 主动寻找支持证据、反证、替代解释和缺失证据，避免只强化最初怀疑。
5. 每条时间线、关系、矩阵和 finding 必须能回到 evidence。
6. 只处理 scope 中允许的文件、期间和人员；越界行进入 `out_of_scope_rows.csv`，不得静默使用。

## Inputs and profiles

核心脚本支持 CSV 消息/日志以及 TXT/MD 文本。字段别名与标准化规则见 [normalization.md](references/normalization.md)。

- Full Execution：运行脚本建立完整工作空间。
- Host Native：用宿主文件、表格和哈希能力复现 [chain of custody](references/chain-of-custody.md) 与 [调查工作流](references/investigation-workflow.md)。
- Reasoning Only：只有粘贴片段时，只生成临时事实/假设表，明确没有完成原件登记和全量调查。

## Workflow

1. 校验 scope gate；记录授权来源和本次允许范围。
2. 仅盘点 `allowed_sources`，计算 SHA-256、大小和类型，分配 Evidence ID。
3. 复制原件到新工作空间 `evidence/raw`，再次 hash 验证；记录 chain-of-custody 事件。
4. 在 `derived/` 生成标准化消息、日志和文本行；超出人员/时间范围的结构化行单列。
5. 构建每条事件都含 `evidence_id` 的时间线、实体索引和关系边。
6. 依据 scope 中 issue 的关键词建立证据矩阵；支持与反证分别列示。关键词命中只是检索结果，不是相关性结论。
7. 建立 hypothesis register：支持证据、反证、缺口、替代解释和状态都必须显式保留。
8. 生成访谈计划与 memo 模板；宿主 Agent 回到原文复核后再补写，不得把模板当调查结论。

## Full Execution command

```bash
python3 scripts/build_case_workspace.py \
  --input-dir /path/to/authorized-case-input \
  --scope /path/to/scope.json \
  --output /path/to/new-case-workspace
```

先用 `python3 scripts/build_case_workspace.py --check-env` 查看支持格式。若要处理 PDF、Office 或邮箱专有归档格式，先用宿主已有工具做可追溯提取，并把原文件与提取结果同时列入 scope；核心 skill 不默认上传云端解析。

## Output contract

输出包括 `evidence_inventory.jsonl`、`evidence.jsonl`、`chain_of_custody.jsonl`、`evidence/raw/`、`derived/normalized_messages.csv`、`derived/normalized_logs.csv`、`timeline.csv`、`entity_index.csv`、`relationships.json`、`evidence_matrix.csv`、`hypothesis_register.csv`、`findings.jsonl`、`interview_plan.csv`、`case_memo_template.md`、`run_manifest.json`。详见 [调查工作流](references/investigation-workflow.md)。

## Failure and fallback

- scope gate 不完整或 `authorization_confirmed` 不为 true：停止，不复制或解析材料。
- allowed source 缺失或路径跳出输入目录：停止并报告精确文件；不扩大搜索。
- 时间戳无法解析：保留记录与 evidence，但不放入排序时间线，并写入数据质量警告。
- 未识别结构化文件：作为原始证据登记，但不猜测字段含义。
- 关键词无命中：保持 issue 为 open，并列出缺失证据；不能写“未发生”。
- 输出目录非空：使用新目录，不覆盖历史案卷。

## Final quality checks

- raw 副本 hash 与源文件一致；chain-of-custody 覆盖登记、复制和派生。
- 时间线和关系中的 evidence ID 全部存在。
- 每个 issue 同时保留支持、反证和缺失证据栏。
- findings 的 facts 来自具体记录，hypotheses 明确标注待验证，human review 为 true。
- manifest 显示 `network_access:false`，并记录 scope hash、脚本 hash 和所有输出。
- memo 不含最终责任、处分或法律结论。

## References

- 原件登记与副本：[references/chain-of-custody.md](references/chain-of-custody.md)
- 消息、日志和文本标准化：[references/normalization.md](references/normalization.md)
- 矩阵、假设、反证与访谈：[references/investigation-workflow.md](references/investigation-workflow.md)
