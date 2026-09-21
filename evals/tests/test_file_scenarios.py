import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PACK_ROOT / "evals" / "fixtures"
EXPENSE_SCRIPT = PACK_ROOT / "skills" / "expense-audit" / "scripts" / "run_expense_audit.py"
PROCUREMENT_SCRIPT = PACK_ROOT / "skills" / "procurement-fraud" / "scripts" / "run_procurement_audit.py"
INVESTIGATION_SCRIPT = PACK_ROOT / "skills" / "investigation-assistant" / "scripts" / "build_case_workspace.py"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ExpenseFileScenarioTest(unittest.TestCase):
    def run_scenario(self, name):
        fixture = FIXTURES / "expense-audit" / name
        expected = json.loads((fixture / "expectations.json").read_text(encoding="utf-8"))
        temporary = tempfile.TemporaryDirectory()
        output = Path(temporary.name) / "output"
        completed = subprocess.run(
            [
                sys.executable,
                str(EXPENSE_SCRIPT),
                "--input",
                str(fixture / "expenses.csv"),
                "--policy",
                str(fixture / "policy.json"),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, expected["expected_return_code"], completed.stderr)
        return temporary, output, expected

    def test_clean_control_accepts_chinese_headers_without_false_findings(self):
        temporary, output, expected = self.run_scenario("clean-control")
        try:
            self.assertEqual(len(read_csv(output / "clean_expenses.csv")), expected["expected_valid_rows"])
            self.assertEqual(len(read_csv(output / "bad_rows.csv")), expected["expected_bad_rows"])
            self.assertEqual(len(read_jsonl(output / "findings.jsonl")), expected["expected_findings"])
            self.assertEqual(len(read_jsonl(output / "evidence.jsonl")), expected["expected_evidence"])
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["field_mapping"]["expense_id"], "费用编号")
            self.assertEqual(manifest["field_mapping"]["amount"], "报销金额")
            self.assertEqual(manifest["parameters"]["policy_version"], expected["required_policy_version"])
        finally:
            temporary.cleanup()

    def test_dirty_input_quarantines_bad_rows_and_keeps_valid_rows(self):
        temporary, output, expected = self.run_scenario("dirty-input")
        try:
            clean = read_csv(output / "clean_expenses.csv")
            bad = read_csv(output / "bad_rows.csv")
            self.assertEqual(len(clean), expected["expected_valid_rows"])
            self.assertEqual(len(bad), expected["expected_bad_rows"])
            self.assertEqual(len(read_jsonl(output / "findings.jsonl")), expected["expected_findings"])
            self.assertEqual(clean[1]["currency"], expected["expected_defaulted_currency"])
            rendered_reasons = "\n".join(row["reasons"] for row in bad)
            for required in expected["required_bad_row_reasons"]:
                self.assertIn(required, rendered_reasons)
            self.assertNotIn("DIRTY-003", {row["expense_id"] for row in clean})
            self.assertNotIn("DIRTY-004", {row["expense_id"] for row in clean})
        finally:
            temporary.cleanup()


class ProcurementFileScenarioTest(unittest.TestCase):
    def run_scenario(self, name):
        fixture = FIXTURES / "procurement-fraud" / name
        expected = json.loads((fixture / "expectations.json").read_text(encoding="utf-8"))
        temporary = tempfile.TemporaryDirectory()
        output = Path(temporary.name) / "output"
        completed = subprocess.run(
            [
                sys.executable,
                str(PROCUREMENT_SCRIPT),
                "--input-dir",
                str(fixture),
                "--config",
                str(fixture / "config.json"),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, expected["expected_return_code"], completed.stderr)
        return temporary, output, expected

    def test_clean_control_runs_all_tables_without_false_findings(self):
        temporary, output, expected = self.run_scenario("clean-control")
        try:
            self.assertEqual(len(read_jsonl(output / "findings.jsonl")), expected["expected_findings"])
            self.assertEqual(len(read_csv(output / "bad_rows.csv")), expected["expected_bad_rows"])
            handoff = json.loads((output / "investigation_handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["status"], expected["expected_handoff_status"])
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            loaded = {item["table"] for item in manifest["input_files"] if item.get("table") != "config"}
            self.assertEqual(loaded, set(expected["expected_loaded_tables"]))
            self.assertEqual(manifest["skipped_modules"], [])
        finally:
            temporary.cleanup()

    def test_dirty_input_quarantines_three_rows_and_marks_optional_tables_missing(self):
        temporary, output, expected = self.run_scenario("dirty-input")
        try:
            self.assertEqual(len(read_jsonl(output / "findings.jsonl")), expected["expected_findings"])
            bad = read_csv(output / "bad_rows.csv")
            self.assertEqual(len(bad), expected["expected_bad_rows"])
            rendered_reasons = "\n".join(row["reasons"] for row in bad)
            for required in expected["required_bad_row_reasons"]:
                self.assertIn(required, rendered_reasons)
            for table, count in expected["expected_valid_rows"].items():
                self.assertEqual(len(read_csv(output / ("normalized_%s.csv" % table))), count)
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            for table in expected["expected_not_provided_tables"]:
                self.assertIn(table + " 模块：未提供输入", manifest["skipped_modules"])
                self.assertFalse((output / ("normalized_%s.csv" % table)).exists())
            handoff = json.loads((output / "investigation_handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["status"], expected["expected_handoff_status"])
        finally:
            temporary.cleanup()


class InvestigationFileScenarioTest(unittest.TestCase):
    def test_scope_filter_excludes_all_structured_rows_and_preserves_raw_files(self):
        fixture = FIXTURES / "investigation-assistant" / "scope-filter"
        expected = json.loads((fixture / "expectations.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(INVESTIGATION_SCRIPT),
                    "--input-dir",
                    str(fixture),
                    "--scope",
                    str(fixture / "scope.json"),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, expected["expected_return_code"], completed.stderr)
            self.assertEqual(len(read_csv(output / "timeline.csv")), expected["expected_timeline_rows"])
            self.assertEqual(len(read_csv(output / "out_of_scope_rows.csv")), expected["expected_out_of_scope_rows"])
            self.assertEqual(len(read_jsonl(output / "findings.jsonl")), expected["expected_findings"])
            matrix = read_csv(output / "evidence_matrix.csv")
            self.assertEqual(len(matrix), expected["expected_issue_rows"])
            self.assertEqual(matrix[0]["status"], expected["expected_issue_status"])
            inventory = read_jsonl(output / "evidence_inventory.jsonl")
            self.assertEqual(len(inventory), expected["expected_raw_files"])
            for item in inventory:
                source = fixture / item["relative_path"]
                raw_copy = output / "evidence" / "raw" / item["relative_path"]
                self.assertEqual(sha256(source), sha256(raw_copy))
                self.assertEqual(raw_copy.stat().st_mode & 0o222, 0)

    def test_authorization_denied_stops_before_output_creation(self):
        fixture = FIXTURES / "investigation-assistant" / "authorization-denied"
        expected = json.loads((fixture / "expectations.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(INVESTIGATION_SCRIPT),
                    "--input-dir",
                    str(fixture),
                    "--scope",
                    str(fixture / "scope.json"),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, expected["expected_return_code"])
            self.assertIn(expected["expected_error_contains"], completed.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
