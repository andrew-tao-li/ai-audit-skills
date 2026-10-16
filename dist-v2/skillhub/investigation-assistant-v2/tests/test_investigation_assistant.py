import csv
import hashlib
import json
import os
import shutil
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
            # 版本取自本 skill 的 manifest.json，避免每次发版都要改测试字面量
            expected_version = json.loads((SKILL_ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
            self.assertEqual(manifest["skill_version"], expected_version)
            self.assertEqual(manifest["case_id"], "CASE-SYNTHETIC-001")
            self.assertEqual(manifest["scope"]["persons_in_scope"], ["E001", "E002"])
        finally:
            temp.cleanup()


class InvestigationOptionalSwitchesTest(unittest.TestCase):
    """v0.2.7：三个可选开关必须「配了才生效、不配就一字不变」。

    这些用例同时锁死：
      · 开关关闭 → 表头与 0.2.6 一致（与 evals 的帕累托守卫互为双保险）
      · 开关打开 → 新列如期出现且取值正确
      · hypothesis_extended → **至少生成一条真正挑战核心命题的反方假设**
    """

    def _run(self, extra_scope=None, extra_input=None):
        import json as _json
        import tempfile
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        input_dir = root / "input"
        shutil.copytree(INPUT, input_dir)
        scope = _json.loads((input_dir / "scope.json").read_text(encoding="utf-8"))
        if extra_scope:
            scope.update(extra_scope)
        (input_dir / "scope.json").write_text(_json.dumps(scope, ensure_ascii=False, indent=2), encoding="utf-8")

        notes = []
        if extra_input == "observed_at":
            # 给消息表加一列"记录时间"，验证双时间列只在有该列时才出现
            path = input_dir / "messages.csv"
            lines = path.read_text(encoding="utf-8-sig").splitlines()
            header = lines[0].rstrip(",") + ",recorded_at"
            body = [row.rstrip(",") + ",2026-07-02T09:00:00Z" for row in lines[1:]]
            path.write_text("\n".join([header] + body) + "\n", encoding="utf-8")
            notes.append("已在 messages.csv 增加 recorded_at 列")

        out = root / "out"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--input-dir", str(input_dir),
             "--scope", str(input_dir / "scope.json"), "--output", str(out)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return temp, completed, out

    def test_switches_off_keeps_original_headers(self):
        """不配开关 → 三个 CSV 表头与 0.2.6 完全一致。"""
        temp, completed, out = self._run()
        try:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(self._header(out, "evidence_matrix.csv")[:7], (
                "issue_id", "allegation_or_issue", "supporting_evidence_refs", "contradictory_evidence_refs",
                "missing_evidence", "alternative_explanations", "status"))
            self.assertEqual(len(self._header(out, "evidence_matrix.csv")), 7)
            self.assertEqual(len(self._header(out, "hypothesis_register.csv")), 9)
            self.assertEqual(len(self._header(out, "timeline.csv")), 8)
        finally:
            temp.cleanup()

    def test_evidence_tiers_adds_column_and_flags_non_hard(self):
        """开 evidence_tiers → 增列；来源被标 LEAD 时 finding 提示"不能独立支撑认定"。"""
        temp, completed, out = self._run(extra_scope={"evidence_tiers": {"messages.csv": "LEAD", "logs.csv": "HARD"}})
        try:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            header = self._header(out, "evidence_matrix.csv")
            self.assertIn("evidence_tier", header)
            rows = self._rows(out, "evidence_matrix.csv")
            self.assertTrue(rows, "示例应至少有一个 issue")
            self.assertIn(rows[0]["evidence_tier"], ("HARD", "SOFT", "LEAD", "UNSPECIFIED"))
            findings = [json.loads(line) for line in (out / "findings.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            joined = " ".join(" ".join(f.get("open_questions", [])) for f in findings)
            if rows[0]["evidence_tier"] != "HARD":
                self.assertIn("不能独立支撑认定", joined, "非 HARD 证据必须给出提示")
        finally:
            temp.cleanup()

    def test_bad_tier_value_is_rejected(self):
        """evidence_tiers 取值非法 → 直接报错（与"未知键拒绝"同一套防呆）。"""
        temp, completed, out = self._run(extra_scope={"evidence_tiers": {"messages.csv": "VERY_STRONG"}})
        try:
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("evidence_tiers", completed.stderr + completed.stdout)
        finally:
            temp.cleanup()

    def test_deduplicate_sources_counts_independent_files(self):
        temp, completed, out = self._run(extra_scope={"deduplicate_sources": True})
        try:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            header = self._header(out, "evidence_matrix.csv")
            self.assertIn("independent_source_count", header)
            rows = self._rows(out, "evidence_matrix.csv")
            self.assertTrue(all(r["independent_source_count"].isdigit() for r in rows))
        finally:
            temp.cleanup()

    def test_observed_at_only_when_input_provides_it(self):
        """双时间列：输入没有记录时间列时不出现；有了才出现。"""
        temp, completed, out = self._run()
        try:
            self.assertNotIn("observed_at", self._header(out, "timeline.csv"))
        finally:
            temp.cleanup()
        temp, completed, out = self._run(extra_input="observed_at")
        try:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            header = self._header(out, "timeline.csv")
            self.assertIn("observed_at", header)
            self.assertEqual(header[0], "timestamp")
            self.assertEqual(header[1], "observed_at")
        finally:
            temp.cleanup()

    def test_hypothesis_extended_generates_a_counter_hypothesis(self):
        """开 hypothesis_extended → **至少一条真正挑战核心命题的假设**，且带反驳条件两列。"""
        temp, completed, out = self._run(extra_scope={
            "hypothesis_extended": True,
            "issues": [{
                "issue_id": "ISSUE-001",
                "allegation_or_issue": "被举报人是否在未经授权的情况下将项目资料发给外部",
                "keywords": ["资料", "外部"],
                "contradictory_keywords": ["经批准"],
                "alternative_explanations": ["资料本属公开信息，不存在未授权外发"],
                "refutation_criteria": ["若确有授权邮件，则该指控不成立"],
                "discriminating_evidence": ["OA 授权记录 / 邮件往来"],
                "priority": "high",
            }],
        })
        try:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            header = self._header(out, "hypothesis_register.csv")
            self.assertIn("refutation_criteria", header)
            self.assertIn("discriminating_evidence", header)
            rows = self._rows(out, "hypothesis_register.csv")
            self.assertGreaterEqual(len(rows), 2, "除指控本身外，至少还要有一条反方假设行")
            allegations = [r["hypothesis"] for r in rows]
            self.assertTrue(
                any("公开信息" in value for value in allegations),
                "反方假设必须来自 alternative_explanations：%s" % allegations)
            counter = [r for r in rows if "公开信息" in r["hypothesis"]][0]
            self.assertIn("授权邮件", counter["refutation_criteria"], "反驳条件应被登记到反方假设行")
            self.assertIn("OA 授权记录", counter["discriminating_evidence"], "区分性证据应被登记")
        finally:
            temp.cleanup()

    @staticmethod
    def _header(out: Path, name: str):
        line = (out / name).read_text(encoding="utf-8-sig").splitlines()[0]
        return tuple(line.split(","))

    def _rows(self, out: Path, name: str):
        import csv as _csv
        with (out / name).open(encoding="utf-8-sig", newline="") as handle:
            return list(_csv.DictReader(handle))


class CounterLike(dict):
    def __init__(self, values):
        super().__init__()
        for value in values:
            self[value] = self.get(value, 0) + 1


if __name__ == "__main__":
    unittest.main()
