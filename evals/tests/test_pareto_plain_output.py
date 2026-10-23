#!/usr/bin/env python3
"""帕累托守卫：**没碰到新场景的人，产出里不应出现任何新功能的痕迹。**

用户反复强调的原则：
> "前面用得很丝滑、没遇到异常的人，使用时丝毫感觉不到我们的变动；而恰好命中新增场景的人，
>  能明显感觉到提升。"

这条原则很容易在后续迭代里被悄悄破坏（多一行提示、多一个文件、多一条 skipped 都会被用户看到）。

> **v0.2.31 起**：本用例不再依赖包内示例（示例现在**故意**含航班/住宿日期等字段，用来演示条件提示），
> 而是在临时目录里构造一份**最小的「普通台账」**（无航班、无住宿、无差标列），断言：
>
>   1. 产出文件清单**不变**；
>   2. `summary.md` + `data_quality.md` 里**不出现**任何新功能关键词；
>   3. `run_manifest.json` 里没有新功能条目。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills-v2" / "expense-audit-v2"
SCRIPT = SKILL / "scripts" / "run_expense_audit.py"

# 普通场景下**原件**就产出的文件（多一个都算破坏帕累托）
# v0.2.37：dashboard 文件名带数据源 → 本用例的输入固定为 plain.csv，故固定为 dashboard-plain.html
BASELINE_FILES = sorted([
    "bad_rows.csv", "clean_expenses.csv", "dashboard-plain.html", "data_quality.md",
    "evidence.jsonl", "findings.csv", "findings.jsonl", "run_manifest.json", "summary.md",
])

# 新增能力的"痕迹词"：普通场景一个都不该出现
NEW_TRACES = [
    "行程/单据真实性", "travel-verification", "周几", "weekday", "差标", "row_limit", "row-limit",
    "单价合理性", "unit-price", "price-reference", "替票", "invoice-payee", "payments",
    "ticket-number-reused", "itinerary-segment", "lodging", "住宿凭证", "suppressed_findings",
    "allowlist", "multi_occurrence", "fixed_amount", "outlier_min_amount", "vendor-concentration",
    "split-expense-cross-merchant", "large-amount", "voucher-incomplete",
    # v0.2.33：时间级规则——普通台账（无具体时间）不许出现
    "checkout-before-transport", "segment-overlap",
]

# 最小「普通台账」：不含航班/住宿/差标等任何新场景字段；日期全为工作日
PLAIN_CSV = """expense_id,employee_id,department,expense_type,expense_date,submit_date,amount,currency,vendor_name,invoice_number,project_code,approver,business_purpose
E-001,E01,销售,meal,2026-06-01,2026-06-02,120,CNY,餐厅A,INV-A1,P1,A1,客户餐
E-002,E01,交通,transport,2026-06-03,2026-06-03,60,CNY,出租A,TAX-A1,P1,A1,市内交通
E-003,E02,研发,meal,2026-06-04,2026-06-04,80,CNY,餐厅B,INV-B1,P2,A2,加班餐
E-004,E02,采购,office,2026-06-05,2026-06-05,150,CNY,文具B,OFF-B1,P2,A2,办公用品
E-005,E03,研发,meal,2026-06-08,2026-06-08,95,CNY,餐厅B,INV-B2,P2,A2,加班餐
E-006,E03,交通,transport,2026-06-09,2026-06-09,45,CNY,出租A,TAX-A2,P2,A2,市内交通
"""

PLAIN_POLICY = {
    "policy_version": "PLAIN-1.0",
    "default_currency": "CNY",
    "limits": [{"rule_id": "OFFICE-CAP", "expense_type": "office", "currency": "CNY", "max_amount": 1000}],
    "approval_thresholds": [{"rule_id": "GENERAL-APPROVAL", "currency": "CNY", "amount": 900}],
    "split_window_days": 3,
    "near_duplicate_window_days": 7,
    "near_duplicate_amount_tolerance": 0.02,
    "weekend_check": True,
}


class ParetoPlainOutputTest(unittest.TestCase):
    def test_plain_run_has_no_new_feature_traces(self):
        with tempfile.TemporaryDirectory(prefix="pareto-plain-") as td:
            root = Path(td)
            data = root / "plain.csv"
            policy = root / "policy.json"
            data.write_text(PLAIN_CSV, encoding="utf-8")
            policy.write_text(json.dumps(PLAIN_POLICY, ensure_ascii=False, indent=2), encoding="utf-8")
            out = root / "out"

            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(data), "--policy", str(policy), "--output", str(out)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            # ① 产出文件清单不变
            actual_files = sorted(p.name for p in out.iterdir())
            self.assertEqual(actual_files, BASELINE_FILES,
                             "普通场景的产出文件清单变了（多/少了文件）：%s" % actual_files)

            # ② 面向用户的文本里没有新功能痕迹
            blob = "\n".join([
                (out / "summary.md").read_text(encoding="utf-8"),
                (out / "data_quality.md").read_text(encoding="utf-8"),
            ])
            for kw in NEW_TRACES:
                self.assertNotIn(kw, blob, "普通场景不该出现新功能痕迹：%r" % kw)

            # ③ manifest 里没有新功能条目
            manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
            manifest_text = json.dumps(manifest, ensure_ascii=False)
            for kw in ("travel-verification", "weekday", "row-limit", "unit-price", "invoice-payee",
                       "allowlist", "multi_occurrence", "fixed_amount"):
                self.assertNotIn(kw, manifest_text, "普通场景的 manifest 不该出现新功能条目：%r" % kw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
