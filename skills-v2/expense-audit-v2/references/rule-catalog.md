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


