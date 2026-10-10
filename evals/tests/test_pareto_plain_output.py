#!/usr/bin/env python3
"""帕累托守卫：**没碰到新场景的人，产出里不应出现任何新功能的痕迹。**

用户反复强调的原则：
> "前面用得很丝滑、没遇到异常的人，使用时丝毫感觉不到我们的变动；而恰好命中新增场景的人，
>  能明显感觉到提升。"

这条原则很容易在后续迭代里被悄悄破坏（多一行提示、多一个文件、多一条 skipped 都会被用户看到）。
所以把它变成**自动化测试**：用**完全普通**的输入（自带样例 + 无任何新开关/新输入），断言

  1. 产出文件清单**不变**（没有多出任何"可选文件"）；
  2. `summary.md` + `data_quality.md` 里**不出现**任何新功能关键词；
  3. `run_manifest.json` 的 `skipped_rules` / `warnings` 里没有新功能条目。

只要有人给普通场景加了可见信息，这里就会红。
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
EXAMPLE = SKILL / "examples" / "input" / "expenses.csv"
POLICY = SKILL / "examples" / "input" / "policy.json"

# 普通场景下**原件**就产出的文件（多一个都算破坏帕累托）
BASELINE_FILES = sorted([
    "bad_rows.csv", "clean_expenses.csv", "dashboard.html", "data_quality.md",
    "evidence.jsonl", "findings.csv", "findings.jsonl", "run_manifest.json", "summary.md",
])

# 新增能力的"痕迹词"：普通场景一个都不该出现
NEW_TRACES = [
    "行程/单据真实性", "travel-verification", "周几", "weekday", "差标", "row_limit", "row-limit",
    "单价合理性", "unit-price", "price-reference", "替票", "invoice-payee", "payments",
    "ticket-number-reused", "itinerary-segment", "lodging", "住宿凭证", "suppressed_findings",
    "allowlist", "multi_occurrence", "fixed_amount", "outlier_min_amount", "vendor-concentration",
    "split-expense-cross-merchant", "large-amount", "voucher-incomplete",
]


class ParetoPlainOutputTest(unittest.TestCase):
    def test_plain_run_has_no_new_feature_traces(self):
        with tempfile.TemporaryDirectory(prefix="pareto-plain-") as td:
            out = Path(td) / "out"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--input", str(EXAMPLE), "--policy", str(POLICY), "--output", str(out)],
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

            # ③ skipped_rules / warnings 里没有新功能条目
            manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
            manifest_text = json.dumps(manifest, ensure_ascii=False)
            for kw in ("travel-verification", "weekday", "row-limit", "unit-price", "invoice-payee",
                       "allowlist", "multi_occurrence", "fixed_amount"):
                self.assertNotIn(kw, manifest_text, "普通场景的 manifest 不该出现新功能条目：%r" % kw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
