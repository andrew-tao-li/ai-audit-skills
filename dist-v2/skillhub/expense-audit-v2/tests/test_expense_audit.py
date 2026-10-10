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

    def _run_with_policy(self, csv_text, policy, out):
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "e.csv"; data.write_text(csv_text, encoding="utf-8")
            cmd = [sys.executable, str(SCRIPT), "--input", str(data), "--output", str(out)]
            if policy is not None:
                pol = Path(td) / "p.json"; pol.write_text(json.dumps(policy), encoding="utf-8")
                cmd += ["--policy", str(pol)]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(r.returncode, 0, r.stderr)
            return {json.loads(l)["finding_type"]
                    for l in (Path(out) / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

    def test_optional_v0213_rules_are_opt_in(self):
        """跨商户拆单 / 绝对大额 / 商户集中度：默认关闭，配置后才生效（帕累托）。"""
        base = Path(tempfile.mkdtemp())
        cm = ("单据号,工号,费用类型,发生日期,金额,商户\n"
              "X1,EMP1,办公,2026-10-09,400,V1\nX2,EMP1,办公,2026-10-09,400,V2\nX3,EMP1,办公,2026-10-09,400,V3\n")
        thr = {"policy_version": "T", "default_currency": "CNY",
               "approval_thresholds": [{"amount": 1000, "currency": "CNY"}], "split_window_days": 0}
        self.assertNotIn("split-expense-cross-merchant", self._run_with_policy(cm, thr, base / "cm_off"))
        self.assertIn("split-expense-cross-merchant",
                      self._run_with_policy(cm, dict(thr, split_cross_merchant=True), base / "cm_on"))

        la = "单据号,工号,费用类型,发生日期,金额\nZ1,EMP1,差旅,2026-10-09,6000\n"
        self.assertNotIn("large-amount", self._run_with_policy(la, {"policy_version": "T", "default_currency": "CNY"}, base / "la_off"))
        self.assertIn("large-amount", self._run_with_policy(
            la, {"policy_version": "T", "default_currency": "CNY", "large_amount_threshold": 5000, "large_amount_check": True}, base / "la_on"))

        vc = ("单据号,工号,费用类型,发生日期,金额,商户\n"
              + "".join("W%d,EMP9,办公,2026-10-%02d,100,集中商户A\n" % (i, i) for i in range(1, 7))
              + "".join("W%d,EMP9,办公,2026-10-%02d,100,其他商户B\n" % (i, i - 6) for i in range(7, 9)))
        self.assertNotIn("vendor-concentration", self._run_with_policy(vc, {"policy_version": "T", "default_currency": "CNY"}, base / "vc_off"))
        self.assertIn("vendor-concentration", self._run_with_policy(
            vc, {"policy_version": "T", "default_currency": "CNY", "vendor_concentration_check": True}, base / "vc_on"))

    def test_allowlist_suppresses_but_records(self):
        """白名单：只移出「全部行都命中」的告警，且完整写进 suppressed_findings.csv（不静默丢弃）。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            data = base / "e.csv"
            data.write_text("单据号,工号,费用类型,发生日期,金额,商户\n"
                            "D1,EMP5,餐饮,2026-10-09,200,餐厅B\nD2,EMP5,餐饮,2026-10-09,200,餐厅B\n", encoding="utf-8")
            # 无白名单：重复告警应在，且没有 suppressed 文件
            o1 = base / "o1"
            self._run_with_policy(data.read_text(encoding="utf-8"), None, o1)
            self.assertIn("exact-duplicate-employee-date-amount",
                          (o1 / "findings.jsonl").read_text(encoding="utf-8"))
            self.assertFalse((o1 / "suppressed_findings.csv").exists())
            # 有白名单：重复告警被移出，但 suppressed_findings.csv 完整留痕
            allow = base / "allow.csv"
            allow.write_text("expense_id,employee_id,vendor_name,invoice_number,expense_type,amount_max,reason\n"
                             ",,餐厅B,,餐饮,500,园区餐厅工作餐\n", encoding="utf-8")
            o2 = base / "o2"
            r = subprocess.run([sys.executable, str(SCRIPT), "--input", str(data), "--output", str(o2), "--allowlist", str(allow)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("exact-duplicate-employee-date-amount", (o2 / "findings.jsonl").read_text(encoding="utf-8"))
            supp = (o2 / "suppressed_findings.csv").read_text(encoding="utf-8")
            self.assertIn("园区餐厅工作餐", supp)

    def test_travel_verification_and_vouchers_are_opt_in(self):
        """v0.2.15：外部行程核验（不联网、文件驱动）与两条可选凭证规则的默认零回归 + 红线。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)

            def run(cmd):
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 0, r.stderr)
                out = Path(cmd[cmd.index("--output") + 1])
                findings = [json.loads(l) for l in (out / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
                return findings

            ledger = base / "m.csv"
            ledger.write_text("单据号,工号,费用类型,发生日期,金额,出发城市,目的城市,航班号\n"
                              "F1,EMP1,机票,2026-10-09,3000,北京,上海,CA1234\n", encoding="utf-8")
            # ① 不提供核验文件 → 零 travel-verification（默认零回归）
            f = run([sys.executable, str(SCRIPT), "--input", str(ledger), "--output", str(base / "o0")])
            self.assertFalse([x for x in f if x["finding_type"].startswith("travel-verification")])
            # ② 方向相反 → mismatch
            rev = base / "v.csv"
            rev.write_text("expense_id,depart_city,arrive_city,source\nF1,上海,北京,航司官网\n", encoding="utf-8")
            f = run([sys.executable, str(SCRIPT), "--input", str(ledger), "--output", str(base / "o1"),
                     "--travel-verification", str(rev)])
            self.assertTrue(any(x["finding_type"] == "travel-verification-mismatch" for x in f))
            # ③ 查不到 → 只报弱信号，且**写明不等于虚构**（红线）
            nf = base / "nf.csv"
            nf.write_text("expense_id,source\nF1,航旅纵横\n", encoding="utf-8")
            f = run([sys.executable, str(SCRIPT), "--input", str(ledger), "--output", str(base / "o2"),
                     "--travel-verification", str(nf)])
            nf_findings = [x for x in f if x["finding_type"] == "travel-verification-not-found"]
            self.assertEqual(len(nf_findings), 1)
            self.assertEqual(nf_findings[0]["evidence_strength"], "weak")
            self.assertIn("不等于", json.dumps(nf_findings[0], ensure_ascii=False))
            # ④ 同一凭证多人：默认关，开启生效
            sh = base / "sh.csv"
            sh.write_text("单据号,工号,费用类型,发生日期,金额,订座号\n"
                          "P1,EMP1,机票,2026-10-09,3000,PNRAAA\nP2,EMP2,机票,2026-10-09,3000,PNRAAA\n", encoding="utf-8")
            self.assertNotIn("shared-voucher-multiple-employees",
                             [x["finding_type"] for x in run([sys.executable, str(SCRIPT), "--input", str(sh), "--output", str(base / "o3")])])
            pol = base / "p.json"; pol.write_text(json.dumps({"policy_version": "T", "default_currency": "CNY", "shared_voucher_check": True}), encoding="utf-8")
            self.assertIn("shared-voucher-multiple-employees",
                          [x["finding_type"] for x in run([sys.executable, str(SCRIPT), "--input", str(sh), "--output", str(base / "o4"), "--policy", str(pol)])])
            # ⑤ 凭证完备性：默认关，开启生效
            self.assertNotIn("voucher-incomplete",
                             [x["finding_type"] for x in run([sys.executable, str(SCRIPT), "--input", str(sh), "--output", str(base / "o5")])])
            pol2 = base / "p2.json"; pol2.write_text(json.dumps({"policy_version": "T", "default_currency": "CNY", "voucher_completeness_check": True}), encoding="utf-8")
            self.assertIn("voucher-incomplete",
                          [x["finding_type"] for x in run([sys.executable, str(SCRIPT), "--input", str(sh), "--output", str(base / "o6"), "--policy", str(pol2)])])

    def test_voucher_consistency_is_offline_and_opt_in(self):
        """v0.2.16：凭证内部一致性（**完全离线**）——默认关闭，开启后三条规则生效。"""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            data = base / "d.csv"
            data.write_text("单据号,工号,费用类型,发生日期,金额,票号,出票日期,订座号,出发城市,目的城市\n"
                            "T1,EMP1,机票,2026-09-10,3000,9991234567890,2026-09-12,PXA,北京,上海\n"
                            "T2,EMP2,机票,2026-09-11,3000,9991234567890,2026-09-01,PXB,广州,成都\n"
                            "T3,EMP1,机票,2026-09-20,2000,9999999999999,2026-09-01,PYC,北京,上海\n"
                            "T4,EMP1,机票,2026-09-20,2100,9998888888888,2026-09-02,PYC,上海,北京\n", encoding="utf-8")

            def types(cmd):
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 0, r.stderr)
                out = Path(cmd[cmd.index("--output") + 1])
                return {json.loads(l)["finding_type"]
                        for l in (out / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

            rule_ids = ("ticket-number-reused", "ticket-issue-after-flight", "itinerary-segment-conflict")
            off = types([sys.executable, str(SCRIPT), "--input", str(data), "--output", str(base / "off")])
            for rid in rule_ids:
                self.assertNotIn(rid, off)
            pol = base / "p.json"
            pol.write_text(json.dumps({"policy_version": "T", "default_currency": "CNY", "voucher_consistency_check": True}), encoding="utf-8")
            on = types([sys.executable, str(SCRIPT), "--input", str(data), "--output", str(base / "on"), "--policy", str(pol)])
            for rid in rule_ids:
                self.assertIn(rid, on)

    def test_flight_hint_only_when_flight_data_present(self):
        """v0.2.17：只有台账含航班/订座号信息时才在报告里提示「去哪查」；不含则不打扰。"""
        def summary_of(csv_text, verif=None, out=None):
            with tempfile.TemporaryDirectory() as td:
                data = Path(td) / "e.csv"; data.write_text(csv_text, encoding="utf-8")
                cmd = [sys.executable, str(SCRIPT), "--input", str(data), "--output", str(out)]
                if verif:
                    vp = Path(td) / "v.csv"; vp.write_text(verif, encoding="utf-8")
                    cmd += ["--travel-verification", str(vp)]
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                self.assertEqual(r.returncode, 0, r.stderr)
                return (Path(out) / "summary.md").read_text(encoding="utf-8")

        base = Path(tempfile.mkdtemp())
        noflight = "单据号,工号,费用类型,发生日期,金额,商户\nA1,E1,餐饮,2026-10-09,100,餐厅\n"
        withflight = "单据号,工号,费用类型,发生日期,金额,航班号,订座号\nB1,E1,机票,2026-10-09,3000,CA1234,PNRAAA\n"
        self.assertNotIn("行程/单据真实性", summary_of(noflight, None, base / "o1"))
        self.assertIn("行程/单据真实性", summary_of(withflight, None, base / "o2"))
        self.assertNotIn("行程/单据真实性", summary_of(
            withflight, "expense_id,flight_no,travel_date,source\nB1,CA1234,2026-10-09,航司官网\n", base / "o3"))


if __name__ == "__main__":
    unittest.main()
