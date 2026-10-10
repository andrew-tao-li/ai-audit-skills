---
name: expense-audit-v2
description: "用于清洗、体检和审计员工费用、报销、发票、差旅或相关付款台账；分离坏行与标准化结果，识别重复、制度例外、拆分、统计离群、自审自批、发票跨人复用、提交日期倒挂、未来日期等。Use when the user asks to examine, clean, normalize, or audit expense/reimbursement/invoice/travel/meal CSV, XLSX, or pasted records; mentions duplicate claims, policy exceptions, split reimbursements, weekend signals, robust outliers, MAD outlier, self-approval, cross-employee invoice reuse, missing expense type, large amount without proper approval, or asks for findings.jsonl/evidence.jsonl/data_quality reports. Do not use for policy drafting, procurement payments, vendor screening, fraud determinations, reimbursement rejection, disciplinary decisions, secret monitoring, archiving, translation, or summarization."
version: 0.2.21
slug: andrew-tao-li-expense-audit
displayName: 费用报销审计
summary: 扫描费用/报销/发票/差旅台账，识别重复报销、超制度上限、拆分报销、自审自批、发票跨人复用等异常，输出可追溯证据与经理可读报告。辅助分析，不替代专业审计判断。
license: MIT-0
homepage: https://github.com/andrew-tao-li/ai-audit-skills
tags: [审计, 费用审计, 报销, 发票, 差旅, 反舞弊, 财税处理, 风险风控]
metadata:
  author: "andrew-tao-li"
  aiaudit_compatibility: "Agent Skills hosts; offline; Python 3.10+ recommended; openpyxl for XLSX; pandas not required"
  predecessor: "expense-audit 0.1.1"
---

# Expense Audit

## 联网与风险（必读）

> 我们对外的说法是「**完全离线、不上传数据**」。这里把边界一次说清，避免任何误解。

**会联网吗？** 会，但**只有一处**，而且可以关：

| 场景 | 动作 | 方向 | 能否关闭 |
|---|---|---|---|
| 版本检查（可选） | 读取一个**公开的版本号文件**（`VERSIONS.json`） | **只读下载** | 能——用户说「不用检查更新」即跳过 |

**会外发数据吗？** **不会。**

- 核心分析脚本**不做任何网络请求**（`run_manifest.json` 记录 `network_access: false`）。
- 代码里**不含**任何服务器地址、webhook 或密钥；反馈内容只能由**用户自己**复制走、自己发送。
- ⚠️ **历史诚实说明**：**早期版本（≤ v0.3.10）** 曾内置一个「匿名反馈」外发地址与密钥。
  **该地址与密钥已彻底移除**，现在不存在。若你在旧版本里见过它，请以本说明为准。

**最大的风险与边界（不藏着）**

- 本技能是**辅助分析**：**异常 ≠ 舞弊**，结果**不构成任何认定**；正式结论必须由有权人员人工复核后作出。
- 规则是启发式的：**会有漏报和误报**。请先在包内合成示例上验证，再上真实数据。
- 它只读你给它的文件、不改原始资料；但**输出目录**可能含敏感信息（人员、金额），请按你的保密要求存放。

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
7. **只有用户/提示词提到时才提**（v0.2.21）：凡需要**外部数据**才能做的核验（**市场价 / 单价合理性**、以及**外部行程核验**），
   **只有**当用户在对话里、或提示词里**显式提到**时，才**显式提示**用户"可以提供这类数据、格式是什么"。
   **用户提到几次就提示几次**；**从未提到就一个字都不要提**（不要主动推销功能）。见下方「v0.2.21」一节。

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

## v0.2.8 新增 policy.json 字段（可选，默认行为不变）

```json
{
  "status_filter": { "include": ["已同意"], "exclude": ["已撤回", "已拒绝"] },
  "resubmit_window_days": 90,
  "amount_columns": ["机票", "火车", "住宿", "市内交通", "其他"]
}
```

