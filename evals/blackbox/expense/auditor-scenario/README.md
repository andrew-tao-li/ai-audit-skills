# 审计师场景（行级 ground truth）

真实审计师提供了一份「带标准答案」的出差费用数据（`出差费用模拟数据.xlsx`），
其「审计说明」工作表明确植入了 **16 个异常场景**及对应费用编号。

本目录把它收编进案例库，用于**行级覆盖率**度量（比 `score_blackbox.py` 的
finding_type 级更严格——它精确到「哪个费用编号被哪个规则命中」）。

## 文件

| 文件 | 说明 |
|---|---|
| `data.csv` | 828 行，规范化英文表头（含 `origin_city`/`dest_city`） |
| `ground-truth.json` | 16 场景标准答案（费用编号 → 期望 finding_type → rule_status） |
| `audit_config.json` | 启用 config 驱动规则（limits/审批阈值/大额阈值/低层级关键词/as_of_date + 新规则参数） |
| `score_coverage.py` | 行级覆盖率评分器 |

## 运行

```bash
python3 evals/blackbox/expense/auditor-scenario/score_coverage.py
```

## 当前结果（2026-09-24，v0.2.1 后）

**16/16 场景检出**。

| 类别 | 结果 |
|---|---|
| 已实现规则 | 7/7 ✅ |
| 配置驱动规则 | 4/4 ✅（含修复后的 missing-expense-type） |
| 数据质量 | 1/1 ✅ |
| 未实现规则 | 0（三条新规则已补齐） |

## 这份数据逼出的改动（已落地）

1. **修 bug**：`missing-expense-type` 的「最严格上限」`max()` → `min()`。
2. **新增 `space-time-conflict`**：同员工同日在多城定位型消费。
3. **新增 `cross-period`**：提交距发生 > N 月。
4. **新增 `high-frequency-small-amount`**：同员工短期 ≥N 笔同类型小额。

三条新规则已各配 1 个 golden fixture（`13/14/15_*.json`），纳入黑盒回归。

## 两个已知边界（如实记录）

1. **space-time-conflict 会额外命中 7 组**（`#3/#4` 之外）：如 E014 同日长沙+西安各一套
   酒店+餐饮。这 7 组同样是「同日两城」的物理不可能模式，只是审计师未编入 16 场景索引。
   规则按审计定义工作，属**额外暴露的真实异常**，非误报。
2. **high-frequency-small-amount 的阈值是可调的**：默认 `min_count=10` 会额外命中
   E020 的 11 笔餐费（边界信号）。可通过 `high_frequency_min_count` 收紧，或作为复核线索保留。

## 与 score_blackbox.py 的关系

本目录**独立**于 `score_blackbox.py`（后者跑 25 个 fixture，F1 100%）。它是一次性的
「外部盲测基准」，既是后续「补规则/修 bug」的前后对比基线，也是未来接收真实审计师
带答案数据时可复用的模板。
