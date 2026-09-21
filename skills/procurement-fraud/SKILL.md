---
name: procurement-fraud
description: "对供应商主数据、采购订单、付款、员工和投标文本执行采购舞弊红旗筛查，识别共享属性（银行账号/电话/地址/邮箱/法人）、员工—供应商关联、peer-group 价格离群、拆单、流程时序倒置（先采购后审批/先收货后订单/先付款后审批）、采购员集中度、投标文本余弦相似度和报价模式，并生成可追溯线索、关系图与调查移交包。Use when the user asks to screen procurement CSV/XLSX data, vendor master, purchase orders, payments, bid text, or mentions shared accounts, split orders, three-way match, approval timing, red flags, collusion indicators, or asks for findings.jsonl/relationship_graph.json/investigation_handoff.json. Do not use for employee expense claims, draft policies, write contracts, vendor onboarding/offboarding, automatic blacklisting, payment freezes, final collusion/corruption/guilt decisions, vendor email drafting, internet lookups, or summarization."
license: Apache-2.0
metadata:
  author: "aiaudit"
  version: "0.1.1"
  aiaudit_compatibility: "Agent Skills hosts; offline; Python 3.10+ recommended; openpyxl for XLSX"
---

# Procurement Fraud Red-Flag Detection

## Purpose

对供应商主数据、员工信息、采购订单、付款、投标清单和投标文本进行多模块红旗筛查，输出可解释、可追溯的复核线索、关系图和可选调查移交包。相似、关联或高价都不是串标、利益输送或舞弊认定。

用户的明确指示优先。不得因本 skill 自动联网查工商、扩大人员范围、停止付款、停用供应商或启动调查。

兼容 Agent Skills 宿主；离线优先，建议 Python 3.10+。CSV/TXT 使用标准库，XLSX 另需 `openpyxl`。

## Use this skill when

- 用户要求检查供应商马甲、共享账号/电话/地址、员工供应商关联。
- 用户要求分析采购价格异常、疑似拆单、先采购后审批、集中度或投标文本雷同。
- 用户需要把多个采购红旗连接成带证据的复核路径。

## Do not use this skill when

- 任务只是撰写采购制度、招标文件或供应商邮件。
- 用户要求算法直接认定串标、腐败、利益输送或责任人。
- 只有费用台账或已进入调查案卷；分别使用 `expense-audit` 或 `investigation-assistant`。

## Operating principles

1. 默认离线、只读；源文件先 hash，输出到新目录。
2. 按表分别体检、映射和标准化，保留 bad rows 与覆盖率。
3. 先执行共享属性、时间顺序、统计、拆单和 TF-IDF 等确定性分析，再由宿主 Agent 解释。
4. 价格必须在 peer group 内比较；文本相似度阈值是本次配置，不是法律标准。
5. 公共注册地址、集团总机、支付平台账户、强制招标模板、独家供应商等合理异常必须通过白名单或人工复核处理。
6. 单一弱信号不得形成严重指控；多模块信号也只生成建议移交，且要求人工批准。

## Inputs and profiles

输入目录可包含：`vendors.csv|xlsx`、`purchase_orders.csv|xlsx`；可选 `employees`、`payments`、`bids` 和 `bid-docs/*.txt|md`。字段合同见 [数据合同](references/data-contract.md)，参数样例见 [config.json](examples/input/config.json)。

只使用用户在当前任务中明确提供的附件、准确路径或粘贴记录。若没有当前输入，先列出所需文件并请用户提供；不得用 `find` 等方式遍历工作目录、复用其他任务的 `normalized_*`/历史输出，或把包内合成样例当作用户数据，除非用户明确要求运行样例。

- Full Execution：运行本地脚本，完成全部可用模块。
- Host Native：使用表格、SQL 或数据分析工具复现 [模块与规则](references/module-catalog.md)。
- Reasoning Only：小片段只做局部关系和条款比较，说明样本范围，不生成总体比例或声称全量检查。

无法唯一映射核心字段时，先输出候选字段；只在会改变关键计算且无法合理判断时向用户确认。

## Workflow

1. 确认授权范围、期间、业务单位、币种、审批阈值、公共属性白名单和投标公共模板。
2. 盘点输入、计算 SHA-256，分别检查行数、主键、空值、类型和跨表匹配覆盖率。
3. 标准化供应商名称、电话、邮箱、地址、银行账号、标识符、金额和日期；不得覆盖原文件。
4. 按可用数据依次运行共享属性、员工—供应商关系、peer-group 价格离群、拆单、流程时序、集中度、投标文本相似度和报价模式。
5. 生成 `relationship_graph.json`；每条正式 finding 绑定 evidence。
6. 对同一实体出现多个独立高风险类型时生成 `investigation_handoff.json`，但不得自动启动调查。
7. 宿主 Agent 主动寻找合理解释、反证和缺失证据，再向用户给出复核顺序。

## Full Execution command

```bash
python3 scripts/run_procurement_audit.py \
  --input-dir /path/to/procurement-files \
  --config /path/to/config.json \
  --output /path/to/new-output-directory
```

先用 `python3 scripts/run_procurement_audit.py --check-env` 检查环境。PDF/OCR 不由核心脚本处理：由宿主已有文档工具先提取文本到 `.txt`，并保留原 PDF hash、页码或段落映射。

## Output contract

输出：标准化表、`bad_rows.csv`、`findings.csv/jsonl`、`evidence.jsonl`、`relationship_graph.json`、`investigation_handoff.json`、`summary.md`、`data_quality.md`、`run_manifest.json`。解释顺序见 [输出协议](references/output-contract.md)。

## Failure and fallback

- 缺供应商或采购订单核心表：停止正式全量运行，输出缺口；不得改读其他任务的标准化表或历史输出，也不得用临时手工规则虚构模块结果。
- 可选表缺失：继续运行其余模块，并在 manifest 记录跳过原因。
- peer group 太小或 MAD 为零：跳过统计组；不要改用全体采购统一 Z-score。
- 未提供审批阈值：跳过拆单；未提供公共模板：相似度仍可跑，但提高人工复核力度。
- 文档只有 PDF：请求先做可追溯文本提取；不得把空文本视为“不相似”。
- 输出目录非空：换新目录，不覆盖旧运行。

## Final quality checks

- 每个 finding 的 evidence 引用存在，源表、行号或投标文档 hash 可回源。
- 阈值、白名单、peer-group 字段和文本参数写入 manifest。
- 共享地址白名单和公共模板反例没有被提升为强关联证据。
- 文本结果称为“高相似复核线索”，不称“串标成立”。
- handoff 的 `human_approval_required` 为 `true`，且不会自动触发外部动作。

## References

- 输入文件与字段：[references/data-contract.md](references/data-contract.md)
- 八个分析模块、白名单和评分：[references/module-catalog.md](references/module-catalog.md)
- 输出与调查移交：[references/output-contract.md](references/output-contract.md)
