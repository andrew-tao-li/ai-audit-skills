# Expense-Audit 文件回归 — 2026-09-17

运行方式：`run_expense_audit.py --input <expenses.csv> --policy <policy.json> --output <new-dir>`，输入为 `evals/fixtures/expense-audit/` 下的合成样例，逐项对照各场景 `expectations.json`。

## clean-control → PASS

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 返回码 | 0 | 0 | ✓ |
| valid_rows | 6 | 6 | ✓ |
| bad_rows | 0 | 0 | ✓ |
| findings | 0 | 0 | ✓ |
| evidence | 0 | 0 | ✓ |
| policy_version | SYNTHETIC-EXPENSE-CLEAN-1.0 | SYNTHETIC-EXPENSE-CLEAN-1.0 | ✓ |

run_id：`EXP-20260917T005232Z-2d6e622d`；network_access=false；skipped_rules 仅 robust-outlier（样本不足）。

## dirty-input → PASS

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 返回码 | 0 | 0 | ✓ |
| valid_rows | 2 | 2 | ✓ |
| bad_rows | 3 | 3 | ✓ |
| findings | 0 | 0 | ✓ |
| required_bad_row_reasons | 3 项 | expense_date 无法解析 / amount 无法解析为有限数值 / employee_id 为空，全部命中 | ✓ |
| defaulted_currency | CNY | DIRTY-002 空币种默认为 CNY | ✓ |

run_id：`EXP-20260917T005232Z-6d0f2cc7`；network_access=false；skipped_rules：policy-threshold、split-expense、weekend-signal、robust-outlier（policy 未提供 limits/approval_thresholds 且 weekend_check=false，符合预期）。

## 结论

2/2 场景 PASS。输出目录：

- `evals/workbuddy-output/file-regression-2026-09-17/clean-control/`
- `evals/workbuddy-output/file-regression-2026-09-17/dirty-input/`
