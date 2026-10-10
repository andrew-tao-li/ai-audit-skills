#!/usr/bin/env python3
"""audit-sql-builder 单测。

关键：不只检查"SQL 长得对"，而是**真的执行**——用 Python 自带 `sqlite3` 建一张合成表，
跑我们生成的 SQL，**比对返回的行**。这样才能说"测过是对的"，而不是"看起来对"。
"""
import csv
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "run_sql_builder.py"
SCHEMA = SKILL_ROOT / "examples" / "input" / "schema.csv"


def load_module():
    spec = importlib.util.spec_from_file_location("sql_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(schema: Path, out: Path, extra=None):
    cmd = [sys.executable, str(SCRIPT), "--schema", str(schema), "--output", str(out)]
    if extra:
        cmd += extra
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env={"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONIOENCODING": "utf-8"})
    return proc


class SqlBuilderTest(unittest.TestCase):
    def test_suggests_mapping_and_generates_all_needs(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            proc = build(SCHEMA, out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            names = sorted(p.name for p in (out / "sql").glob("*.sql"))
            self.assertEqual(names, ["duplicate-claim.sql", "duplicate-invoice.sql",
                                     "self-approval.sql", "weekend-expense.sql"])
            mapping = json.loads((out / "mapping.suggested.json").read_text(encoding="utf-8"))["used"]
            self.assertEqual(mapping["employee_id"]["column"], "EMP_NO")
            self.assertEqual(mapping["amount"]["column"], "CLAIM_AMOUNT")

    def test_missing_fields_are_reported_not_guessed(self):
        """缺字段绝不硬凑：字典里没有发票号 → duplicate-invoice 被跳过并明确报出。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            thin = td / "thin.csv"
            thin.write_text("表名,字段名,类型,中文名\nT,EMP_NO,VARCHAR,工号\nT,EXPENSE_DATE,DATE,费用发生日期\nT,AMOUNT,DECIMAL,金额\n",
                            encoding="utf-8")
            out = td / "out"
            proc = build(thin, out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((out / "sql" / "duplicate-invoice.sql").exists())
            missing = (out / "missing_fields.csv").read_text(encoding="utf-8")
            self.assertIn("duplicate-invoice", missing)
            self.assertIn("发票", missing)

    def test_generated_sql_actually_runs_and_finds_rows(self):
        """★ 真执行：建 sqlite 合成表 → 跑生成的 SQL → 比对行。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            out = td / "out"
            self.assertEqual(build(SCHEMA, out).returncode, 0)

            conn = sqlite3.connect(":memory:")
            conn.execute("""CREATE TABLE FIN_CLAIM (
                CLAIM_ID TEXT, EMP_NO TEXT, EXPENSE_DATE TEXT, CLAIM_AMOUNT REAL,
                INVOICE_NO TEXT, APPROVER TEXT, EXPENSE_TYPE TEXT)""")
            rows = [
                # E1：同日同额两笔 → 重复报销；且审批人是分号列表且含 E1 → 自审自批
                ("C1", "E1", "2024-05-02", 100.0, "INV-A", "M1;E1", "餐饮"),
                ("C2", "E1", "2024-05-02", 100.0, "INV-A", "M1", "餐饮"),
                # E2：周末（2024-05-04 周六）
                ("C3", "E2", "2024-05-04", 50.0, "INV-B", "M1", "交通"),
                ("C4", "E3", "2024-05-06", 20.0, "INV-C", "M1", "交通"),
            ]
            conn.executemany("INSERT INTO FIN_CLAIM VALUES (?,?,?,?,?,?,?)", rows)

            def sql(name):
                text = (out / "sql" / ("%s.sql" % name)).read_text(encoding="utf-8")
                return "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))

            dup = conn.execute(sql("duplicate-claim")).fetchall()
            self.assertEqual({r[0] for r in dup}, {"C1", "C2"})          # 只有同日同额的两笔

            inv = conn.execute(sql("duplicate-invoice")).fetchall()
            self.assertEqual({r[0] for r in inv}, {"C1", "C2"})          # 同发票号 + 同金额

            self_approval = conn.execute(sql("self-approval")).fetchall()
            self.assertEqual({r[0] for r in self_approval}, {"C1"})      # 审批人列表含 E1

            weekend = conn.execute(sql("weekend-expense")).fetchall()
            self.assertEqual({r[0] for r in weekend}, {"C3"})            # 2024-05-04 是周六

    def test_dialects_render_via_library(self):
        """五个方言都能渲染出 SQL；含中文/特殊列名时按方言加引号。"""
        module = load_module()
        mapping = {
            "employee_id": {"table": "财务台账", "column": "工号"},
            "expense_date": {"table": "财务台账", "column": "发生日期"},
            "amount": {"table": "财务台账", "column": "金额"},
            "approver": {"table": "财务台账", "column": "审批人"},
            "_table": {"table": "财务台账", "column": "工号"},
        }
        templates = module.load_templates(SKILL_ROOT / "assets" / "sql_templates.json")
        need = next(n for n in templates["needs"] if n["id"] == "weekend-expense")
        for dialect in module.DIALECTS:
            sql = module.render(need["sql"][dialect], mapping, dialect)
            self.assertIn("财务台账", sql)
            self.assertNotIn("{{", sql, "方言 %s 仍有未渲染的占位符" % dialect)

    def test_refuses_nonempty_output_dir(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            out.mkdir()
            (out / "x.txt").write_text("x", encoding="utf-8")
            proc = build(SCHEMA, out)
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
