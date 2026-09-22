#!/usr/bin/env python3
"""
A/B 测试护栏（L2.3）：改动前快照分数，改动后跑测试对比，F1 退步则报告 / 自动回滚。

用法：
    python3 evolution/guardrail.py baseline            # 快照当前 git HEAD + 分数
    python3 evolution/guardrail.py verify              # 跑测试对比；退步则退出码 1（不修改任何东西）
    python3 evolution/guardrail.py verify --rollback   # 退步时自动回滚到 baseline 的 git HEAD

语义：
    - baseline：跑一遍黑盒测试，把「git HEAD + 每 skill 的 F1/P/R + 每个 fixture 的结果」存到
      evolution/guardrail/baseline.json。
    - verify：再跑一遍测试，与 baseline 逐 skill 对比 F1：
        * 任何一个 skill 的 F1 下降（超过 1e-6）即判为「退步」（regression）。
        * 默认只报告、退出码 1，不碰代码。
        * --rollback 时：确认 baseline 的 git HEAD 是当前 HEAD 的祖先后，执行
          `git reset --hard <baseline_head>` 丢弃改动，并重跑测试确认分数回到 baseline。
    - 无论退步与否，都会把 before/after 分数记进 evolution/state.json 的 guardrail_history。

设计约束（对应 docs 的 Pareto 改进理念）：
    改动必须「不牺牲原有优点 + 让能力更强」——所以任何 skill 的 F1 都不允许退步。
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "evolution" / "log"
STATE_FILE = ROOT / "evolution" / "state.json"
GUARD_DIR = ROOT / "evolution" / "guardrail"
BASELINE_FILE = GUARD_DIR / "baseline.json"

VERSION = "v0.2.0-baseline"
SKILLS = ["expense", "procurement", "investigation"]
EPS = 1e-6


def git(args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {r.stderr.strip()}")
    return r


def run_tests():
    """跑一遍黑盒测试，返回最新 log 的 JSON（summary + results）。"""
    subprocess.run(
        ["python3", "evals/blackbox/score_blackbox.py", "--version", VERSION],
        cwd=ROOT, capture_output=True, text=True,
    )
    logs = sorted(LOG_DIR.glob(f"*-test-{VERSION}.json"))
    if not logs:
        raise SystemExit("ERROR: 未找到评分日志，先确保 score_blackbox.py 能正常产出 log")
    return json.loads(logs[-1].read_text(encoding="utf-8"))


def fixture_map(log):
    """从 log 的 results 里抽出 {skill: {fixture: f1 或 "error"}}，用于逐 fixture 对比。"""
    out = {}
    for skill, results in log.get("results", {}).items():
        out[skill] = {}
        for r in results:
            if "error" in r:
                out[skill][r["fixture"]] = "error"
            else:
                out[skill][r["fixture"]] = round(r.get("f1", 0.0), 6)
    return out


def snapshot(log):
    """把原始评分 log 归一成 {scores, fixtures} 的可比快照。"""
    return {
        "scores": log["summary"],
        "fixtures": fixture_map(log),
    }


def compare(before, after):
    """对比 before/after 的 summary 与 fixtures，返回 (rows, regressed)。"""
    rows = []
    regressed = False
    b_sum = before["scores"]
    a_sum = after["scores"]
    b_fix = before.get("fixtures", {})
    a_fix = after.get("fixtures", {})

    for skill in SKILLS:
        b = b_sum.get(skill, {})
        a = a_sum.get(skill, {})
        b_f1 = b.get("f1", 0.0)
        a_f1 = a.get("f1", 0.0)
        delta = round(a_f1 - b_f1, 6)
        if delta < -EPS:
            status = "REGRESSED"
            regressed = True
        elif delta > EPS:
            status = "improved"
        else:
            status = "same"
        rows.append({
            "skill": skill,
            "before_f1": round(b_f1, 4),
            "after_f1": round(a_f1, 4),
            "delta": delta,
            "status": status,
            "before_p": round(b.get("precision", 0), 4),
            "after_p": round(a.get("precision", 0), 4),
            "before_r": round(b.get("recall", 0), 4),
            "after_r": round(a.get("recall", 0), 4),
        })

        # 逐 fixture 变化：f1 从「通过」变「不通过/报错」= 破坏；反之 = 修复
        bf = b_fix.get(skill, {})
        af = a_fix.get(skill, {})
        broken = []
        fixed = []
        for f in set(bf) | set(af):
            bv = bf.get(f)
            av = af.get(f)
            b_bad = bv == "error" or (isinstance(bv, float) and bv < 1.0 - EPS)
            a_bad = av == "error" or (isinstance(av, float) and av < 1.0 - EPS)
            if not b_bad and a_bad:
                broken.append(f)
            elif b_bad and not a_bad:
                fixed.append(f)
        if broken:
            rows[-1]["broken_fixtures"] = sorted(broken)
            regressed = True
        if fixed:
            rows[-1]["fixed_fixtures"] = sorted(fixed)

    return rows, regressed


def record_state(before, after, verdict, rolled_back=False):
    """把 before/after 记录进 state.json 的 guardrail_history。"""
    if not STATE_FILE.exists():
        return
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    entry = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": verdict,
        "rolled_back": rolled_back,
        "before": before["scores"],
        "after": after["scores"],
    }
    state.setdefault("guardrail_history", []).append(entry)
    # 只保留最近 50 条，避免无限增长
    state["guardrail_history"] = state["guardrail_history"][-50:]
    state["last_modified"] = entry["checked_at"]
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_baseline():
    print("▶ 跑测试以建立基线…")
    log = run_tests()
    head = git(["rev-parse", "HEAD"]).stdout.strip()
    snap = snapshot(log)
    baseline = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_head": head,
        "version": VERSION,
        "scores": snap["scores"],
        "fixtures": snap["fixtures"],
    }
    GUARD_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ 基线已保存: {BASELINE_FILE}")
    print(f"  git HEAD: {head[:12]}")
    for skill in SKILLS:
        s = baseline["scores"].get(skill, {})
        print(f"  {skill:15s} F1={s.get('f1', 0):.4f}  P={s.get('precision', 0):.4f}  R={s.get('recall', 0):.4f}")


def cmd_verify(rollback=False):
    if not BASELINE_FILE.exists():
        raise SystemExit("ERROR: 无基线。请先运行 `python3 evolution/guardrail.py baseline`")
    before = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))

    print("▶ 跑测试以验证…")
    after = snapshot(run_tests())

    rows, regressed = compare(before, after)

    print("\n===== A/B 对比 =====")
    for r in rows:
        print(f"  {r['skill']:15s} F1 {r['before_f1']:.4f} → {r['after_f1']:.4f} "
              f"({r['delta']:+.4f})  [{r['status']}]")
        if "broken_fixtures" in r:
            print(f"      破坏的 fixture: {r['broken_fixtures']}")
        if "fixed_fixtures" in r:
            print(f"      修复的 fixture: {r['fixed_fixtures']}")

    if not regressed:
        print("\n✓ PASS：无任何 skill 的 F1 退步。")
        record_state(before, after, "pass")
        return 0

    print("\n✗ FAIL：检测到 F1 退步。")
    if not rollback:
        print("  未回滚（未指定 --rollback）。要回滚请运行：")
        print(f"  python3 evolution/guardrail.py verify --rollback")
        record_state(before, after, "regressed")
        return 1

    # 回滚：只把「技能代码目录」恢复到基线，不动 HEAD，也不动 state.json / log / proposals 等数据
    #（避免 reset --hard 把护栏自己的审计轨迹也一并抹掉）
    head = git(["rev-parse", "HEAD"]).stdout.strip()
    base_head = before["git_head"]
    print(f"  回滚范围：skills-v2 skills（基线 {base_head[:12]}）")
    print("  → git checkout <baseline> -- skills-v2 skills")
    git(["checkout", base_head, "--", "skills-v2", "skills"])
    if base_head != head:
        print(f"  注：代码已恢复到基线，但 HEAD 仍在 {head[:8]}；"
              f"如需彻底丢弃其上提交：git reset --hard {base_head[:12]}")
    print("  → 重跑测试确认…")
    after_rollback = snapshot(run_tests())
    rows2, regressed2 = compare(before, after_rollback)
    if regressed2:
        print("  ✗ 回滚后仍未恢复到基线分数，请人工检查。")
        record_state(before, after_rollback, "rollback_failed", rolled_back=True)
        return 1
    print("  ✓ 已回滚，分数恢复到基线。")
    record_state(before, after_rollback, "rollback", rolled_back=True)
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["baseline", "verify"])
    p.add_argument("--rollback", action="store_true", help="verify 检测到退步时自动回滚")
    args = p.parse_args()
    if args.command == "baseline":
        sys.exit(cmd_baseline())
    sys.exit(cmd_verify(rollback=args.rollback))


if __name__ == "__main__":
    main()
