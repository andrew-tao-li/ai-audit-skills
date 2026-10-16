"""帕累托守卫（调查技能）：**没有任何新配置时，产出里不得出现任何新功能痕迹**。

与 expense 的 `test_pareto_plain_output.py` 同一思路。这里守的是 investigation-assistant-v2
v0.2.7 新增的三个可选开关与双时间列——它们的默认值必须让产出与 0.2.6 完全一致：

  · timeline.csv          → 固定 8 列（不得出现 observed_at）
  · evidence_matrix.csv   → 固定 7 列（不得出现 evidence_tier / independent_source_count）
  · hypothesis_register.csv → 固定 9 列（不得出现 refutation_criteria / discriminating_evidence）

只要有一个字节或一列表头变了，这个测试就会红——这是「改功能不许动旧产出」的硬闸门。
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills-v2" / "investigation-assistant-v2"
SCRIPT = SKILL / "scripts" / "build_case_workspace.py"
EXAMPLE_INPUT = SKILL / "examples" / "input"
EXAMPLE_SCOPE = EXAMPLE_INPUT / "scope.json"

TIMELINE_COLUMNS = ("timestamp", "actor", "event_type", "object", "source_file", "source_row", "evidence_id", "confidence")
MATRIX_COLUMNS = ("issue_id", "allegation_or_issue", "supporting_evidence_refs", "contradictory_evidence_refs",
                  "missing_evidence", "alternative_explanations", "status")
HYPOTHESIS_COLUMNS = ("hypothesis_id", "issue_id", "hypothesis", "supporting_evidence_refs",
                      "contradictory_evidence_refs", "missing_evidence", "alternative_explanations",
                      "next_validation_step", "status")

# 只在**配置了开关**时才允许出现的列名
GATED_COLUMNS = ("observed_at", "evidence_tier", "independent_source_count",
                 "refutation_criteria", "discriminating_evidence")


class ParetoPlainOutputTest(unittest.TestCase):
    def test_default_run_has_no_new_traces(self):
        temp = tempfile.TemporaryDirectory()
        try:
            out = Path(temp.name) / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--input-dir", str(EXAMPLE_INPUT),
                 "--scope", str(EXAMPLE_SCOPE), "--output", str(out)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            def header(name):
                line = (out / name).read_text(encoding="utf-8-sig").splitlines()[0]
                return tuple(line.split(","))

            # 表头必须与 0.2.6 完全一致（顺序也不能变）
            self.assertEqual(header("timeline.csv"), TIMELINE_COLUMNS, "timeline.csv 表头变了")
            self.assertEqual(header("evidence_matrix.csv"), MATRIX_COLUMNS, "evidence_matrix.csv 表头变了")
            self.assertEqual(header("hypothesis_register.csv"), HYPOTHESIS_COLUMNS, "hypothesis_register.csv 表头变了")

            # 新列名不得出现在任何产出里（表头或内容都不行）
            blob = "\n".join(
                p.read_text(encoding="utf-8", errors="ignore")
                for p in sorted(out.rglob("*")) if p.is_file() and p.suffix in (".csv", ".json", ".jsonl", ".md", ".html")
            )
            for column in GATED_COLUMNS:
                self.assertNotIn(column, blob, "未配置开关，产出里却出现了 %s" % column)
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
