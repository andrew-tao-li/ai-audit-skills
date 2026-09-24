import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "run_expense_audit.py"
EXAMPLE = SKILL_ROOT / "examples" / "input" / "expenses.csv"
POLICY = SKILL_ROOT / "examples" / "input" / "policy.json"
EXPECTED = SKILL_ROOT / "examples" / "expected" / "expectations.json"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ExpenseAuditEndToEndTest(unittest.TestCase):
    def run_example(self, input_path=EXAMPLE):
        temp = tempfile.TemporaryDirectory()
        output = Path(temp.name) / "out"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--input", str(input_path), "--policy", str(POLICY), "--output", str(output)],
            capture_output=True, text=True, encoding="utf-8"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return temp, output

    def test_fixture_finds_injected_patterns_and_keeps_evidence_traceable(self):
        temp, output = self.run_example()
        try:
            findings = read_jsonl(output / "findings.jsonl")
            evidence = read_jsonl(output / "evidence.jsonl")
            expectations = json.loads(EXPECTED.read_text(encoding="utf-8"))
            finding_types = {item["finding_type"] for item in findings}
            self.assertTrue(set(expectations["must_include_finding_types"]).issubset(finding_types))
            evidence_ids = {item["evidence_id"] for item in evidence}
            for finding in findings:
                self.assertTrue(finding["human_review_required"])
                self.assertTrue(finding["evidence_refs"])
                self.assertTrue(set(finding["evidence_refs"]).issubset(evidence_ids))
                self.assertNotIn("judgment", finding)
            with (output / "bad_rows.csv").open(encoding="utf-8-sig", newline="") as handle:
                bad_rows = list(csv.DictReader(handle))
            self.assertEqual(len(bad_rows), expectations["must_have_bad_rows"])
        finally:
            temp.cleanup()

    def test_reasonable_weekend_cases_remain_weak_low_priority_signals(self):
        temp, output = self.run_example()
        try:
            weekend = [f for f in read_jsonl(output / "findings.jsonl") if f["finding_type"] == "weekend-signal"]
            self.assertGreaterEqual(len(weekend), 1)
            self.assertTrue(all(f["risk_priority"] == "low" for f in weekend))
            self.assertTrue(all(f["evidence_strength"] == "weak" for f in weekend))
            joined = json.dumps(weekend, ensure_ascii=False)
            self.assertIn("值班", joined)
            self.assertNotIn("舞弊成立", joined)
        finally:
            temp.cleanup()

    def test_manifest_records_offline_run_and_parameters(self):
        temp, output = self.run_example()
        try:
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["network_access"])
            self.assertEqual(manifest["skill"], "expense-audit-v2")
            self.assertEqual(manifest["skill_version"], "0.2.1")
            self.assertEqual(manifest["parameters"]["policy_version"], "SYNTHETIC-EXPENSE-POLICY-1.0")
            self.assertTrue(manifest["input_files"][0]["sha256"])
        finally:
            temp.cleanup()

    def test_xlsx_input_when_openpyxl_is_available(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl not installed")
        with tempfile.TemporaryDirectory() as directory:
            xlsx = Path(directory) / "expenses.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "费用明细"
            with EXAMPLE.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.reader(handle):
                    sheet.append(row)
            workbook.save(xlsx)
            temp, output = self.run_example(xlsx)
            try:
                manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["input_files"][0]["sheet"], "费用明细")
            finally:
                temp.cleanup()


if __name__ == "__main__":
    unittest.main()
