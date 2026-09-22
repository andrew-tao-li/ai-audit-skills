#!/usr/bin/env python3
"""
L2.4 半自动 fixture 生成（LLM 出题补盲点）

流程（对应 ROADMAP L2.4）：
  1. generate — LLM 生成候选 fixture（完整 CSV 数据 + ground truth）到 evals/blackbox/scenarios/<run>/
  2. validate — 用默认 policy 跑 skill，报告「实际检测到的 finding」与「预期」是否一致
  3. promote  — 人工 review 通过后，把候选迁入黄金测试集（fixtures/ + ground_truth/）
  4. list     — 列出候选

用法：
  export MINIMAX_API_KEY=...   # 或 DEEPSEEK_API_KEY（call_llm 自动回退）
  python3 evolution/fixture_generator.py generate --domain expense --count 3
  python3 evolution/fixture_generator.py generate --domain procurement --count 3 --focus "中国制造业"
  python3 evolution/fixture_generator.py list
  python3 evolution/fixture_generator.py validate --run <run-id>
  python3 evolution/fixture_generator.py promote --run <run-id> --id <fixture-id>

原则（对应 AGENTS.md / security-model）：
  - 生成的是「候选」，绝不自动入黄金测试集；promote 前必须人工 review。
  - 候选 fixture 必须与「默认 blackbox policy」一致（见 DEFAULT_* 常量，与 score_blackbox.py 对齐），
    否则 promote 后会导致黄金集 F1 退步。
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals" / "blackbox"))

from call_llm import call_llm  # noqa: E402  （返回 (text, provider)）
import score_blackbox  # noqa: E402  （复用其 run_expense / run_procurement）

SCENARIOS_DIR = ROOT / "evals" / "blackbox" / "scenarios"

# ============ 默认 policy（必须与 score_blackbox.py 的 run_expense/run_procurement 对齐） ============

EXPENSE_DEFAULT_POLICY = {
    "policy_version": "BLACKBOX-EXP-V2",
    "default_currency": "CNY",
    "limits": [{"rule_id": "HOTEL", "expense_type": "hotel", "currency": "CNY", "max_amount": 1000}],
    "approval_thresholds": [{"rule_id": "GENERAL", "currency": "CNY", "amount": 1000}],
    "large_amount_threshold": 5000,
    "low_level_approver_keywords": ["INTERN", "ASSIST"],
    "holidays": ["2026-10-01", "2026-10-02", "2026-10-03"],
    "weekend_check": True,
}

PROCUREMENT_DEFAULT_CONFIG = {
    "config_version": "BLACKBOX-PROC-V2",
    "default_currency": "CNY",
    "approval_thresholds": [{"rule_id": "PO-APPROVAL-20000", "currency": "CNY", "amount": 20000}],
    "split_window_days": 0,
    "new_vendor_days_threshold": 180,
    "new_vendor_amount_threshold": 20000,
    "concentration_share": 0.7,
    "concentration_min_orders": 3,
    "whitelists": {"address": []},
}

# ============ 领域 schema ============

DOMAINS = {
    "expense": {
        "skill": "expense-audit-v2",
        "label": "费用审计",
        "columns": ["expense_id", "employee_id", "expense_type", "expense_date", "submit_date",
                    "amount", "currency", "vendor_name", "invoice_number", "approver"],
        "finding_types": [
            "exact-duplicate-invoice", "exact-duplicate-employee-date-amount", "near-duplicate",
            "policy-threshold", "split-expense", "weekend-signal", "holiday-signal",
            "robust-outlier", "self-approval", "cross-employee-invoice", "submit-before-expense",
            "future-date", "missing-expense-type", "sequential-invoice", "invoice-format-anomaly",
            "large-amount-low-level-approval",
        ],
        "default_policy": EXPENSE_DEFAULT_POLICY,
    },
    "procurement": {
        "skill": "procurement-fraud-v2",
        "label": "采购审计",
        "tables": {
            "vendors": ["vendor_id", "vendor_name", "bank_account", "phone", "address", "created_at"],
            "purchase_orders": ["po_id", "vendor_id", "buyer_id", "category", "item", "unit", "region",
                                "quantity", "unit_price", "total_amount", "currency", "order_date",
                                "approval_date", "receipt_date"],
            "employees": ["employee_id", "employee_name", "department", "phone", "email", "address", "bank_account"],
            "payments": ["payment_id", "po_id", "vendor_id", "amount", "currency", "payment_date", "bank_account"],
            "bids": ["tender_id", "lot_id", "bidder_id", "bid_price", "currency", "document_path", "submitted_at"],
        },
        "finding_types": [
            "shared-bank-account", "shared-phone", "shared-email", "shared-address",
            "employee-vendor-shared-phone", "price-outlier", "split-order",
            "bid-text-similarity", "bid-price-subcluster", "new-vendor-large-order",
            "overpayment", "payment-before-order", "process-receipt-before-approval",
            "process-receipt-before-order", "process-payment-before-approval",
            "buyer-vendor-concentration",
        ],
        "default_config": PROCUREMENT_DEFAULT_CONFIG,
    },
}


def existing_ids(domain: str) -> list:
    gt_dir = ROOT / "evals" / "blackbox" / domain / "ground_truth"
    return sorted(f.stem for f in gt_dir.glob("*.json")) if gt_dir.exists() else []


# ============ generate ============

def build_prompt(domain: str, n: int, focus: str) -> str:
    d = DOMAINS[domain]
    existing = ", ".join(existing_ids(domain)) or "（无）"
    if domain == "expense":
        header = ", ".join('"' + c + '"' for c in d["columns"])
        return f"""你是资深中国民营制造业审计师。为「{d['label']} skill」生成 1 个新的黑盒测试 fixture（完整数据）。

