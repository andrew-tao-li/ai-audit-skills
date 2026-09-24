# 审计师场景（行级 ground truth）

真实审计师提供了一份「带标准答案」的出差费用数据（`出差费用模拟数据.xlsx`），
其「审计说明」工作表明确植入了 **16 个异常场景**及对应费用编号。

本目录把它收编进案例库，用于**行级覆盖率**度量（比 `score_blackbox.py` 的
finding_type 级更严格——它精确到「哪个费用编号被哪个规则命中」）。

## 文件

| 文件 | 说明 |
|---|---|
| `data.csv` | 828 行，规范化英文表头（含 `origin_city`/`dest_city` 供未来时空规则用） |
| `ground-truth.json` | 16 场景标准答案（费用编号 → 期望 finding_type → rule_status） |
| `audit_config.json` | 启用 config 驱动规则（limits/审批阈值/大额阈值/低层级关键词/as_of_date） |
| `score_coverage.py` | 行级覆盖率评分器 |

## 运行

```bash
python3 evals/blackbox/expense/auditor-scenario/score_coverage.py
```

## 当前结果（2026-09-24）

**11/16 场景检出**（配完整 config 后）。

| 类别 | 结果 |
|---|---|
| 已实现规则 | 7/7 检出 ✅ |
| 配置驱动规则 | 3/4 检出（split-expense / large-amount-low-level / future-date ✅；missing-expense-type ❌ 见下） |
| 数据质量 | 1/1 处理 ✅（EXP-0802 隔离、EXP-0803 被 outlier 命中） |
| 未实现规则 | 4 个必漏 → 新规则目标 |

## 从这份数据里挖出的发现

### 发现 1：`missing-expense-type` 规则有 bug（max 应为 min）

`run_expense_audit.py` 第 753 行，计算「最严格上限」时用了 `max()`：

```python
strictest_max = max(...)  # 应为 min()
```

「最严格上限」= 各限额里**最小的** max_amount（越小越严），却取了最大。
- 单限额时 `max == min`，不暴露（所以老 fixture `11_missing_expense_type` 测不出来）；
- 多限额时（如 hotel 700 / meal 200 / taxi 150）就会漏报。

已实证：单限额 100 时 missing-expense-type 能命中 EXP-0827，多限额时漏掉。

### 发现 2：三个新规则需求（真实盲点）

| 场景 | 建议新规则 | 依赖字段 |
|---|---|---|
| #3/#4 同日异城 | `space-time-conflict` | `origin_city` / `dest_city`（数据已有） |
| #16 跨期入账 | `cross-period` | `expense_date` vs `submit_date` 间隔 > N 月 |
| #14 频繁小额套现 | `high-frequency-small-amount` | 同员工短窗口内 N 笔小额 |

> 注：`#14` 当前已被 `near-duplicate` 大簇间接覆盖，但缺少「模式识别」级专用规则；
> `#3/#4/#16` 目前**完全未检出**。

## 与 score_blackbox.py 的关系

本目录**独立**于 `score_blackbox.py`（后者仍只跑 22 个既有 fixture，F1 不变）。
它是一次性的「外部盲测基准」：量化我们在这份真实数据上的召回，并作为后续
「补规则 / 修 bug」的前后对比基线。
