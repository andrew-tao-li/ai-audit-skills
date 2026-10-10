# Expense rule catalog v0.1.0

## Exact duplicate

- 相同非空发票号 + 相同币种 + 相同金额：强证据。
- 相同员工 + 发生日期 + 币种 + 金额：中等证据；可能是同日多笔合理消费，必须核对商户和凭证。

每组只形成一条 finding，并引用组内全部源行。冲销、退款、重提和发票拆分是常见替代解释。

## Near duplicate

同员工、同归一化商户、同币种，在配置天数内金额差异不超过配置比例，且未被 exact duplicate 覆盖。它只表示 `possible near duplicate`。默认窗口 7 天、金额差异 2%，均写入 manifest。

## Policy threshold

只读取 policy 的 `limits`。每项可按 `expense_type`、`currency` 匹配 `max_amount`。没有适用条款就跳过，不能使用行业“常识金额”。输出要保留 `rule_id` 和制度说明。

## Split expense

以同员工、同商户、同币种为组，在滚动窗口内检查多笔均低于审批阈值但合计超过阈值。阈值来自 `approval_thresholds`；还要检查是否为分期结算、多人费用、合同约定或不同业务目的。

## Weekend signal

仅在 `weekend_check=true` 时生成低优先级、弱证据 finding。周末真实出差、值班和跨时区是合理解释；不得单独升级为高风险。

## Robust outlier

按 `expense_type + currency` 建 peer group；组太小时回退到 currency。使用 median 与 MAD，`robust_z = 0.6745 * (x - median) / MAD`。默认最小组 5、阈值 3.5，只报告正向高额离群。MAD 为零则跳过该组并记录。

## Risk scale

规则提供可解释积分，优先级由分数映射：1 为 low，2–3 为 medium，4–5 为 high，6 以上为 critical。证据强度独立判断，不能写“舞弊概率”。

## 审批状态过滤（v0.2.8，可选）

真实报销台账几乎都有「审批状态」列（如 `已同意 / 已撤回 / 已拒绝`）。**默认不做任何过滤**——与旧版逐字节一致。
在 `policy.json` 里配置后才生效：

```json
{ "status_filter": { "include": ["已同意"], "exclude": ["已撤回", "已拒绝"] } }
```

- `include` 非空时**只分析**所列状态；`exclude` 用于排除。二者可只用其一。
- 被排除的行**不参与任何规则**，但会单独写入 `excluded_by_status.csv`（**绝不静默丢弃**）。
- **状态为空的行一律保留**——不猜、不藏。
- 字段别名：`status / approval_status / state / 状态 / 审批状态 / 单据状态 / 报销状态 / 流程状态 / 审批结果`。

> 为什么需要它：真实数据里，一笔被撤回/拒绝后重新提交的费用，会让「同员工同日同金额」这类规则产生大量假阳性
> （实测某真实台账 47 条发现里 39 条属此类）。过滤状态后，噪声消失，真正值得看的信号才会浮出来。

## 撤回/拒绝后重提且金额增加（v0.2.8）

仅在**配置了 `status_filter` 且存在被排除行**时才会触发（因此对旧数据零影响）。`resubmit_window_days: 0` 可关闭。

判定：同一员工 + 同一费用类型 + 同一商户，先有一条被撤回/拒绝的记录，其后 `resubmit_window_days`（默认 90）天内
又有一条被采纳的记录，且**金额增加**。输出两次提交的金额、间隔天数与状态，供人工核对是「正常修正」还是「先试小额、通过后加码」。

## 出差交叉核验（v0.2.9，可选）

需要 `--travel-requests` / `--attendance` 提供辅助数据（任一份即可），提供后自动启用：

| 规则 | 需要的输入 | 说明 |
|---|---|---|
| `expense-without-travel-request` | 出差申请 | 差旅类报销的日期不在该员工任何出差申请区间内（`date_tolerance_days` 容差） |
| `office-swipe-on-offsite-claim` | 打卡 | 报销称外地，但当天有**公司打卡**（可能是代报销，需核实实际出差人） |
| `attendance-city-mismatch` | 打卡（+出差申请） | 打卡地点所在城市与报销的出差城市不一致（地点识别不出城市则跳过） |
| （出差期间缺卡） | 出差申请+打卡+开关 | 仅当 `require_swipe_during_travel: true` 时核对 |

**「是否在公司」三层判定**：① 显式布尔 → ② 经纬度+半径（`company_locations`，默认 1000m）→ ③ 地点文本（`company_location_keywords`）；三层都不成立则标「未知」并跳过。

**「差旅类报销」的认定**：`expense_type` 命中 `travel_types`（默认 差旅/住宿/机票/火车/市内交通/补贴…）**或** `dest_city` 存在且不在 `company_cities` 内。