## CSV 表头（严格按此顺序，不要增删列）
{",".join(d["columns"])}

## 已知 finding 类型（候选应触发其中一个或多个，且必须能被默认 policy 检出）
{chr(10).join("- " + ft for ft in d["finding_types"])}

## 默认 policy（fixture 必须在这个 policy 下触发预期 finding）
{json.dumps(d["default_policy"], ensure_ascii=False, indent=2)}

## 已存在 fixture（避免重复）
{existing}

## 额外关注
{focus or "（无，按你认为重要的盲点来）"}

## 要求
1. 真实可信（中国民营制造业常见金额、商户、日期、员工）
2. 明确"应该触发(expected_findings)"和"不应该触发(not_expected_findings)"的 finding
3. data 为完整 CSV：第一行是表头，后面至少 2 行数据（行数按需，能稳定触发预期 finding 即可）
4. 金额要与默认 policy 的阈值配合（注意：默认 policy 只有 hotel 有 1000 上限；meal/taxi/office 无上限，不会触发 policy-threshold）
5. 所有日期（expense_date/submit_date）一律用 2026-01-01 ~ 2026-06-30 之间的过去日期，绝不用未来日期（否则会误触发 future-date）

## 只输出一个 JSON（不要解释、不要 markdown 代码块），格式：
{{"id": "cand-{n:02d}", "description": "一句话", "difficulty": "简单|中等|困难", "expected_findings": ["finding-type"], "not_expected_findings": ["finding-type"], "data": [[{header}], ["E-1", "E-EMP-1", "..."]]}}"""

    # procurement
    table_desc = "\n".join(f"- {t}: {','.join(cols)}" for t, cols in d["tables"].items())
    return f"""你是资深中国民营制造业审计师。为「{d['label']} skill」生成 1 个新的黑盒测试 fixture（完整数据）。

## 数据表（每张表第一行是表头，后面是数据行）
{table_desc}

## 已知 finding 类型（候选应触发其中一个或多个）
{chr(10).join("- " + ft for ft in d["finding_types"])}

## 默认 config（fixture 必须在这个 config 下触发预期 finding）
{json.dumps(d["default_config"], ensure_ascii=False, indent=2)}

