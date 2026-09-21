import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "build_case_workspace.py"
INPUT = SKILL_ROOT / "examples" / "input"
SCOPE = INPUT / "scope.json"
EXPECTED = SKILL_ROOT / "examples" / "expected" / "expectations.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class InvestigationAssistantEndToEndTest(unittest.TestCase):
    def run_example(self, scope=SCOPE):
        temp = tempfile.TemporaryDirectory()
        output = Path(temp.name) / "out"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--input-dir", str(INPUT), "--scope", str(scope), "--output", str(output)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return temp, output

    def test_raw_copies_match_source_hashes_and_custody_is_logged(self):
        temp, output = self.run_example()
        try:
            scope = json.loads(SCOPE.read_text(encoding="utf-8"))
            for relative in scope["allowed_sources"]:
                raw_copy = output / "evidence" / "raw" / relative
                self.assertEqual(sha256(INPUT / relative), sha256(raw_copy))
                self.assertEqual(raw_copy.stat().st_mode & 0o222, 0)
            custody = read_jsonl(output / "chain_of_custody.jsonl")
            events = CounterLike(item["event"] for item in custody)
            self.assertEqual(events["registered"], 3)
            self.assertEqual(events["copied_and_verified"], 3)
            self.assertGreater(events["derived"], 0)
            self.assertTrue(all(item.get("protection") == "read-only" for item in custody if item["event"] == "copied_and_verified"))
        finally:
            temp.cleanup()

    def test_scope_filter_excludes_out_of_scope_people_and_dates(self):
        temp, output = self.run_example()
        try:
            expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
            timeline = read_csv(output / "timeline.csv")
            excluded = read_csv(output / "out_of_scope_rows.csv")
            self.assertEqual(len(timeline), expected["timeline_rows"])
            self.assertEqual(len(excluded), expected["out_of_scope_rows"])
            rendered = json.dumps(timeline, ensure_ascii=False)
            self.assertNotIn("E999", rendered)
            self.assertNotIn("old_file.pdf", rendered)
            self.assertEqual([row["timestamp"] for row in timeline], sorted(row["timestamp"] for row in timeline))
        finally:
            temp.cleanup()

    def test_matrix_registers_both_supporting_and_contradictory_candidates(self):
        temp, output = self.run_example()
        try:
            matrix = read_csv(output / "evidence_matrix.csv")
            self.assertEqual(len(matrix), 1)
            self.assertTrue(matrix[0]["supporting_evidence_refs"])
            self.assertTrue(matrix[0]["contradictory_evidence_refs"])
            hypothesis = read_csv(output / "hypothesis_register.csv")[0]
            self.assertEqual(hypothesis["status"], "open")
            self.assertTrue(hypothesis["alternative_explanations"])
        finally:
            temp.cleanup()

    def test_all_cross_references_exist_and_no_final_judgment_is_generated(self):
        temp, output = self.run_example()
        try:
            evidence_ids = {item["evidence_id"] for item in read_jsonl(output / "evidence.jsonl")}
            findings = read_jsonl(output / "findings.jsonl")
            self.assertEqual(len(findings), 1)
            for finding in findings:
                self.assertTrue(finding["human_review_required"])
                self.assertTrue(set(finding["evidence_refs"]).issubset(evidence_ids))
                self.assertNotIn("judgment", finding)
                self.assertTrue(finding["facts"])
                self.assertTrue(finding["inferences"])
                self.assertTrue(finding["hypotheses"])
            memo = (output / "case_memo_template.md").read_text(encoding="utf-8")
            self.assertIn("仅由有权人员", memo)
            self.assertNotIn("责任认定：", memo)
        finally:
            temp.cleanup()

    def test_scope_gate_rejects_unconfirmed_authorization_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            bad_scope = Path(directory) / "scope.json"
            scope = json.loads(SCOPE.read_text(encoding="utf-8"))
            scope["authorization_confirmed"] = False
            bad_scope.write_text(json.dumps(scope, ensure_ascii=False), encoding="utf-8")
            output = Path(directory) / "out"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--input-dir", str(INPUT), "--scope", str(bad_scope), "--output", str(output)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"}
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("authorization_confirmed", completed.stderr)
            self.assertFalse(output.exists())

    def test_manifest_is_offline_and_scope_is_recorded(self):
        temp, output = self.run_example()
        try:
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["network_access"])
            self.assertEqual(manifest["skill_version"], "0.2.0")
            self.assertEqual(manifest["case_id"], "CASE-SYNTHETIC-001")
            self.assertEqual(manifest["scope"]["persons_in_scope"], ["E001", "E002"])
        finally:
            temp.cleanup()


class CounterLike(dict):
    def __init__(self, values):
        super().__init__()
        for value in values:
            self[value] = self.get(value, 0) + 1


if __name__ == "__main__":
    unittest.main()
