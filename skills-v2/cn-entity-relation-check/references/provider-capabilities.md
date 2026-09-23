# Provider 能力与优先级（provider-capabilities）

## 按能力找工具，不按固定函数名找工具

例如理解为「找到一个能查询中国企业股东的结构化工具」，而不是写死 `qcc_get_shareholders()`。

## 标准能力表

```json
{
  "structured_company_data": false,
  "company_entity_resolution": false,
  "company_shareholders": false,
  "company_key_people": false,
  "company_investments": false,
  "company_controller": false,
  "company_history": false,
  "person_resolution": false,
  "person_related_companies": false,
  "shortest_path": false,
  "web_search": false
}
```

## 数据源优先级

1. P0：当前宿主已授权的结构化企业数据 Connector / MCP
2. P1：企查查 MCP / CLI
3. P2：天眼查开放 API（公司—公司 shortest_path）
4. P3：启信宝等合法结构化企业数据
5. P4：国家企业信用信息等官方公开来源
6. P5：公开 Web Search

「已连接的数据源」通常应优先于「理论上更好但需要重新注册」的数据源。

## 天眼查的 Native Shortest Path

公司—公司场景，若检测到用户已配置 Token，优先用 `shortest_path(company_a, company_b)`。V0.1 只启用工商强关系（法人、任职、投资、分支），不把诉讼/客户/供应商/债务/担保/竞合当作「工商关联」。