## 已存在 fixture（避免重复）
{existing}

## 额外关注
{focus or "（无）"}

## 要求
1. 真实可信（中国民营制造业常见供应商、物料、金额、日期）
2. 明确 expected_findings 与 not_expected_findings
3. 每张表用数组表示：vendors/purchase_orders/employees 必填；payments/bids 按需（可为空数组）
4. 金额与默认 config 阈值配合（如 approval_threshold 20000、new_vendor_amount_threshold 20000）

## 只输出一个 JSON（不要解释、不要 markdown），格式：
{{"id": "cand-{n:02d}", "description": "一句话", "difficulty": "简单|中等|困难", "expected_findings": ["..."], "not_expected_findings": ["..."], "vendors": [["vendor_id", "vendor_name", "..."], ["V-1", "甲公司", "..."]], "purchase_orders": [[...]], "employees": [[...]], "payments": [], "bids": []}}"""


def parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```"))
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        text = text[s:e + 1]
    return json.loads(text)


def generate(domain: str, count: int, focus: str) -> str:
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    out_dir = SCENARIOS_DIR / run_id / domain
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for n in range(1, count + 1):
        prompt = build_prompt(domain, n, focus)
        try:
            text, provider = call_llm(prompt, provider="auto", max_tokens=4000, temperature=0.8)
            fx = parse_json(text)
            fid = str(fx.get("id", f"cand-{n:02d}"))
            fx_dir = out_dir / fid
            fx_dir.mkdir(parents=True, exist_ok=True)
            if domain == "expense":
                write_csv(fx_dir / "data.csv", fx["data"])
            else:
                input_dir = fx_dir / "input"
                input_dir.mkdir(parents=True, exist_ok=True)
                for table, rows in fx.items():
                    if table in d_tables(domain) and isinstance(rows, list) and rows:
                        write_csv(input_dir / f"{table}.csv", rows)
            write_gt(fx_dir / "ground-truth.json", fx, domain)
            print(f"  ✓ [{provider}] {fid}  ({fx.get('difficulty','?')})  expected={fx.get('expected_findings')}")
            ok += 1
        except Exception as e:
            print(f"  ⚠ 第 {n} 个生成失败: {e}", file=sys.stderr)
    print(f"\n生成 {ok}/{count} 个候选 → {out_dir.relative_to(ROOT)}")
    return run_id


def d_tables(domain):
    return DOMAINS[domain].get("tables", {}).keys()


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


def write_gt(path: Path, fx: dict, domain: str):
    gt = {
        "fixture_id": fx.get("id", ""),
        "description": fx.get("description", ""),
        "difficulty": fx.get("difficulty", ""),
        "expected_findings": fx.get("expected_findings", []),
        "not_expected_findings": fx.get("not_expected_findings", []),
        "generated_by": "fixture_generator",
    }
    path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")


# ============ validate ============

def validate(run_id: str) -> int:
    run_dir = SCENARIOS_DIR / run_id
    if not run_dir.exists():
        print(f"ERROR: 找不到 {run_dir}", file=sys.stderr)
        return 1
    all_consistent = True
    for domain in ["expense", "procurement"]:
        ddir = run_dir / domain
        if not ddir.exists():
            continue
        for fx_dir in sorted(ddir.iterdir()):
            gt = json.loads((fx_dir / "ground-truth.json").read_text(encoding="utf-8"))
            expected = set(gt.get("expected_findings", []))
            not_expected = set(gt.get("not_expected_findings", []))
            with tempfile.TemporaryDirectory() as tmp:
                work = Path(tmp)
                if domain == "expense":
                    csv_path = fx_dir / "data.csv"
                    detected = set(score_blackbox.run_expense(csv_path, {}, work))
                else:
                    detected = set(score_blackbox.run_procurement(fx_dir, {}, work))
            missing = expected - detected          # 漏报：预期但没检出
            extra = detected & not_expected         # 误报：不该触发却触发了
            consistent = not missing and not extra
            all_consistent = all_consistent and consistent
            mark = "✓" if consistent else "✗"
            print(f"  {mark} {domain}/{fx_dir.name}")
            print(f"      expected={sorted(expected)}")
            print(f"      detected={sorted(detected)}")
            if missing:
                print(f"      ⚠ 漏报: {sorted(missing)}")
            if extra:
                print(f"      ⚠ 误报: {sorted(extra)}")
    print("\n结论:", "全部一致" if all_consistent else "存在不一致（promote 前请修正）")
    return 0 if all_consistent else 1


# ============ promote ============

def promote(run_id: str, fixture_id: str) -> int:
    fx_dir = None
    for domain in ["expense", "procurement"]:
        cand = SCENARIOS_DIR / run_id / domain / fixture_id
        if cand.exists():
            fx_dir = cand
            break
    if fx_dir is None:
        print(f"ERROR: 找不到候选 {run_id}/{fixture_id}", file=sys.stderr)
        return 1
    domain = fx_dir.parent.name
    gt = json.loads((fx_dir / "ground-truth.json").read_text(encoding="utf-8"))

    # 防撞名
    if fixture_id in existing_ids(domain):
        print(f"ERROR: {domain} 已存在 fixture {fixture_id}，请先改名", file=sys.stderr)
        return 1

    # 迁入黄金集
    if domain == "expense":
        shutil.copy2(fx_dir / "data.csv", ROOT / "evals" / "blackbox" / "expense" / "fixtures" / f"{fixture_id}.csv")
    else:
        dst = ROOT / "evals" / "blackbox" / "procurement" / "fixtures" / fixture_id
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(fx_dir / "input", dst / "input")

    gt_out = {
        "fixture_id": fixture_id,
        "description": gt.get("description", ""),
        "expected_findings": gt.get("expected_findings", []),
        "policy_overrides": {},
    }
    (ROOT / "evals" / "blackbox" / domain / "ground_truth" / f"{fixture_id}.json").write_text(
        json.dumps(gt_out, indent=2, ensure_ascii=False), encoding="utf-8")

    # 复跑黄金集确认不退步
    r = subprocess.run(["python3", "evals/blackbox/score_blackbox.py", "--version", "v0.2.0-baseline"],
                       cwd=ROOT, capture_output=True, text=True)
    summary_ok = "F1: 100.00%" in r.stdout
    print(f"✓ 已迁入 {domain}/{fixture_id}")
    print(f"  复跑黄金集: {'F1 仍 100%（通过）' if summary_ok else '请检查（可能退步）'}")
    return 0 if summary_ok else 1


# ============ list ============

def list_runs():
    if not SCENARIOS_DIR.exists():
        print("(无候选)")
        return
    for run in sorted(SCENARIOS_DIR.iterdir(), reverse=True):
        if not run.is_dir():
            continue
        print(f"\n[{run.name}]")
        for domain in sorted(run.iterdir()):
            if domain.is_dir():
                for fx in sorted(domain.iterdir()):
                    if fx.is_dir():
                        gt = json.loads((fx / "ground-truth.json").read_text(encoding="utf-8"))
                        print(f"  {domain.name}/{fx.name}  [{gt.get('difficulty','?')}]  {gt.get('description','')}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--domain", choices=list(DOMAINS.keys()), required=True)
    g.add_argument("--count", type=int, default=3)
    g.add_argument("--focus", default="")

    sub.add_parser("list")

    v = sub.add_parser("validate")
    v.add_argument("--run", required=True)

    pm = sub.add_parser("promote")
    pm.add_argument("--run", required=True)
    pm.add_argument("--id", required=True)

    args = p.parse_args()
    if args.cmd == "generate":
        sys.exit(generate(args.domain, args.count, args.focus))
    if args.cmd == "list":
        sys.exit(list_runs())
    if args.cmd == "validate":
        sys.exit(validate(args.run))
    if args.cmd == "promote":
        sys.exit(promote(args.run, args.id))


if __name__ == "__main__":
    main()
