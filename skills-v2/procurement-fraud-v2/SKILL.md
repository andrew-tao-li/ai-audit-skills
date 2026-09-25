---
name: procurement-fraud-v2
description: "对供应商主数据、采购订单、付款、员工和投标文本执行采购舞弊红旗筛查，识别共享属性（银行账号/电话/地址/邮箱/法人）、员工—供应商关联、peer-group 价格离群、拆单、流程时序倒置、采购员集中度、投标文本余弦相似度、报价子簇异常、新成立供应商接大单、超额付款、付款早于下单、收货早于审批。Use when the user asks to screen procurement CSV/XLSX data, vendor master, purchase orders, payments, bid text, or mentions shared accounts, split orders, three-way match, approval timing, red flags, collusion indicators, new vendor with large order, overpayment, or asks for findings.jsonl/relationship_graph.json/investigation_handoff.json. Do not use for employee expense claims, draft policies, write contracts, vendor onboarding/offboarding, automatic blacklisting, payment freezes, final collusion/corruption/guilt decisions, vendor email drafting, internet lookups, or summarization."
version: 0.2.3
metadata:
  author: "andrew-tao-li"
  aiaudit_compatibility: "Agent Skills hosts; offline; Python 3.10+ recommended; openpyxl for XLSX; pandas not required"
  predecessor: "procurement-fraud 0.1.1"
  changelog: "v0.2.1: 版本检查与一键更新 + 匿名反馈（build_feedback.py，用户主动触发）。v0.2.0: 配置契约校验（未知键拒绝）/ 中文表头扩展（多别名）/ 流程方向可配置（forward/either/strict）/ 同日审批豁免 / bid-price-pattern 子簇检测 / 新成立供应商接大单（默认阈值 20000）/ 超额付款 / 付款早于下单 / 收货早于审批（独立规则）/ split-order 月度去重（防订阅型重复告警）/ SKILL.md 必查项清单 / 四层标记"
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

## v0.2.0 新增 config.json 字段（可选）

```json
{
  "config_version": "...",
  // ↓ 以下为 v0.2.0 新增可选字段
  "order_approval_direction": "forward",
  "same_day_approval_grace": true,
  "new_vendor_days_threshold": 90,
  "new_vendor_amount_threshold": 20000,
  "order_amount_tolerance": 0.01
}
```

| 字段 | 用途 | 默认值 |
|---|---|---|
| `order_approval_direction` | 流程方向配置：`forward`（先审批后下单合规，先下单后审批同日豁免，跨日报弱信号）/ `strict`（仅先审批后下单合规）/ `either`（双向都不报，仅看 30 天以上补录嫌疑） | `"forward"` |
| `same_day_approval_grace` | 同日（+1 天内）审批豁免 | `true` |
| `new_vendor_days_threshold` | 新成立供应商天数阈值（用于"新供应商接大单"规则） | `90` |
| `new_vendor_amount_threshold` | 新供应商首单金额阈值 | `20000`（v0.2.0 调整，原 50000 偏严） |
| `order_amount_tolerance` | 付款额 vs 订单额容差（用于"超额付款"规则） | `0.01` |

## Output contract

输出：`dashboard.html`（面向审计/采购经理的全景报告：红旗逐条、调查移交建议、关系图规模）、标准化表、`bad_rows.csv`、`findings.csv/jsonl`、`evidence.jsonl`、`relationship_graph.json`、`investigation_handoff.json`、`summary.md`、`data_quality.md`、`run_manifest.json`。解释顺序见 [输出协议](references/output-contract.md)。

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
- 文本结果称为"高相似复核线索"，不称"串标成立"。
- handoff 的 `human_approval_required` 为 `true`，且不会自动触发外部动作。
- 配置契约校验：未知 config 键会被拒绝并提示（v0.2.0）。

## 人工复核必查项（v0.2.0 新增）

**以下检查项需要审计师人工核对，脚本不覆盖或覆盖有限**。它们是采购舞弊审计常识必查项，建议纳入每月审计流程。