配置示例：

```json
{
  "travel_cross_check": {
    "company_cities": ["上海"],
    "company_locations": [{"name": "上海总部", "lat": 31.23, "lon": 121.47, "radius_m": 1000}],
    "company_location_keywords": ["上海", "总部"],
    "travel_types": ["差旅", "住宿", "机票", "火车", "市内交通"],
    "date_tolerance_days": 1,
    "flag_city_mismatch": true,
    "require_swipe_during_travel": false,
    "min_swipes_per_travel_day": 2
  }
}
```

> **默认口径**：出差申请可替代打卡。若公司要求出差期间也打卡，设 `require_swipe_during_travel: true`。

## 跨商户拆单（v0.2.13，可选，默认关闭）

`split_cross_merchant: true` 时启用。与「拆单报销」同一目的，但**不要求同一商户**：

- 分组：同一**员工** + 同一**币种**（不再含商户）；
- 条件：窗口内 **≥2 个不同商户**，每笔金额低于 `approval_thresholds` 的阈值，**合计超过**阈值；
- 输出：`split-expense-cross-merchant`。

> 为什么默认关闭：跨商户一起加总会引入较多正常消费（同一段时间的多笔独立支出），需要按公司实际口径开启。

## 绝对大额（v0.2.13，可选，默认关闭）

`large_amount_check: true` + `large_amount_threshold` 时启用 → `large-amount`。

- 适用：公司**没有制度额度/审批阈值**，但仍想按"绝对金额"确定复核优先级。
- 与 `large-amount-low-level-approval` **自动去重**（已被后者覆盖的行不再重复报）。
- 与 `robust-outlier` 的区别：后者是**同类内的相对离群**（需要同类样本 ≥ `outlier_min_group_size`）；前者是**绝对金额**。

> **想让"异常高额"跑出来，至少要有下面之一**：① `policy_thresholds`（制度上限）② `large_amount_threshold` + `low_level_approver_keywords` ③ `large_amount_check` ④ 同类样本足够多（相对离群）。

## 商户集中度（v0.2.13，可选，默认关闭）

`vendor_concentration_check: true` 时启用 → `vendor-concentration`。

- 口径：`vendor_concentration_scope`（`employee` 默认 / `department`）；
- 条件：该员工/部门在该商户的笔数 ≥ `vendor_concentration_min_count`（默认 5）**且** 占比 ≥ `vendor_concentration_share`（默认 0.6）；
- 定位：**关系/串通风险的复核线索**（如回扣、指定供应商），不是结论。

## 白名单（v0.2.13，可选输入 `--allowlist`）

见 SKILL.md「可选白名单」。要点：**只压制"整条告警的每一行都命中"**；被压制内容写入 `suppressed_findings.csv`，**绝不静默丢弃**。

## 外部行程核验（v0.2.15，可选输入 `--travel-verification`）

把**外部查到的航班记录**与报销单比对。**技能本身不联网**，核验数据由使用者/宿主提供。

| 规则 | 触发 |
|---|---|
| `travel-verification-mismatch` | 外部记录与报销单的**航班号/日期/方向/乘机人**任一不符（强） |
| `travel-verification-not-found` | 在**给定来源中**查不到该行程（**弱**，且明文声明"不等于虚构"） |

> 取得方式、来源可靠性与合规提醒见 [travel-verification-guide.md](travel-verification-guide.md)。

## 同一凭证多人各报（v0.2.15，可选，默认关闭）

`shared_voucher_check: true` → `shared-voucher-multiple-employees`（强）：

同一 `pnr`（订座号）被**多名员工**各自报销。典型场景：国际机票同行合并开票、却各自按全额报销。
表里没有 `pnr` 列时自动跳过。

## 凭证要素完备性（v0.2.15，可选，默认关闭）

`voucher_completeness_check: true` → `voucher-incomplete`（弱）：

统计并列出**缺发票号 / 缺发票日期**的记录。定位是**合规/入账效力**问题，**不直接等于虚假**，仅提示补凭证。

## 凭证内部一致性（v0.2.16，可选，默认关闭，**完全离线**）

`voucher_consistency_check: true` 时启用——**不联网**，抓"假票/伪行程单常见的自相矛盾"：

| 规则 | 触发 | 强度 |
|---|---|---|
| `ticket-number-reused` | 同一**票号**在台账里重复出现 | 强 |
| `ticket-issue-after-flight` | **出票日期晚于**行程/费用日期 | 中 |
| `itinerary-segment-conflict` | 同一**订座号（PNR）**同一天出现多个不同航段 | 中 |