| 字段 | 用途 | 默认值 |
|---|---|---|
| `status_filter` | 按审批状态过滤：`include` 只分析所列状态；`exclude` 排除。被排除的行**不参与分析**，但会完整写入 `excluded_by_status.csv`（绝不静默丢弃）；状态为空的行一律保留 | 不配置 = **完全不启用**（与旧版行为一致） |
| `resubmit_window_days` | 「撤回/拒绝后重提且金额增加」的关联窗口（天）；`0` 表示关闭该规则 | `90` |
| `amount_columns` | 台账金额分散在多列、且没有「小计」列时，把这些列**求和**当作单条金额（仅在该行没有单一金额列时生效） | 不配置 = 不启用 |

> **为什么要有 `status_filter`**：真实台账里「已撤回 / 已拒绝」的记录默认也会参与分析，会让「同员工同日同金额」等规则产生大量假阳性
> （实测某真实台账 47 条发现中 39 条属此类）。配置后噪声消失，真正值得看的信号（例如**撤回后重提且金额增加**）才会浮出来。
>
> **多列金额 / 表头不在第一行 / 发票号为空** 等接入问题，见 [真实台账接入指南](references/field-mapping-guide.md)。

## v0.2.9 出差交叉核验（可选，有料自醒）

报销的真实性，常常要靠**出差申请**和**打卡记录**来印证。提供任一份，本技能就**自动追加**交叉核验：

```bash
python3 scripts/run_expense_audit.py \
  --input 报销台账.xlsx \
  --travel-requests 出差申请.xlsx \   # 可选
  --attendance 打卡记录.xlsx \         # 可选
  --policy policy.json --output ./out
```

| 提供了什么 | 自动启用 |
|---|---|
| 只有 `--input` | **与上一版完全一致**（一条新规则也不跑） |
| `+ --travel-requests` | 「差旅报销无对应出差申请」 |
| `+ --attendance` | 「报销称外地，但当天有公司打卡」、「打卡地点与出差城市不一致」 |
| 两者都提供 | 以上全部 |

**「是否在公司」的三层判定**（按可得性从高到低，拿到一层就停）：
1. **显式布尔**（`是否在公司` / `打卡类型`）——最可靠；
2. **经纬度 + 半径**（与 `company_locations` 算距离，半径可配，默认 1000 米；支持多办公地）；
3. **地点文本**（与 `company_location_keywords` 匹配）。
> 三层都拿不到 → 标「未知」并**跳过**，不猜、不报。

### ⚠️ 口径确认：出差申请能不能替代打卡？

**默认口径：能**（多数公司制度如此——"因出差无法打卡的，以出差申请为准"）。
**但有的公司要求出差期间也要打卡。** 所以：

> **当用户提供了打卡数据时，请主动确认一句**：
> 「默认我按『出差申请可以替代打卡』来理解，也就是出差期间没有公司打卡属正常；
> 如果贵司政策是**出差期间也要求打卡**，请告诉我，我会额外核对出差期间的缺卡。」
>
> 用户确认后，把 `travel_cross_check.require_swipe_during_travel` 设为 `true` 即可。

### 措辞红线（务必遵守）

- **「当天有公司打卡」≠「人没出差」**——可能是**代报销**、同事代交、或出差前后到岗。只能说"请核实**实际出差人**"。
- **「无出差申请」≠「没出差」**——可能没走 OA，或走了线下审批。
- **「打卡地与出差地不一致」** 只是提示——可能中转、改道或地点解析偏差，由用户判断是否需要介意。

配置字段见 [rule-catalog](references/rule-catalog.md) 与 [真实台账接入指南](references/field-mapping-guide.md)。

## v0.2.13 新增：日期、口径与三项可选规则（**新增能力全部默认关闭**）

### 直接生效（不需要任何配置）

- **中文日期**：`2026年10月09日`、`2026年10月9日`、`2026年10月09日 12:30`、`20261009` 等都能识别（旧版会把它们当坏行）。
- **自审自批口径**：报销人可以是**工号或姓名**；若出现「审批人是姓名、报销人是工号」这类**口径不一致**，会在 `data_quality.md` 明确提示（不再静默漏检）。想同时支持两种，表里同时给「工号」与「姓名」两列。

