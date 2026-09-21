# Expense output contract

`findings.jsonl` 和 `evidence.jsonl` 使用仓库 `docs/data-contracts.md` 的公共 Schema。`findings.csv` 是便于筛选的扁平视图；JSONL 是权威机器可读输出。

## Agent reading order

1. 读 `run_manifest.json` 确认范围、hash、参数、警告和跳过规则。
2. 读 `data_quality.md`，先判断分析是否足够可靠。
3. 按 `risk_priority`、`evidence_strength` 和主体聚合 `findings.jsonl`。
4. 通过 `evidence_refs` 回到具体源行，不只复述标题。
5. 为每个高优先级组合写合理解释、开放问题、补证清单和复核责任人建议。

`summary.md` 是确定性摘要，不得被当作审计报告。宿主 Agent 可以起草沟通材料，但要保留覆盖范围、限制和人工复核声明。
