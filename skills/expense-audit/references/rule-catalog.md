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