### 可选规则（写进 `policy.json` 才启用；不写 = 与旧版完全一致）

| 字段 | 用途 | 默认 |
|---|---|---|
| `split_cross_merchant` | **跨商户拆单**：同一员工在窗口内、**跨 ≥2 个商户**的多笔（每笔低于阈值、合计超过阈值）→ `split-expense-cross-merchant`（配合 `approval_thresholds` / `split_window_days`） | `false` |
| `large_amount_check` | **绝对大额**：公司没有制度额度时，按 `large_amount_threshold` 给出复核线索 → `large-amount`（与「大额低层级审批」自动去重） | `false` |
| `vendor_concentration_check` | **商户集中度**：某员工/部门支出过度集中于单一商户 → `vendor-concentration` | `false` |
| `vendor_concentration_min_count` | 商户集中度：该商户的最少笔数 | `5` |
| `vendor_concentration_share` | 商户集中度：占比阈值 | `0.6` |
| `vendor_concentration_scope` | 商户集中度口径：`employee`（默认）/ `department` | `employee` |

### 可选白名单（命令行 `--allowlist <csv>`）

把"已知无风险"的行（小额固定支出、上期已核实单据）从告警里排除。**只压制「该条告警的每一行都命中」的情况**，
且被压制内容**完整**写入 `suppressed_findings.csv`，并在 `data_quality.md` 与 `run_manifest.json` 计数——**绝不静默丢弃**。

```csv
expense_id,employee_id,vendor_name,invoice_number,expense_type,amount_max,reason
,,餐厅B,,餐饮,500,园区日常餐费（已核实）
E2025001,,,,,,上期已核实
```

> 空列 = 通配；`amount_max` = 金额上限。至少填一个条件，否则该行会被忽略。不提供 `--allowlist` 时，本功能完全不参与（与旧版一致）。

## v0.2.15 新增：外部核验与凭证规则（**全部可选、默认关闭，技能零联网**）

### 外部行程核验（`--travel-verification <csv>`）

把**外部查到的航班/行程记录**喂进来，与报销单据逐字段比对：

| 情况 | 结果 |
|---|---|
| 查到且一致 | 不产生 finding |
| 查到但不一致（航班号/日期/方向/乘机人） | `travel-verification-mismatch`（**强**） |
| **在给定来源中查不到** | `travel-verification-not-found`（**弱**）；**「查不到」≠「虚构」** |

> **本技能不做任何联网查询。** 核验数据由**你/你的智能体**取得后提供（与 `--travel-requests` / `--attendance` 同一模式）。
> 取得方法、来源可靠性、合规提醒、输入格式 → [references/travel-verification-guide.md](references/travel-verification-guide.md)。

> **v0.2.17 起**：若台账里**含航班/订座号信息**但**未提供** `--travel-verification`，交付时 `summary.md` 会自动附一段
> 「**去哪里查 + 怎么填**」的指引（`data_quality.md` 里也有一条）。**请把它一并转达给用户**——用户提供了航班信息，
> 就说明他有这个期待。台账里没有航班信息时**不会**出现这段（不打扰）。

### 两条可选凭证规则（写进 `policy.json` 才启用；不写 = 与旧版一致）

| 字段 | 用途 | 默认 |
|---|---|---|
| `shared_voucher_check` | 同一凭证（`pnr`/订座号）被**多名员工各自报销** → `shared-voucher-multiple-employees` | `false` |
| `voucher_completeness_check` | 凭证要素完备性（缺发票号 / 发票日期）→ `voucher-incomplete` | `false` |

> 新增字段别名 `flight_no`（航班号）与 `pnr`（订座号）已支持；表里没有这些列时，相关规则自动跳过。

## v0.2.16 新增：凭证内部一致性（**完全离线、可选、默认关闭**）

