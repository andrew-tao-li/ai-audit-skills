# Procurement-Fraud + Investigation-Assistant 文件回归 — 2026-09-17

运行方式（全部为本地离线脚本，`network_required: false`）：

```bash
python3 skills/procurement-fraud/scripts/run_procurement_audit.py \
  --input-dir evals/fixtures/procurement-fraud/<scenario> \
  --config    evals/fixtures/procurement-fraud/<scenario>/config.json \
  --output    evals/workbuddy-output/file-regression-2026-09-17/procurement-<scenario>

python3 skills/investigation-assistant/scripts/build_case_workspace.py \
  --input-dir evals/fixtures/investigation-assistant/<scenario> \
  --scope     evals/fixtures/investigation-assistant/<scenario>/scope.json \
  --output    evals/workbuddy-output/file-regression-2026-09-17/investigation-<scenario>
```

为避免覆盖同目录下已有的 expense-audit 回归结果（`clean-control/`、`dirty-input/`），本次输出使用带前缀的新子目录。

**总体结论：4/4 场景 PASS。** 整包校验 `evals/validate_pack.py` → `status: pass`，`errors: []`；两个 skill 单元测试分别为 5/5 与 6/6 通过。

---

## 1. procurement-fraud / clean-control → PASS

run_id：`PROC-20260917T073922Z-d468b3fb`；脚本 `run_procurement_audit.py` sha256 `d08f4a93…c49aea`（与 manifest 记录一致）。

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 返回码 | 0 | 0 | PASS |
| findings（零误报） | 0 | 0 | PASS |
| bad_rows | 0 | 0（`bad_rows.csv` 仅表头） | PASS |
| handoff 状态 | not_recommended | not_recommended | PASS |
| loaded_tables | vendors / purchase_orders / employees / payments / bids | 5 张全部 `loaded`，`skipped_modules: []` | PASS |

补充：evidence 8 条，全部是 PO 行的中性引用证据（`po_id` / `total_amount`），不含任何红旗类型；`findings.csv` 无数据行，`relationship_graph.json` 只有 4 条 `purchased_from` 正常边。

## 2. procurement-fraud / dirty-input → PASS

run_id：`PROC-20260917T073927Z-9dd20bd0`。

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 返回码 | 0 | 0 | PASS |
| findings（零误报） | 0 | 0 | PASS |
| bad_rows | 3 | 3 | PASS |
| valid_rows | vendors 1 / purchase_orders 1 | vendors 1 / purchase_orders 1 | PASS |
| 未提供表 | employees / payments / bids | 三张均 `not_provided`，并写入 `skipped_modules` | PASS |
| required_bad_row_reasons | 3 项 | 全部命中 | PASS |
| handoff 状态 | not_recommended | not_recommended | PASS |

bad rows 明细（`source_row` 为源文件行号，保留 `raw_record` 原文可回源）：

| 表 | 源文件:行 | 原因 |
|---|---|---|
| vendors | vendors.csv:3 | `vendor_id 为空` |
| purchase_orders | purchase_orders.csv:3 | `unit_price 无法解析`（`bad-number`） |
| purchase_orders | purchase_orders.csv:4 | `buyer_id 为空` |

可选表缺失按契约处理：`data_quality.md` 记录 `employees/payments/bids 模块：未提供输入`，另有 `split-order：未提供 approval_thresholds`（dirty config 未给阈值），均属预期跳过而非静默忽略。

## 3. investigation-assistant / scope-filter → PASS

run_id：`INV-20260917T073933Z-7a8ef81a`；`scope_file.sha256` = `7a8ef81a…6f7`，与磁盘上 `scope-filter/scope.json` 实际哈希一致；脚本 `build_case_workspace.py` sha256 `ed110ec1…794ce` 与 manifest 一致。

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 返回码 | 0 | 0 | PASS |
| raw_files（登记原件） | 3 | 3（complaint.txt / messages.csv / logs.csv） | PASS |
| timeline_rows | 0 | 0（`timeline.csv` 仅表头） | PASS |
| out_of_scope_rows | 4 | 4 | PASS |
| findings（零误报） | 0 | 0（`findings.jsonl` 为空，sha256 = 空文件哈希 `e3b0c442…`） | PASS |
| issue_rows | 1 | 1（`ISSUE-SCOPE-001`） | PASS |
| issue_status | open | open | PASS |

**Scope 排除（4 行全部单列，未静默使用）**：输入共 4 条结构化记录，恰好全部越界。

| 源文件:行 | 排除原因 | evidence_id |
|---|---|---|
| messages.csv:2 | 人员超出 `persons_in_scope`（E999） | EV-000005 |
| messages.csv:3 | 时间超出 scope `date_range`（2026-07-01） | EV-000006 |
| logs.csv:2 | 人员超出 `persons_in_scope`（E999） | EV-000007 |
| logs.csv:3 | 时间超出 scope `date_range`（2026-07-02） | EV-000008 |

**raw hash 与只读副本**：`evidence/raw/` 下 3 个副本 SHA-256 与源文件逐一相等（`5e4c7929…`、`d2987a3e…`、`91e2cbd3…`），且权限为 `-r--r--r--`。`chain_of_custody.jsonl` 共 16 条，覆盖每个文件的 `registered` + `copied_and_verified`（带 `protection: read-only`）以及 10 条 `derived` 派生事件。`out_of_scope_rows.csv` 引用的 EV-000005…8 均存在于 `evidence.jsonl`，无悬空引用。

**只读输入**：4 个输入 fixture 的 mtime 全部保持 `2026-09-17 08:46:10`（早于本次 15:39 运行），源文件未被改写。

## 4. investigation-assistant / authorization-denied → PASS

| 检查项 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 返回码 | 2 | 2 | PASS |
| 错误信息含 `authorization_confirmed` | 是 | `ERROR: authorization_confirmed 必须明确为 true` | PASS |
| output_must_not_exist | true | 输出目录不存在 | PASS |
| 拒绝发生在产出之前 | 是 | 见下 | PASS |

**拒绝先于产出**已独立验证：运行前手动确认目标目录不存在，运行后仍不存在；`find . -newermt "-60 minutes"` 在目标输出目录之外无任何新增或改动文件；`authorization-denied/` fixture 目录保持只有 `expectations.json` 和 `scope.json`（scope 中引用的 `placeholder.txt` 也未被读取或创建）。即：未登记证据、未复制原件、未生成任何 workspace 文件。

---

## 结论

| 场景 | 结果 |
|---|---|
| procurement-fraud / clean-control | PASS |
| procurement-fraud / dirty-input | PASS |
| investigation-assistant / scope-filter | PASS |
| investigation-assistant / authorization-denied | PASS |

4/4 PASS。零误报、bad rows 计数与原因、缺失可选表记录、scope 越界单列、raw 副本哈希一致与只读保护、未授权时先拒绝后产出，全部符合各场景 `expectations.json`。

输出目录：

- `evals/workbuddy-output/file-regression-2026-09-17/procurement-clean-control/`
- `evals/workbuddy-output/file-regression-2026-09-17/procurement-dirty-input/`
- `evals/workbuddy-output/file-regression-2026-09-17/investigation-scope-filter/`
- `evals/workbuddy-output/file-regression-2026-09-17/investigation-authorization-denied/`（按预期不存在）

无脚本改动，故未触发 pack 内其他回归基线更新。
