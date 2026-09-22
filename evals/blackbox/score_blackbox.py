#!/usr/bin/env python3
"""
评分脚本：跑黄金测试集，输出 precision/recall/F1 + 每个 fixture 的诊断。
调用：python3 evals/blackbox/score_blackbox.py [--version VERSION]
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

ROOT = Path(__file__).resolve().parent.parent.parent
BLACKBOX = ROOT / "evals" / "blackbox"
LOG_DIR = ROOT / "evolution" / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 评分类型常量
PRECISION = "precision"
RECALL = "recall"
F1 = "f1"


def run_expense(fix_dir: Path, gt: dict, work_dir: Path) -> list:
    """跑一个 expense fixture，返回 finding_type 列表"""
    # expense fixture 是 csv 文件，直接在 fixtures/ 下
    csv_in = fix_dir.with_suffix(".csv")
    if not csv_in.exists():
        return ["__ERROR__: csv not found: " + str(csv_in)]
    # 使用通用 policy
    policy_path = work_dir / "policy.json"
    policy = {
        "policy_version": "BLACKBOX-EXP-V2",
        "default_currency": "CNY",
        "limits": [{"rule_id": "HOTEL", "expense_type": "hotel", "currency": "CNY", "max_amount": 1000}],
        "approval_thresholds": [{"rule_id": "GENERAL", "currency": "CNY", "amount": 1000}],
        "large_amount_threshold": 5000,
        "low_level_approver_keywords": ["INTERN", "ASSIST"],
        "holidays": ["2026-10-01", "2026-10-02", "2026-10-03"],
        "weekend_check": True,
    }
    # 应用 fixture 的 policy overrides
    policy.update(gt.get("policy_overrides", {}))
    policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False), encoding="utf-8")

    output_dir = work_dir / "output"
    script = ROOT / "skills-v2" / "expense-audit-v2" / "scripts" / "run_expense_audit.py"
    result = subprocess.run(
        ["python3", str(script), "--input", str(csv_in), "--policy", str(policy_path), "--output", str(output_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return ["__ERROR__: " + result.stderr[:200]]

    findings_csv = output_dir / "findings.csv"
    if not findings_csv.exists():
        return []

    types = []
    with findings_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            types.append(row.get("finding_type", ""))
    return types


def run_procurement(fix_dir: Path, gt: dict, work_dir: Path) -> list:
    """跑一个 procurement fixture，返回 finding_type 列表"""
    input_dir = fix_dir / "input"
    output_dir = work_dir / "output"
    script = ROOT / "skills-v2" / "procurement-fraud-v2" / "scripts" / "run_procurement_audit.py"

    # 创建临时 config
    config_path = work_dir / "config.json"
    config = {
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
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    result = subprocess.run(
        ["python3", str(script), "--input-dir", str(input_dir), "--config", str(config_path), "--output", str(output_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return ["__ERROR__: " + result.stderr[:200]]

    findings_csv = output_dir / "findings.csv"
    if not findings_csv.exists():
        return []

    types = []
    with findings_csv.open(encoding="utf-8") as f:
        import csv as csvmod
        reader = csvmod.DictReader(f)
        for row in reader:
            types.append(row.get("finding_type", ""))
    return types


def run_investigation(fix_dir: Path, gt: dict, work_dir: Path) -> list:
    """跑一个 investigation fixture"""
    input_dir = fix_dir / "input"
    output_dir = work_dir / "output"
    script = ROOT / "skills-v2" / "investigation-assistant-v2" / "scripts" / "build_case_workspace.py"

    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}

    if gt.get("expected_outcome") == "rejected_by_scope_gate":
        # 应该被拒绝
        result = subprocess.run(
            ["python3", str(script), "--input-dir", str(input_dir), "--scope", str(input_dir / "scope.json"), "--output", str(output_dir)],
            capture_output=True, text=True, env=env
        )
        if result.returncode != 0 and "authorization_confirmed" in result.stderr:
            return ["__rejected_by_scope_gate__"]
        return ["__scope_gate_not_rejected__"]
    else:
        result = subprocess.run(
            ["python3", str(script), "--input-dir", str(input_dir), "--scope", str(input_dir / "scope.json"), "--output", str(output_dir)],
            capture_output=True, text=True, env=env
        )
        if result.returncode != 0:
            return ["__ERROR__: " + result.stderr[:200]]

        # 检查产出是否完整
        findings_file = output_dir / "findings.jsonl"
        if findings_file.exists():
            return ["__workspace_created__"]
        return ["__workspace_missing__"]


def score_one(expected: list, actual: list) -> dict:
    """对单个 fixture 评分"""
    # 处理 actual 中的 marker 格式
    actual_normalized = set()
    for a in actual:
        if a.startswith("__") and a.endswith("__"):
            actual_normalized.add(a[2:-2])
        else:
            actual_normalized.add(a)

    expected_normalized = set()
    for e in expected:
        if e.startswith("__") and e.endswith("__"):
            expected_normalized.add(e[2:-2])
        else:
            expected_normalized.add(e)

    expected_set = expected_normalized
    actual_set = actual_normalized

    # 特殊处理：完全空集合
    if not expected_set and not actual_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": [], "fp": [], "fn": [], "clean_match": True}
    if not expected_set and actual_set:
        return {"precision": 0.0, "recall": 1.0, "f1": 0.0, "tp": [], "fp": sorted(actual_set), "fn": []}
    if expected_set and not actual_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "tp": [], "fp": [], "fn": sorted(expected_set)}

    tp = expected_set & actual_set
    fp = actual_set - expected_set
    fn = expected_set - actual_set

    p = len(tp) / (len(tp) + len(fp)) if (len(tp) + len(fp)) > 0 else 0
    r = len(tp) / (len(tp) + len(fn)) if (len(tp) + len(fn)) > 0 else 0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0

    return {
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f1, 4),
        "tp": sorted(tp),
        "fp": sorted(fp),
        "fn": sorted(fn),
    }


def run_skill_for_skill(skill_name: str, fixtures: list, work_dir: Path) -> list:
    """跑一个 skill 的所有 fixture，返回每个 fixture 的评分结果"""
    import csv as csvmod
    results = []
    runner = {"expense": run_expense, "procurement": run_procurement, "investigation": run_investigation}[skill_name]

    for fix in fixtures:
        fix_id = fix["fixture_id"]
        gt = fix.get("expected_findings", [])
        # investigation 用 expected_outcome，expense/procurement 用 expected_findings
        if "expected_outcome" in fix:
            gt = [fix["expected_outcome"]]

        # expense: csv 文件在 fixtures/<id>.csv
        # procurement/investigation: 目录在 fixtures/<id>/input
        if skill_name == "expense":
            fix_path = BLACKBOX / "expense" / "fixtures" / f"{fix_id}.csv"
            if not fix_path.exists():
                results.append({"fixture": fix_id, "error": f"fixture csv not found: {fix_path}"})
                continue
        else:
            fix_path = BLACKBOX / skill_name / "fixtures" / fix_id
            if not fix_path.exists():
                results.append({"fixture": fix_id, "error": f"fixture dir not found: {fix_path}"})
                continue

        # 每个 fixture 用独立 tmp dir
        with tempfile.TemporaryDirectory(prefix=f"{fix_id}_") as tmp:
            tmp_path = Path(tmp)
            try:
                actual = runner(fix_path, fix, tmp_path)
                score = score_one(gt, actual)
                results.append({
                    "fixture": fix_id,
                    "description": fix.get("description", ""),
                    "expected": gt,
                    "actual": actual,
                    **score,
                })
            except Exception as e:
                results.append({"fixture": fix_id, "error": str(e)})

    return results


def aggregate(results_by_skill: dict) -> dict:
    """聚合所有 skill 的评分"""
    summary = {}
    for skill, results in results_by_skill.items():
        valid = [r for r in results if "error" not in r]
        if not valid:
            summary[skill] = {"tests": len(results), "errors": len(results)}
            continue
        avg_p = sum(r["precision"] for r in valid) / len(valid)
        avg_r = sum(r["recall"] for r in valid) / len(valid)
        avg_f1 = sum(r["f1"] for r in valid) / len(valid)
        summary[skill] = {
            "tests": len(results),
            "errors": len([r for r in results if "error" in r]),
            "precision": round(avg_p, 4),
            "recall": round(avg_r, 4),
            "f1": round(avg_f1, 4),
        }
    return summary


def load_fixtures(skill: str) -> list:
    """从 ground_truth 目录加载 fixture 列表"""
    base = BLACKBOX / skill / "ground_truth"
    fixtures = []
    for gt_path in sorted(base.glob("*.json")):
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        fixtures.append(gt)
    return fixtures


def print_report(results_by_skill: dict, summary: dict):
    """输出人类可读报告"""
    print("=" * 80)
    print(f"  Blackbox Test Report  -  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    for skill, results in results_by_skill.items():
        s = summary[skill]
        print(f"\n## {skill}")
        print(f"   Tests: {s['tests']} | Errors: {s['errors']} | "
              f"Precision: {s.get('precision', 0):.2%} | "
              f"Recall: {s.get('recall', 0):.2%} | "
              f"F1: {s.get('f1', 0):.2%}")
        print("-" * 80)
        for r in results:
            if "error" in r:
                print(f"  ✗ {r['fixture']}: ERROR - {r['error'][:80]}")
            elif r.get("expected") and r["expected"][0].startswith("__"):
                marker = "✓" if r.get("precision") == 1.0 else "✗"
                print(f"  {marker} {r['fixture']}: {r['description'][:60]}")
            else:
                f1 = r.get("f1", 0)
                p = r.get("precision", 0)
                r_score = r.get("recall", 0)
                if f1 == 1.0:
                    marker = "✓"
                elif f1 >= 0.5:
                    marker = "△"
                else:
                    marker = "✗"
                print(f"  {marker} {r['fixture']}: p={p:.0%} r={r_score:.0%} f1={f1:.0%}")
                if r.get("fp"):
                    print(f"      误报: {r['fp']}")
                if r.get("fn"):
                    print(f"      漏报: {r['fn']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v0.2.0", help="skill 版本标签")
    parser.add_argument("--skill", choices=["expense", "procurement", "investigation", "all"], default="all")
    args = parser.parse_args()

    skills = ["expense", "procurement", "investigation"] if args.skill == "all" else [args.skill]
    results_by_skill = {}

    with tempfile.TemporaryDirectory(prefix="blackbox_") as tmp:
        work_dir = Path(tmp)
        for skill in skills:
            print(f"\n>> Running {skill} blackbox tests...")
            fixtures = load_fixtures(skill)
            results_by_skill[skill] = run_skill_for_skill(skill, fixtures, work_dir)

    summary = aggregate(results_by_skill)
    print_report(results_by_skill, summary)

    # 写日志
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_file = LOG_DIR / f"{timestamp}-test-{args.version}.json"
    log_data = {
        "timestamp": timestamp,
        "version": args.version,
        "summary": summary,
        "results": results_by_skill,
    }
    log_file.write_text(json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n>>> Log saved: {log_file}")

    return 0 if summary.get("all_errors", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