`policy.json` → `"voucher_consistency_check": true` 时启用——**不需要联网**，专门抓"假票/伪行程单常见的自相矛盾"：

| 规则 | 检查 |
|---|---|
| `ticket-number-reused` | 同一**票号**在台账里重复出现（同票多报 / 多人共用一票） |
| `ticket-issue-after-flight` | **出票日期晚于**行程/费用日期（先飞后出票） |
| `itinerary-segment-conflict` | 同一**订座号（PNR）**同一天出现**多个不同航段** |

> 配套字段别名：`ticket_number`（票号/电子客票号）、`issue_date`（出票日期）、`pnr`、`flight_no`。
> 表里没有这些列时自动跳过；默认关闭时**与旧版完全一致**。
> 这一块是"**假票很难自洽**"的直接应用——**比外部核验更划算**（零成本、零联网）。

## v0.2.18 新增：住宿凭证交叉核验（**完全离线、可选、默认关闭**）

`policy.json` → `"lodging_cross_check": true` 时启用——来自真实国际差旅审计的三个模式：

| 规则 | 检查 |
|---|---|
| `consecutive-nightly-invoicing` | 同一员工**连续逐晚单独开票**（≥ `lodging_min_nights`，默认 3），疑规避单笔审批阈值 |
| `same-amount-no-invoice` | 同一员工 + 同一商户、金额完全相同、且**均无发票号**（≥ `lodging_same_amount_min_count`，默认 3） |
| `lodging-night-mismatch` | 凭证写的**晚数**与**入离店日期**算出的晚数不符 |

> 配套字段别名：`check_in` / `check_out`（入/离店日期）、`nights`（晚数）、`room_number`（房号）。
> `lodging_types`（默认 住宿/酒店/宾馆/旅馆/民宿/住宿费/房费）可覆盖。默认关闭时**与旧版完全一致**。

## v0.2.20 新增：替票比对 与 日期↔周几（**均为可选、默认不启用**）

### 开票方 ↔ 实际收款方（`--payments <csv>`）

把**支付/收款记录**喂进来，与报销单上的**开票方/发票抬头**比对：**不一致 → `invoice-payee-mismatch`（强）**——
这是"替票/虚开"的典型信号（发票抬头与实际收款方分裂，**即使发票本身为真**）。

```csv
expense_id,payee,invoice_issuer,amount
R1,丙公司,甲维修厂,12000
```

> `invoice_issuer` 可省略，缺省用报销单上的 `vendor_name`。**本技能不联网**，记录由使用者从支付流水/银行回单整理。
> **不提供 `--payments` 时完全不参与**（与旧版逐字节一致）。

### 日期 ↔ 周几一致性（`weekday_check`，默认关闭）

篡改/编造日期时，"周几"常常与真实日期对不上（原件级防伪线索）。
台账含 `weekday`（周几 / 星期几）列**且**开关打开时 → `weekday-mismatch`。

> 台账**不含**该列 → 完全不参与；**含该列但未开启** → 只在 `data_quality.md` 里给一条提示（不产生 finding）。

## v0.2.21 新增：单价合理性（**外部数据，仅在用户/提示词提到时才提**）

> ⚠️ **触发规则（务必遵守）**
>
> - **只有**当用户在对话里、或提示词里**显式提到**「单价是否合理 / 市场价 / 报价偏高 / 价格合理性」这类话题时，
>   才**显式提示**用户：本技能可以核验单价合理性，但**需要提供市场价格参考**，并给出下面的格式与做法。
> - 用户**提到几次就提示几次**（第一次、第二次完全一样）。
> - 用户**从未提到**（对话里没提、提示词里也没提）→ **不要主动提，一个字都不要提**。

**触发时，照下面说（可调整措辞）**：

> 你要核验「单价是否合理」的话，需要给我一份**市场价格参考**——你自己的采购价、行业报价、第三方比价都可以。
> CSV 一行一个项目：`项目,单位,最高价,来源`（例：`起动机,个,1200,市场比价`）。
> 放工作目录里告诉我文件名，或直接贴给我都行；有了它，我会把报销单的单价与参考价**逐项比对**。

