#!/usr/bin/env python3
"""audit-sql-builder 核心：把「审计需求」翻译成可在业务系统上执行的 **SQL 文本**。

定位：审计的**第 0 步——取数**。它不分析数据、不下审计结论；只做两件事：
  1. 读你从 IT 拿到的**数据字典**（表名/字段名/中文名），**建议字段映射**（带候选与置信度，不硬猜）；
  2. 按**审计需求**渲染出 `.sql` 文件（带注释），交给 DBA 跑；跑出来的 CSV 再喂给 expense-audit-v2 等。

**离线确定性**：不调用任何模型、不联网、不连接数据库；纯字符串渲染，结果可复现。
缺字段时**绝不硬凑**——明确指出"这个需求需要『发票号』，你的字典里没有"。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

VERSION = "0.1.0"
SKILL = "audit-sql-builder"

# ── 审计「标准字段」→ 数据字典里可能的列名/中文名别名（用于猜映射）─────────────
FIELD_ALIASES: Dict[str, List[str]] = {
    "employee_id": ["employee_id", "emp_id", "employee", "staff_id", "工号", "员工编号", "员工", "报销人", "申请人"],
    "expense_date": ["expense_date", "date", "transaction_date", "发生日期", "费用日期", "业务日期", "消费日期", "报销日期"],
    "amount": ["amount", "expense_amount", "claim_amount", "金额", "报销金额", "费用金额", "付款金额", "金额(元)"],
    "currency": ["currency", "币种", "货币"],
    "invoice_number": ["invoice_number", "invoice_no", "invoice", "发票号", "发票号码"],
    "expense_type": ["expense_type", "category", "type", "费用类型", "费用类别", "报销类型", "费用科目"],
    "approver": ["approver", "approved_by", "审批人", "审核人", "审批"],
    "vendor_name": ["vendor_name", "vendor", "merchant", "supplier", "商户", "商家", "供应商", "收款方"],
    "department": ["department", "dept", "部门", "成本中心"],
    "submit_date": ["submit_date", "submission_date", "提交日期", "申请日期", "申报日期"],
}

DIALECTS = ("sqlite", "mysql", "postgres", "sqlserver", "oracle")

# 各方言的「周末表达式」与标识符引用
WEEKEND_EXPR = {
    "sqlite": "strftime('%w', {d}) IN ('0','6')",
    "mysql": "DAYOFWEEK({d}) IN (1,7)",
    "postgres": "EXTRACT(DOW FROM {d}) IN (0,6)",
    "sqlserver": "DATEPART(weekday, {d}) IN (1,7)",
    "oracle": "TRIM(TO_CHAR({d}, 'D')) IN ('1','7')",
}
QUOTE = {
    "sqlite": ('"', '"'), "postgres": ('"', '"'), "oracle": ('"', '"'),
    "mysql": ("`", "`"), "sqlserver": ("[", "]"),
}

# v0.1.0：审批人是「多人分号列表」时，判断其中是否包含报销人（真实审计师踩过的坑）
APPROVER_CONTAINS = {
    "sqlite": "{a} LIKE '%' || {e} || '%'",
    "postgres": "{a} LIKE '%' || {e} || '%'",
    "oracle": "{a} LIKE '%' || {e} || '%'",
    "mysql": "{a} LIKE CONCAT('%', {e}, '%')",
    "sqlserver": "{a} LIKE CONCAT('%', {e}, '%')",
}


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def norm_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", norm_text(value).lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quote_ident(name: str, dialect: str) -> str:
    left, right = QUOTE.get(dialect, ('"', '"'))
    return "%s%s%s" % (left, str(name).replace(right, right + right), right)


def qualify(table: str, column: str, dialect: str) -> str:
    if table:
        return "%s.%s" % (quote_ident(table, dialect), quote_ident(column, dialect))
    return quote_ident(column, dialect)


# ── 读数据字典 ────────────────────────────────────────────────────────────────
def read_schema(path: Path) -> List[Dict[str, str]]:
    """数据字典：表名 / 字段名 / （类型）/（中文名）/（备注）。最少需要「表名+字段名」两列。"""
    suffix = path.suffix.lower()
    rows: List[Dict[str, str]] = []
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = [norm_text(h) for h in (reader.fieldnames or [])]
            for raw in reader:
                rows.append({norm_text(k): norm_text(v) for k, v in raw.items() if k is not None})
    elif suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("读取 XLSX 需要 openpyxl；或先把数据字典另存为 CSV。") from exc
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        values = list(ws.iter_rows(values_only=True))
        if not values:
            return []
        headers = [norm_text(h) for h in values[0]]
        for row in values[1:]:
            rows.append({headers[i]: norm_text(row[i]) for i in range(min(len(headers), len(row)))})
    else:
        raise SystemExit("数据字典只支持 CSV / XLSX：%s" % path)

    def pick(*names: str) -> str:
        for n in names:
            for h in (rows[0].keys() if rows else []):
                if norm_key(h) == norm_key(n):
                    return h
        for n in names:
            for h in (rows[0].keys() if rows else []):
                if norm_key(n) in norm_key(h):
                    return h
        return ""

    table_col = pick("表名", "table", "table_name", "表")
    column_col = pick("字段名", "column", "column_name", "字段", "列名")
    label_col = pick("中文名", "label", "comment", "说明", "含义", "字段说明")
    type_col = pick("类型", "type", "data_type", "数据类型")
    if not table_col or not column_col:
        raise SystemExit("数据字典缺少「表名」或「字段名」列（最少需要这两列）。")
    out = []
    for raw in rows:
        table, column = norm_text(raw.get(table_col)), norm_text(raw.get(column_col))
        if not table and not column:
            continue
        out.append({
            "table": table, "column": column,
            "label": norm_text(raw.get(label_col)) if label_col else "",
            "type": norm_text(raw.get(type_col)) if type_col else "",
        })
    return out


# ── 猜字段映射（给候选 + 置信度，不硬猜）─────────────────────────────────────
def suggest_mapping(schema: List[Dict[str, str]]) -> Dict[str, Any]:
    suggestions: Dict[str, Any] = {}
    for field, aliases in FIELD_ALIASES.items():
        candidates = []
        for item in schema:
            for alias in aliases:
                a = norm_key(alias)
                for text in (item["column"], item["label"]):
                    t = norm_key(text)
                    if not t:
                        continue
                    if t == a:
                        score = 1.0
                    elif a in t or t in a:
                        score = 0.7
                    else:
                        continue
                    candidates.append({"table": item["table"], "column": item["column"],
                                        "label": item["label"], "confidence": score})
        # 去重，保留最高分
        best: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for c in candidates:
            key = (c["table"], c["column"])
            if key not in best or c["confidence"] > best[key]["confidence"]:
                best[key] = c
        ranked = sorted(best.values(), key=lambda c: (-c["confidence"], c["table"], c["column"]))
        suggestions[field] = ranked[:3]
    return suggestions


def resolve_mapping(suggestions: Dict[str, Any], explicit: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """显式映射优先；否则取置信度最高的唯一候选（≥0.7 且无并列）。"""
    mapping: Dict[str, Dict[str, str]] = {}
    for field in FIELD_ALIASES:
        if field in explicit:
            value = explicit[field]
            if isinstance(value, dict):
                mapping[field] = {"table": norm_text(value.get("table", "")), "column": norm_text(value.get("column", ""))}
            else:   # 允许 "表.字段" 或 "字段"
                text = norm_text(value)
                if "." in text:
                    t, c = text.split(".", 1)
                    mapping[field] = {"table": t, "column": c}
                else:
                    cands = [s for s in suggestions.get(field, []) if norm_key(s["column"]) == norm_key(text)]
                    mapping[field] = {"table": cands[0]["table"] if cands else "", "column": text}
            continue
        cands = suggestions.get(field, [])
        if len(cands) == 1 and cands[0]["confidence"] >= 0.7:
            mapping[field] = {"table": cands[0]["table"], "column": cands[0]["column"]}
    return mapping


# ── 渲染 SQL ─────────────────────────────────────────────────────────────────
def load_templates(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render(template: str, mapping: Dict[str, Dict[str, str]], dialect: str) -> str:
    def ref(field: str) -> str:
        m = mapping.get(field)
        if not m:
            raise KeyError(field)
        return qualify(m["table"], m["column"], dialect)

    out = template
    out = out.replace("{{table}}", quote_ident(mapping["_table"]["table"], dialect))
    out = out.replace("{{approver_contains_employee}}",
                      APPROVER_CONTAINS.get(dialect, APPROVER_CONTAINS["sqlite"]).format(a=ref("approver"), e=ref("employee_id")))
    # 周末表达式需要日期列
    out = re.sub(r"\{\{weekend:(\w+)\}\}", lambda m: WEEKEND_EXPR[dialect].format(d=ref(m.group(1))), out)
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: ref(m.group(1)), out)
    return out


def build(args) -> int:
    schema_path = args.schema.resolve()
    if not schema_path.is_file():
        raise FileNotFoundError(schema_path)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("输出目录非空；请指定新的目录：%s" % output)
    output.mkdir(parents=True, exist_ok=True)

    schema = read_schema(schema_path)
    if not schema:
        raise SystemExit("数据字典是空的（没有解析到任何字段）。")
    suggestions = suggest_mapping(schema)
    explicit = json.loads(args.map.read_text(encoding="utf-8-sig")) if args.map else {}
    mapping = resolve_mapping(suggestions, explicit)

    templates = load_templates(Path(__file__).resolve().parent.parent / "assets" / "sql_templates.json")
    wanted = [n.strip() for n in (args.need.split(",") if args.need else []) if n.strip()]
    needs = [n for n in templates["needs"] if not wanted or n["id"] in wanted]
    unknown = [w for w in wanted if w not in {n["id"] for n in templates["needs"]}]
    if unknown:
        raise SystemExit("未知的审计需求：%s。可选：%s" % (", ".join(unknown), ", ".join(n["id"] for n in templates["needs"])))

    sql_dir = output / "sql"
    sql_dir.mkdir(exist_ok=True)
    generated, missing_rows = [], []
    for need in needs:
        lacking = [f for f in need["requires"] if f not in mapping]
        if lacking:
            missing_rows.append({
                "need": need["id"], "need_title": need["title"],
                "missing_fields": "; ".join(FIELD_ALIASES.get(f, [f])[0] for f in lacking),
                "missing_field_keys": "; ".join(lacking),
            })
            continue
        if need.get("single_table") and len({mapping[f]["table"] for f in need["requires"]}) > 1:
            missing_rows.append({"need": need["id"], "need_title": need["title"],
                                 "missing_fields": "需要同一张表内的字段（当前映射跨多张表，需人工指定 --map）",
                                 "missing_field_keys": "cross_table"})
            continue
        m = dict(mapping)
        m["_table"] = mapping[need["requires"][0]]
        try:
            sql = render(need["sql"][args.dialect], m, args.dialect)
        except KeyError:
            continue
        header = ("-- 审计需求：%s\n-- 方言：%s | 依赖字段：%s\n-- 说明：%s\n-- 注意：这是**取数**查询，不构成审计结论；导出 CSV 后交给审计技能分析。\n\n"
                  % (need["title"], args.dialect, ", ".join(need["requires"]), need.get("note", "")))
        (sql_dir / ("%s.sql" % need["id"])).write_text(header + sql + "\n", encoding="utf-8")
        generated.append(need["id"])

    (output / "mapping.suggested.json").write_text(
        json.dumps({"suggested": suggestions, "used": mapping}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "missing_fields.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("need", "need_title", "missing_fields", "missing_field_keys"))
        writer.writeheader()
        writer.writerows(missing_rows)

    summary = [
        "# 取数（SQL）生成摘要", "",
        "- 数据字典：`%s`（%d 个字段）" % (schema_path.name, len(schema)),
        "- 方言：`%s`" % args.dialect,
        "- 生成 SQL：%d 条；因缺字段跳过：%d 条" % (len(generated), len(missing_rows)), "",
        "> 本技能的产出是**给 DBA 执行的 SQL 文本**，不是审计结论、也没有连接任何数据库。",
        "> 跑完导出的 CSV，交给 `expense-audit-v2` 等审计技能即可。", "",
        "## 生成的文件", "",
    ]
    summary += ["- `sql/%s.sql`" % g for g in generated] or ["-（无）"]
    if missing_rows:
        summary += ["", "## 需要回 IT 确认的字段（否则这些需求无法生成）", ""]
        for r in missing_rows:
            summary.append("- **%s**：缺 %s" % (r["need_title"], r["missing_fields"]))
    summary += ["", "## 下一步", "",
                "1. 打开 `mapping.suggested.json`，和 IT 逐条确认字段映射（**这一步必须人工**）；",
                "2. 把确认后的映射用 `--map` 传回来，重新生成；",
                "3. 把 `sql/*.sql` 交给 DBA 执行、导出 CSV；",
                "4. 把 CSV 交给 `expense-audit-v2` 做审计。"]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    quality = ["# 数据字典体检", "",
               "- 表数：%d，字段数：%d" % (len({s["table"] for s in schema}), len(schema)), "",
               "## 已确认的字段映射", ""]
    for field, m in sorted(mapping.items()):
        quality.append("- `%s` → `%s.%s`" % (field, m["table"], m["column"]))
    if not mapping:
        quality.append("-（未能确认任何字段，请用 `--map` 指定）")
    quality += ["", "## 未映射的标准字段", ""]
    for field in FIELD_ALIASES:
        if field not in mapping:
            quality.append("- `%s`（字典里没找到；可能只能靠 `--map`）" % field)
    (output / "data_quality.md").write_text("\n".join(quality) + "\n", encoding="utf-8")

    finished = datetime.now(timezone.utc)
    manifest = {
        "skill": SKILL, "skill_version": VERSION,
        "started_at": finished.isoformat(), "finished_at": finished.isoformat(),
        "input_files": [{"path": schema_path.name, "sha256": sha256_file(schema_path)}],
        "parameters": {"dialect": args.dialect, "need": wanted or "all"},
        "field_mapping": mapping, "generated": generated, "skipped_missing": [r["need"] for r in missing_rows],
        "network_access": False,
        "outputs": ["sql/", "mapping.suggested.json", "missing_fields.csv", "summary.md", "data_quality.md",
                    "run_manifest.json", "dashboard.html"],
        "note": "技术审计轨迹：本技能只生成 SQL 文本，不连接数据库、不分析数据。",
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "dashboard.html").write_text(build_dashboard(manifest), encoding="utf-8")
    print(json.dumps({"output": str(output), "generated": len(generated), "skipped_missing": len(missing_rows)},
                     ensure_ascii=False))
    return 0


def build_dashboard(manifest: Dict[str, Any]) -> str:
    rows = "".join("<li>%s</li>" % g for g in manifest["generated"]) or "<li>（无）</li>"
    miss = "".join("<li>%s</li>" % m for m in manifest["skipped_missing"]) or "<li>（无）</li>"
    return ("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<title>审计取数 · SQL 生成</title></head><body>"
            "<h1>审计取数（SQL）生成</h1>"
            "<p>本技能只把审计需求翻译成 SQL，不连接数据库、不分析数据。</p>"
            "<h2>已生成</h2><ul>%s</ul><h2>因缺字段跳过</h2><ul>%s</ul>"
            "<p>下一步：与 IT 确认 mapping.suggested.json → <code>--map</code> 重新生成 → DBA 执行 → CSV 交给 expense-audit-v2。</p>"
            "</body></html>" % (rows, miss))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="把审计需求翻译成 SQL（离线、确定性）")
    parser.add_argument("--schema", type=Path, required=True, help="数据字典（CSV/XLSX）：表名/字段名/类型/中文名")
    parser.add_argument("--map", type=Path, help="可选：字段映射 JSON（与 IT 确认后回填）")
    parser.add_argument("--need", help="可选：要生成的需求 id，逗号分隔；默认全部")
    parser.add_argument("--dialect", default="sqlite", choices=DIALECTS, help="目标数据库方言")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    return build(args)


if __name__ == "__main__":
    sys.exit(main())
