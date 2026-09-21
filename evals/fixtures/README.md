# 文件化回归测试夹具

本目录只包含合成教学数据，不包含真实员工、供应商、案件或凭证信息。

每个 skill 至少覆盖三种用途：

| Skill | 场景 | 主要验证点 |
| --- | --- | --- |
| expense-audit | 原 skill `examples/input` | 多类红旗正向检出、证据引用、1 条坏行隔离 |
| expense-audit | `clean-control` | 中文字段别名可以识别；正常工作日费用不产生 finding |
| expense-audit | `dirty-input` | 无效日期、金额和缺失主键被隔离；有效行仍继续处理 |
| procurement-fraud | 原 skill `examples/input` | 10 类采购红旗、白名单、关系图和调查移交 |
| procurement-fraud | `clean-control` | 五类表都可处理；正常采购、付款和投标不产生 finding |
| procurement-fraud | `dirty-input` | 必需表中的坏行被隔离；未提供的可选表被明确记录为 not_provided |
| investigation-assistant | 原 skill `examples/input` | 哈希、只读副本、时间线、反证、范围过滤和引用完整性 |
| investigation-assistant | `scope-filter` | 全部结构化记录超出人员或日期范围时，时间线为空且记录排除原因 |
| investigation-assistant | `authorization-denied` | 未明确授权时，在创建输出目录前安全停止 |

各场景的 `expectations.json` 是机器可核对的预期，不是自然语言提示。运行：

```bash
python3 -m unittest discover -s evals/tests -v
```
