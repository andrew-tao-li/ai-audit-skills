#!/usr/bin/env python3
"""
审计师场景覆盖率评分器（行级 ground truth）。

背景：真实审计师提供了一份「带标准答案」的出差费用数据（出差费用模拟数据.xlsx），
其中「审计说明」工作表明确植入了 16 个异常场景及对应费用编号。

本脚本：
  1. 用 audit_config.json 跑 expense-audit-v2 对 data.csv 做全量扫描；
  2. 通过 evidence.jsonl 把 finding 回溯到具体费用编号（行级，而非仅 finding_type 级）；
  3. 对照 ground-truth.json 的 16 个场景，报告「哪些场景被命中、哪些漏掉」。

用法：python3 evals/blackbox/expense/auditor-scenario/score_coverage.py
"""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SCENARIO_DIR = Path(__file__).resolve().parent
SCRIPT = ROOT / "skills-v2" / "expense-audit-v2" / "scripts" / "run_expense_audit.py"


def run_skill(work_dir: Path) -> Path:
    """跑 skill，返回输出目录。"""
    out = work_dir / "output"
    r = subprocess.run(
        ["python3", str(SCRIPT),
         "--input", str(SCENARIO_DIR / "data.csv"),
         "--policy", str(SCENARIO_DIR / "audit_config.json"),
         "--output", str(out)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("运行失败:", r.stderr[:500], file=sys.stderr)
        raise SystemExit(1)
    return out


def load_evidence_expense_map(out: Path) -> dict:
    """evidence_id -> expense_id（只取 field == expense_id 的条目）。"""
    m = {}
    ev_file = out / "evidence.jsonl"
    if ev_file.exists():
        for line in ev_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("field") == "expense_id":
                m[e["evidence_id"]] = e.get("value")
    return m


def load_findings(out: Path, ev2exp: dict) -> list:
    """返回 [{finding_type, expense_ids: set}]。"""
    findings = []
    f_file = out / "findings.jsonl"
    if not f_file.exists():
        return findings
    for line in f_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        f = json.loads(line)
        ids = set()
        for ref in f.get("evidence_refs", []):
            if ref in ev2exp:
                ids.add(ev2exp[ref])
        findings.append({
            "finding_type": f.get("finding_type"),
            "expense_ids": ids,
        })
    return findings


def load_bad_rows(out: Path) -> set:
    """bad_rows.csv 里被隔离的 expense_id 集合。

    bad_rows.csv 的结构是 source_row + reasons + raw_record（raw_record 是 JSON 字符串，
    内含 expense_id）。这里解析 raw_record 提取 expense_id。
    """
    ids = set()
    bf = out / "bad_rows.csv"
    if bf.exists():
        with bf.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw = row.get("raw_record", "")
                if raw:
                    try:
                        rec = json.loads(raw)
                        if rec.get("expense_id"):
                            ids.add(rec["expense_id"])
                    except json.JSONDecodeError:
                        pass
    return ids


def main() -> int:
    gt = json.loads((SCENARIO_DIR / "ground-truth.json").read_text(encoding="utf-8"))
    scenarios = gt["scenarios"]

    with tempfile.TemporaryDirectory(prefix="auditor_scenario_") as tmp:
        out = run_skill(Path(tmp))
        ev2exp = load_evidence_expense_map(out)
        findings = load_findings(out, ev2exp)
        bad_rows = load_bad_rows(out)

    # 构建：expense_id -> 命中的 finding_types
    id2types = {}
    for f in findings:
        for eid in f["expense_ids"]:
            id2types.setdefault(eid, set()).add(f["finding_type"])

    print("=" * 78)
    print("  审计师场景覆盖率（行级 ground truth）")
    print("  source:", gt["source"])
    print("=" * 78)

    detected = 0
    rows_out = []
    for s in scenarios:
        sid = s["id"]
        eids = s["expense_ids"]
        expected = s["expected_finding_type"]
        status = s["rule_status"]

        if status == "data-quality":
            # #12：EXP-0802 应进 bad_rows，EXP-0803 应被某规则命中
            quarantined = [e for e in eids if e in bad_rows]
            hit = [e for e in eids if e in id2types]
            ok = bool(quarantined) and bool(hit)
            mark = "✓" if ok else "△"
            if ok:
                detected += 1
            rows_out.append(f"  {mark} #{sid:2d} {s['category']:24s} 隔离={quarantined} 命中类型={ {e: sorted(id2types.get(e,[])) for e in hit} }")
            continue

        if expected is None or status == "not-implemented":
            # 未实现规则：预期必漏
            hit_types = {e: sorted(id2types.get(e, [])) for e in eids if e in id2types}
            rows_out.append(f"  ✗ #{sid:2d} {s['category']:24s} [规则未实现:{expected}] 间接命中={hit_types}")
            continue

        # 正常场景：expected type 是否命中任一 expense_id
        matched = [e for e in eids if expected in id2types.get(e, set())]
        other = [e for e in eids if e in id2types and expected not in id2types[e]]
        ok = bool(matched)
        if ok:
            detected += 1
            mark = "✓"
        else:
            mark = "✗" if status == "implemented" else "△"
        extra = f"  另有其他类型命中={other}" if other else ""
        rows_out.append(f"  {mark} #{sid:2d} {s['category']:24s} 期望={expected} 命中={matched}{extra}")

    print("\n".join(rows_out))
    print("-" * 78)

    total = len(scenarios)
    not_impl = [s for s in scenarios if s["rule_status"] == "not-implemented"]
    config_gated = [s for s in scenarios if s["rule_status"] == "config-gated"]
    implemented = [s for s in scenarios if s["rule_status"] == "implemented"]
    dq = [s for s in scenarios if s["rule_status"] == "data-quality"]

    print(f"  场景总数: {total}")
    print(f"  已检出: {detected}/{total}")
    print(f"  ├─ 已实现规则(应全检出): {len(implemented)} 个")
    print(f"  ├─ 配置驱动规则(配 config 后应检出): {len(config_gated)} 个")
    print(f"  ├─ 数据质量(隔离+命中): {len(dq)} 个")
    print(f"  └─ 未实现规则(当前必漏 → 新规则目标): {len(not_impl)} 个")
    print()
    print("  未实现规则（下一步补）:")
    for s in not_impl:
        print(f"    - {s['category']} → 建议新规则 {s['expected_finding_type']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