> 与「外部行程核验」互补：**内部一致性（离线）+ 外部存在性（由使用者取数）** 一起用，证据更稳。
> 需要字段别名 `ticket_number` / `issue_date` / `pnr` / `flight_no`；缺列自动跳过。

## 住宿凭证交叉核验（v0.2.18，可选，默认关闭，**完全离线**）

`lodging_cross_check: true` 时启用——来自真实国际差旅审计的三个模式：

| 规则 | 触发 | 强度 |
|---|---|---|
| `consecutive-nightly-invoicing` | 同一员工**连续逐晚单独开票**（≥ `lodging_min_nights`，默认 3） | 中 |
| `same-amount-no-invoice` | 同一员工 + 同一商户、**金额完全相同且均无发票号**（≥ `lodging_same_amount_min_count`，默认 3） | 中 |
| `lodging-night-mismatch` | 凭证写的**晚数** ≠ 入离店日期算出的晚数 | 中 |

> 典型用途：识别"把一笔住宿拆成很多晚、每笔都低于审批阈值"，以及"同一次住宿被重复计费"。
> 字段别名：`check_in` / `check_out` / `nights` / `room_number`；`lodging_types` 可覆盖住宿类关键词。

## 开票方 ↔ 实际收款方（v0.2.20，可选输入 `--payments`，**离线**）

把支付/收款记录与报销单上的**开票方/发票抬头**比对：**不一致 → `invoice-payee-mismatch`（强）**。

- 输入列：`expense_id`（必填）、`payee`（实际收款方，必填）、`invoice_issuer`（开票方，可选，缺省用报销单的 `vendor_name`）、`amount`（可选）。
- 意义：**发票抬头与实际收款方分裂**是"替票/虚开"的典型信号，**即使发票本身为真**。
- 默认不参与：不提供 `--payments` 就完全不产生任何 finding。

## 日期 ↔ 周几一致性（v0.2.20，可选，默认关闭，**完全离线**）

`weekday_check: true` 且台账含 `weekday` 列时 → `weekday-mismatch`（中）。

- 篡改/编造日期时"周几"常与真实日期对不上，是**原件级防伪线索**。
- 支持 `周一 / 星期一 / 礼拜一 / 周1 / Monday / Thu`；无法判断的值自动跳过。
- 台账不含该列 → 完全不参与；含该列但未开启 → 只在 `data_quality.md` 给一条提示。

## 单价合理性（v0.2.21，可选输入 `--price-reference`，**离线**）

把报销单的**单价**与**使用者提供的市场价格参考**比对：超过参考上限 × (1 + `price_tolerance`，默认 0.30）
→ `unit-price-above-market`（中）。

- 价格参考列：`item` / `unit` / `max_price`（或 `unit_price`）/ `source`；报销单可含 `item` / `unit` / `unit_price`
  （缺 `unit_price` 时用 `amount`）。
- **需要外部数据**：**只在用户/提示词提到"单价合理性 / 市场价"时才提示用户提供**（见 SKILL.md「Operating principles」第 7 条）；
  **没提到就一个字都不提**。
- **不提供该文件 → 完全不参与**（与旧版逐字节一致）。

## 按行差标 / 限额（v0.2.22，可选，默认关闭，**完全离线**）

`row_limit_check: true` 且台账含 `row_limit`（差标/限额/标准）列时 → `row-limit-exceeded`（强）。

- 比对口径：有 `unit_price`（或由 `amount`/`nights` **自动派生**）就用**间夜单价**，否则用金额。
- `row_limit_tolerance` 默认 `0.0`（严格）。
- 用途：酒店差标**按城市分档、逐行给出**的情形（**不能**塞进单一全局 `limits`）。
- 台账不含该列 → 完全不参与；含列未开启 → 只在 `data_quality.md` 给一条提示。

## 间夜单价派生（v0.2.22，**自动**）

台账有 `nights` 但没 `unit_price` 时，自动 `unit_price = amount / nights`——让多晚订单按**间夜单价**比对。

## 精度旋钮（v0.2.23，**可选，默认不改变行为**）

针对真实**外勤销售**数据里的结构性噪声（固定标准补贴、同日两段同价路桥费、小额被叫"异常高额"）：

| 字段 | 作用 | 默认 |
|---|---|---|
| `outlier_min_amount` | 低于此金额不报「异常高额」 | `0` |
| `fixed_amount_types` | 固定标准值类型 → 不参与「异常高额」「金额近似」 | `[]` |
| `multi_occurrence_types` | 天然可多次发生的类型 → 同日同额/金额近似不报 | `[]` |

- 跳过量写入 `data_quality.md`（不静默丢弃）。
- 黄金集 `26_field_sales_precision` 守住这组精度（开/关旋钮各 1 条对照断言）。


