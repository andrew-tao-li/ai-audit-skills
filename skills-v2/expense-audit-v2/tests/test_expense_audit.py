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
            # 版本取自本 skill 的 manifest.json，避免每次发版都要改测试字面量
            expected_version = json.loads((SKILL_ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
            self.assertEqual(manifest["skill_version"], expected_version)
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


    def test_status_filter_and_resubmit_rule_are_opt_in(self):
        """v0.2.8：状态过滤与新规则必须「默认不影响旧行为，配置后才生效」。"""
        csv_text = (
            "单据号,工号,费用类型,发生日期,提交日期,金额,商户,审批状态\n"
            "E1,EMP1,差旅,2025-03-01,2025-03-02,500,酒店A,已撤回\n"
            "E2,EMP1,差旅,2025-03-01,2025-03-05,800,酒店A,已同意\n"
            "E3,EMP2,餐饮,2025-03-03,2025-03-03,200,餐厅B,已同意\n"
            "E4,EMP2,餐饮,2025-03-03,2025-03-03,200,餐厅B,已撤回\n"
        )

        def run(data, policy=None, out=None):
            cmd = [sys.executable, str(SCRIPT), "--input", str(data), "--output", str(out)]
            if policy:
                cmd += ["--policy", str(policy)]
            completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return [json.loads(l)["finding_type"]
                    for l in (out / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "expenses.csv"
            data.write_text(csv_text, encoding="utf-8")

            # ① 不配置 status_filter（= 旧行为）：撤回行照样参与 → 出现假重复，且没有新规则
            naive = Path(td) / "naive"
            types = run(data, None, naive)
            self.assertIn("exact-duplicate-employee-date-amount", types)
            self.assertNotIn("resubmit-after-rejection-amount-increase", types)
            self.assertFalse((naive / "excluded_by_status.csv").exists())

            # ② 配置 status_filter：假重复消失，新规则出现，被排除行单独落盘（不静默丢弃）
            policy = Path(td) / "policy.json"
            policy.write_text(json.dumps({"policy_version": "T", "default_currency": "CNY",
                                          "status_filter": {"include": ["已同意"]}}), encoding="utf-8")
            filtered = Path(td) / "filtered"
            types = run(data, policy, filtered)
            self.assertNotIn("exact-duplicate-employee-date-amount", types)
            self.assertIn("resubmit-after-rejection-amount-increase", types)
            self.assertIn("已撤回", (filtered / "excluded_by_status.csv").read_text(encoding="utf-8"))

            # ③ 反例：撤回后重提但金额未增加 → 不应触发新规则
            data2 = Path(td) / "no_increase.csv"
            data2.write_text(csv_text.replace(",2025-03-05,800,", ",2025-03-05,500,"), encoding="utf-8")
            types = run(data2, policy, Path(td) / "out2")
            self.assertNotIn("resubmit-after-rejection-amount-increase", types)


if __name__ == "__main__":
    unittest.main()