**能力**：`--price-reference <csv>` → `unit-price-above-market`（单价超过参考上限 × (1 + `price_tolerance`，默认 0.30）时提示）。
价格参考列：`item` / `unit` / `max_price`（或 `unit_price`）/ `source`；报销单可含 `item` / `unit` / `unit_price`。
**不提供该文件时完全不参与**（与旧版逐字节一致）。

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

## 版本检查与更新（只提示，不自动执行）

> **本技能不会自动下载或执行任何东西。** 这一步可选，且**命令最终由用户自己执行**。

宿主 Agent 可在使用本 skill 时（可选）做一次版本检查：

1. 读取公开版本清单：`https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/VERSIONS.json`
   （这是本技能**唯一的联网动作**：一次只读请求，只下载一个公开的版本号文件，不上传任何东西。）
2. 与本 skill frontmatter 的 `version` 对比；若有新版，**告诉用户**：
   「检测到新版本 0.x.y（当前 0.a.b）。更新命令如下，**需要你自己在终端执行**：」
3. 给出命令——**不要代替用户执行**，也不要用「下载后直接管道交给解释器」的写法（旧版本曾如此，已移除）：

   ```bash
   curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh -o ai-audit-install.sh
   # 先下载，看一眼内容确认无误，再由用户自己执行：
   bash ai-audit-install.sh expense-audit-v2
   ```

   （Windows 无 bash 时改用同目录的 `install.ps1`。）
4. 用户不想检查更新（说「不用检查更新」「离线运行」等）就跳过第 1 步——**不影响任何分析功能**。

## 反馈（完全可选；本技能不会自己往外发）

> **本技能没有任何外发通道**：代码里不含服务器地址、webhook 或密钥；
> **不会自动、也不会在用户触发后发送任何内容**。

**正确做法**：用户想要反馈时，运行下面的脚本生成**非敏感统计**文本，**把原文展示给用户**，
由用户**自己决定**是否发送、以及通过什么渠道（GitHub Issue / 自己的邮箱 / 微信）。

```bash
python3 scripts/build_feedback.py --output "<本次输出目录>" --rating satisfied --note "<用户评价，可选>"
```

这段文本只包含：发现总数、发现类型计数、风险优先级分布、跳过的规则、警告、本轮耗时、用户备注、skill 版本。
**绝不**包含员工、供应商、发票号、金额、币种、事由等敏感字段。
**发送者是用户本人，不是本技能。** 作者的仓库 Issue：<https://github.com/andrew-tao-li/ai-audit-skills/issues>
数据边界与隐私说明另见 [references/feedback.md](references/feedback.md)。

### 向用户介绍本功能时——请照下面说（不要省略）

> 这个工具**不会自动往外发任何数据**，代码里也没有我们的服务器地址或密钥。
> 如果你愿意，我可以生成一段**不含任何敏感信息**的统计（发现了几类问题、耗时），
> 由你自己复制走、发到作者的 GitHub Issue。你不发，就没有任何内容离开你的电脑。

### 触发词（任意一种即可）

- 中文：「做匿名反馈」「生成反馈内容」「给作者反馈」
- 英文：`generate feedback`

> 触发词只是「**生成**一段文本」，**不是「发送」**。触发后不要自动发送任何内容——本技能也没有发送能力。

## References

- 字段映射与质量门槛：[references/data-contract.md](references/data-contract.md)
- **真实台账接入（多列金额 / 表头偏移 / 状态列）**：[references/field-mapping-guide.md](references/field-mapping-guide.md)
- 规则、参数与合理解释：[references/rule-catalog.md](references/rule-catalog.md)
- 输出 Schema 与 Agent 解读顺序：[references/output-contract.md](references/output-contract.md)
- 业务实质性声明与深入核查佐证清单：[references/business-substance.md](references/business-substance.md)