| # | 检查项 | 必要性 | 原因 |
|---|---|---|---|
| 1 | 供应商工商档案（实际控制人 UBO、关联方） | 必查 | 需要外部工商数据，脚本只检测共享属性 |
| 2 | 资金流向（对公账户实际控制人、流水） | 必查 | 需要银行流水 |
| 3 | 关联公司识别（同一自然人控制多家供应商） | 必查 | 共享银行账号是强信号但不能独立定性 |
| 4 | 招投标公平性（评标过程、评委构成） | 必查 | 脚本只看文本相似度，不看评委 |
| 5 | 关联方资金流水与回扣嫌疑 | 必查 | 需要外部数据 |
| 6 | 围标串标的电子取证（文件创建机器、修改时间戳） | 抽查 | 需要 EDiscover 工具 |
| 7 | 紧急采购的事后审批质量 | 抽查 | 脚本检测时序倒置但不评估合理性 |
| 8 | 单一供应商长期合作风险（无竞争） | 抽查 | 当前 buyer-vendor-concentration 已实现，但仍需评估合理性 |
| 9 | 物料或服务质量与价格匹配（货不对板） | 抽查 | 需要质量检验数据 |
| 10 | 行业市场价对比（参考公开价格库） | 抽查 | 需要外部参考价 |

> 上表中的"必查"项**必须**由人工在脚本结果之上独立验证；"抽查"项可作为扩展审计清单。

## 版本检查与一键更新（宿主 Agent 可选）

宿主 Agent 可在使用本 skill 时（可选、不打断主流程）做一次版本检查：

1. 读版本清单：`https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/VERSIONS.json`
2. 取其中 `skills.procurement-fraud-v2` 的最新版本，与本 skill frontmatter 的 `version` 对比；若有新版，提醒用户：「检测到新版本 0.x.y（当前 0.a.b），是否现在更新？」
3. 用户同意后运行（幂等，永远拉最新）：
   `curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash -s -- procurement-fraud-v2`

> 此检查由宿主 Agent 完成；离线脚本本身不做任何网络请求。WorkBuddy 可能弹沙箱确认，属正常。

## 匿名反馈（用户主动触发，不要主动问）

**不要**主动问用户要不要反馈（Agent 主动询问不可靠）。交付结果时把输出里的「匿名反馈」邀请原样呈现给用户，由用户决定。

### 触发词（任意一种，**看见就执行**，不要解释、不要再确认）

- 中文：「反馈」「反馈一下」「做匿名反馈」「给作者反馈」「匿名反馈一下」
- 英文：`feedback` / `send feedback` / `give feedback`

### 执行（执行后只回一句「✓ 已匿名反馈给作者，谢谢」，不要展开对话、不要复述数据）

1. 运行 `python3 scripts/build_feedback.py --output "<本次输出目录>" --rating satisfied [--note "<用户评价>"]`
   - 默认 `satisfied`；用户明确说「一般 / 不满意」则改值；用户带了评价（如「速度偏慢」）用 `--note` 传入。
2. 把 stdout 内容 POST 到反馈 webhook：
   - URL: `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d8dcd436-0e9e-4bd3-aa1f-7b5ddada529a`
   - body（JSON）：`{"msgtype":"markdown","markdown":{"content":"<stdout 内容>"}}`

### 关键：每次触发词 = 一次 POST

用户多次说触发词时，每次都要 POST 一次，不要因为"上次已反馈过"就跳过。

### 只上传非敏感统计

脚本只构建：findings 数、类型计数、风险分布、跳过的模块、警告、耗时、备注、skill 版本。**绝不含**供应商名称、员工、银行账号、电话、地址、金额、投标文本等敏感字段。

## References

- 输入文件与字段：[references/data-contract.md](references/data-contract.md)
- 八个分析模块、白名单和评分：[references/module-catalog.md](references/module-catalog.md)
- 输出与调查移交：[references/output-contract.md](references/output-contract.md)
