import csv
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "run_trigger_eval.py"


class TriggerEvalHarnessTest(unittest.TestCase):
    def test_init_creates_balanced_120_case_sheet(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "codex.csv"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "init", "--host", "Codex", "--host-version", "test", "--output", str(output)],
                capture_output=True, text=True, encoding="utf-8"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 120)
            counts = Counter((row["skill"], row["expected_trigger"]) for row in rows)
            for skill in ("expense-audit-v2", "procurement-fraud-v2", "investigation-assistant-v2"):
                self.assertEqual(counts[(skill, "true")], 20)
                self.assertEqual(counts[(skill, "false")], 20)
            self.assertTrue(all(row["observed_skill"] == "" for row in rows))

    def test_score_excludes_blanks_and_builds_confusion_matrix(self):
        rows = [
            ["T1", "expense-audit-v2", "true", "p1", "Codex", "test", "expense-audit-v2", "true", "true", "true", ""],
            ["T2", "expense-audit-v2", "false", "p2", "Codex", "test", "none", "false", "false", "true", ""],
            ["T3", "procurement-fraud-v2", "true", "p3", "Codex", "test", "none", "false", "false", "true", ""],
            ["T4", "procurement-fraud-v2", "false", "p4", "Codex", "test", "procurement-fraud-v2", "true", "false", "true", ""],
            ["T5", "investigation-assistant-v2", "true", "p5", "Codex", "test", "", "", "", "", ""],
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "results.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("case_id", "skill", "expected_trigger", "prompt", "host", "host_version", "observed_skill", "skill_loaded", "script_run", "overclaim_free", "notes"))
                writer.writerows(rows)
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "score", "--input", str(source)],
                capture_output=True, text=True, encoding="utf-8"
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["tested_rows"], 4)
            self.assertEqual(result["incomplete_rows"], 1)
            self.assertEqual(result["per_skill"]["expense-audit-v2"]["accuracy"], 1.0)
            self.assertEqual(result["per_skill"]["procurement-fraud-v2"]["accuracy"], 0.0)
            self.assertFalse(result["complete"])


if __name__ == "__main__":
    unittest.main()
