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


