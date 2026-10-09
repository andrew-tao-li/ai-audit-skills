import csv
import importlib.util
import json
import os
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"}
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
            completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
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


    def test_travel_cross_check_is_opt_in(self):
        """v0.2.9：不给辅助数据 → 行为不变；给了出差申请/打卡 → 自动唤醒交叉核验。"""
        base = ("单据号,工号,费用类型,发生日期,提交日期,金额,商户,目的城市\n"
                "E1,EMP1,差旅,2025-04-01,2025-04-02,800,酒店,北京\n"
                "E2,EMP2,差旅,2025-04-03,2025-04-03,900,酒店,北京\n"
                "E3,EMP3,差旅,2025-04-05,2025-04-05,700,酒店,北京\n"
                "E4,EMP4,差旅,2025-04-07,2025-04-07,600,酒店,北京\n")
        travel = ("工号,姓名,出差开始日期,出差结束日期,目的城市\n"
                  "EMP2,张三,2025-04-03,2025-04-03,北京\n"
                  "EMP3,李四,2025-04-05,2025-04-05,北京\n"
                  "EMP4,王五,2025-04-07,2025-04-07,北京\n"
                  "EMP5,赵六,2025-04-01,2025-04-01,广州\n")
        attendance = ("工号,日期,打卡地点,是否在公司\n"
                      "EMP2,2025-04-03,上海总部,是\n"
                      "EMP3,2025-04-05,广州市天河区,否\n"
                      "EMP4,2025-04-07,北京市朝阳区,否\n")
        policy = {"policy_version": "T", "default_currency": "CNY",
                  "travel_cross_check": {"company_cities": ["上海"], "company_location_keywords": ["上海", "总部"],
                                         "travel_types": ["差旅", "住宿", "机票"]}}
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "e.csv"; data.write_text(base, encoding="utf-8")
            trv = Path(td) / "t.csv"; trv.write_text(travel, encoding="utf-8")
            att = Path(td) / "a.csv"; att.write_text(attendance, encoding="utf-8")
            pol = Path(td) / "p.json"; pol.write_text(json.dumps(policy), encoding="utf-8")

            def types(extra, out):
                cmd = [sys.executable, str(SCRIPT), "--input", str(data), "--policy", str(pol), "--output", str(out)] + extra
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 0, r.stderr)
                return [json.loads(l)["finding_type"]
                        for l in (out / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

            # ① 不给辅助数据 → 一条都不触发（等价于旧行为）
            t0 = types([], Path(td) / "o0")
            for ft in ("expense-without-travel-request", "office-swipe-on-offsite-claim", "attendance-city-mismatch"):
                self.assertNotIn(ft, t0)

            # ② 给了辅助数据 → 自动唤醒；且合理情形不误报（E4 有申请+当地打卡，应为 0）
            t1 = types(["--travel-requests", str(trv), "--attendance", str(att)], Path(td) / "o1")
            self.assertIn("expense-without-travel-request", t1)   # E1：无出差申请
            self.assertIn("office-swipe-on-offsite-claim", t1)    # E2：当天公司打卡
            self.assertIn("attendance-city-mismatch", t1)         # E3：打卡地与出差地不同城
            self.assertEqual(len(t1), 3)                          # E4 不应误报

    # ── v0.2.13（来自真实审计师反馈第 1、4 条）───────────────────────────────
    def test_chinese_date_formats_are_parsed(self):
        """中文日期「2026年10月09日 12:30」必须能识别——旧版识别不了，会当成坏行。"""
        spec = importlib.util.spec_from_file_location("expense_audit_mod", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cases = {
            "2026年10月09日 12:30": "2026-10-09",
            "2026年10月9日": "2026-10-09",
            "2026年10月09日12:30": "2026-10-09",
            "20261009": "2026-10-09",
            "2026-10-09T12:30": "2026-10-09",
            "不是日期": None,
            "2026年13月40日": None,
        }
        for raw, want in cases.items():
            self.assertEqual(mod.parse_date(raw), want, "解析 %r" % raw)

        csv_text = ("单据号,工号,金额,发生日期\n"
                    "E1,EMP1,100,2026年10月09日 12:30\n"
                    "E2,EMP1,200,2026年10月9日\n")
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "cn.csv"; data.write_text(csv_text, encoding="utf-8")
            out = Path(td) / "out"
            r = subprocess.run([sys.executable, str(SCRIPT), "--input", str(data), "--output", str(out)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(r.returncode, 0, r.stderr)
            bad = [l for l in (out / "bad_rows.csv").read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(bad) - 1, 0, "中文日期不应进坏行：%s" % bad)

    def test_self_approval_accepts_name_and_hints_on_mismatch(self):
        """报销人可用姓名；口径不一致时必须提示，不得静默漏检。"""
        def run_csv(csv_text, out):
            with tempfile.TemporaryDirectory() as td:
                data = Path(td) / "e.csv"; data.write_text(csv_text, encoding="utf-8")
                o = Path(out)
                r = subprocess.run([sys.executable, str(SCRIPT), "--input", str(data), "--output", str(o)],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 0, r.stderr)
                types = [json.loads(l)["finding_type"]
                         for l in (o / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
                manifest = json.loads((o / "run_manifest.json").read_text(encoding="utf-8"))
                return types, manifest.get("skipped_rules", [])

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # ① 只有姓名、没有工号：应能运行，且姓名命中 → 自审自批
            types, _ = run_csv("单据号,姓名,金额,发生日期,审批人\nB1,张三,100,2026-10-09,张三\n", base / "n")
            self.assertIn("self-approval", types)
            # ② 报销人是工号、审批人是姓名 → 不得静默漏检，必须提示口径不一致
            types, skipped = run_csv("单据号,工号,金额,发生日期,审批人\nA1,E001,100,2026-10-09,张三\n", base / "m")
            self.assertNotIn("self-approval", types)
            self.assertTrue(any("口径" in s for s in skipped), "应提示口径不一致：%s" % skipped)
            # ③ 工号 + 姓名都有、审批人是姓名 → 命中
            types, _ = run_csv("单据号,工号,姓名,金额,发生日期,审批人\nC1,E001,张三,100,2026-10-09,张三\n", base / "b")
            self.assertIn("self-approval", types)


if __name__ == "__main__":
    unittest.main()
