#!/usr/bin/env python3
"""
OpenCode 全自动验收（跨平台验收的第 1 站）。

在真实 Agent（OpenCode）上跑一批标准用例，验证：
  1. 该触发时，Agent 是否加载了正确的 skill（skill 工具 + input.id）；
  2. 是否真的执行了 skill 的脚本（shell 命令包含预期脚本名）；
  3. 是否产生了预期的输出文件（summary.md / findings.csv / dashboard.html 等）；
  4. Agent 给用户的回答是否包含预期要点；
  5. 不该触发时，是否没有加载 skill（负向对照）。

结果写两份：
  - results/<ts>.json   机器可读（趋势分析 / 喂给 evolve.sh）
  - results/<ts>.md     人类可读（你直接看）
  - results/latest.md   永远指向最新一次

用法：
  python3 evals/cross-agent/run_acceptance.py                 # 跑全部用例
  python3 evals/cross-agent/run_acceptance.py --case expense-trigger-and-run
  python3 evals/cross-agent/run_acceptance.py --no-notify     # 不发通知
"""
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
RESULTS_DIR = HERE / "results"
CASES_FILE = HERE / "cases.json"
DEFAULT_TIMEOUT = 420  # 每个用例最多跑 7 分钟（Agent 多步 + 脚本执行）
OPENCODE = "opencode"


def parse_events(stdout: str) -> dict:
    """把 opencode run --format json 的 JSONL 解析成 {skill_calls, shell_cmds, texts}。"""
    skill_calls, shell_cmds, texts = [], [], []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "tool_use":
            part = e.get("part", {})
            tool = part.get("tool")
            st = part.get("state", {}) or {}
            inp = st.get("input", {}) or {}
            if tool == "skill":
                skill_calls.append(inp.get("id") or inp.get("name") or "")
            elif tool in ("shell", "bash"):
                cmd = inp.get("command") or inp.get("cmd") or ""
                if isinstance(cmd, list):
                    cmd = " ".join(str(x) for x in cmd)
                shell_cmds.append(str(cmd))
        elif e.get("type") == "text":
            texts.append(e.get("part", {}).get("text", ""))
    return {"skill_calls": skill_calls, "shell_cmds": shell_cmds, "texts": texts}


def check_case(case: dict, parsed: dict, outdir: Path) -> dict:
    """对单个用例做校验，返回 {passed, checks: [{name, ok, detail}]}。"""
    exp = case.get("expect", {})
    checks = []

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # 1. 该触发的 skill
    if exp.get("skill_used"):
        ok = exp["skill_used"] in parsed["skill_calls"]
        add("加载预期 skill", ok, "skill 调用=%s" % parsed["skill_calls"])

    # 2. 不该触发（负向对照）
    if exp.get("skill_not_used"):
        ok = len(parsed["skill_calls"]) == 0
        add("未加载任何 skill", ok, "skill 调用=%s" % parsed["skill_calls"])

    # 3. 是否执行了目标脚本
    if exp.get("script_ran_contains"):
        needle = exp["script_ran_contains"]
        ok = any(needle in c for c in parsed["shell_cmds"])
        add("执行了目标脚本", ok, "含 '%s'" % needle if ok else "未找到，shell=%s" % parsed["shell_cmds"][:2])

    # 4. 输出文件
    if exp.get("output_files"):
        missing = [f for f in exp["output_files"] if not (outdir / f).exists()]
        add("产出预期文件", not missing, "缺: %s" % missing if missing else "全部存在")

    # 5. 回答要点
    if exp.get("text_contains_any"):
        joined = "\n".join(parsed["texts"])
        hit = [k for k in exp["text_contains_any"] if k in joined]
        add("回答含预期要点", bool(hit), "命中: %s" % hit if hit else "未命中 %s" % exp["text_contains_any"])

    # 6. 免责/边界声明
    if exp.get("text_contains_all"):
        joined = "\n".join(parsed["texts"])
        miss = [k for k in exp["text_contains_all"] if k not in joined]
        add("回答含全部要点", not miss, "缺: %s" % miss if miss else "全部命中")

    passed = all(c["ok"] for c in checks) and len(checks) > 0
    return {"passed": passed, "checks": checks}


def run_case(case: dict, timeout: int) -> dict:
    case_id = case["id"]
    started = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="acc-%s-" % case_id) as tmp:
        outdir = Path(tmp) / "out"
        outdir.mkdir(parents=True, exist_ok=True)
        prompt = case["prompt"].replace("{outdir}", str(outdir))
        result = {"id": case_id, "skill": case.get("skill"), "prompt": prompt}
        try:
            proc = subprocess.run(
                [OPENCODE, "run", prompt, "--format", "json", "--auto"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
            )
            parsed = parse_events(proc.stdout)
            verdict = check_case(case, parsed, outdir)
            result.update({
                "exit_code": proc.returncode,
                "passed": verdict["passed"],
                "checks": verdict["checks"],
                "skill_calls": parsed["skill_calls"],
                "shell_cmds": parsed["shell_cmds"][:6],
                "answer_excerpt": ("\n".join(parsed["texts"])[:600]),
                "stderr_tail": (proc.stderr or "")[-300:],
            })
        except subprocess.TimeoutExpired:
            result.update({"passed": False, "error": "超时（%ds）" % timeout, "checks": []})
        except FileNotFoundError:
            result.update({"passed": False, "error": "找不到 opencode 可执行文件", "checks": []})
        except Exception as e:  # noqa: BLE001
            result.update({"passed": False, "error": str(e), "checks": []})
    result["duration_s"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    return result


def write_reports(results: list, ts: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": ts,
        "platform": "opencode",
        "total": len(results),
        "passed": sum(1 for r in results if r.get("passed")),
        "failed": sum(1 for r in results if not r.get("passed")),
        "results": results,
    }
    (RESULTS_DIR / ("%s.json" % ts)).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# OpenCode 全自动验收报告", "", "- 时间：%s" % ts, "- 平台：OpenCode（无头 `opencode run`）",
             "- 结果：**%d/%d 通过**" % (payload["passed"], payload["total"]), ""]
    for r in results:
        mark = "✅" if r.get("passed") else "❌"
        lines.append("## %s %s（%s，耗时 %ss）" % (mark, r["id"], r.get("skill") or "负向对照", r.get("duration_s", "?")))
        lines.append("")
        lines.append("> 提问：%s" % r.get("prompt", ""))
        lines.append("")
        if r.get("error"):
            lines.append("- ⚠ 错误：%s" % r["error"])
        for c in r.get("checks", []):
            lines.append("- %s %s%s" % ("✅" if c["ok"] else "❌", c["name"], ("；" + c["detail"]) if c.get("detail") else ""))
        if r.get("skill_calls"):
            lines.append("- skill 调用：`%s`" % r["skill_calls"])
        lines.append("")
    md = "\n".join(lines)
    (RESULTS_DIR / ("%s.md" % ts)).write_text(md, encoding="utf-8")
    (RESULTS_DIR / "latest.md").write_text(md, encoding="utf-8")
    return RESULTS_DIR / ("%s.md" % ts)


def notify(report_path: Path, results: list):
    notify_sh = ROOT / "evolution" / "notify.sh"
    if not notify_sh.exists():
        return
    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    title = "[Audit Box] OpenCode 验收 %d/%d" % (passed, len(results))
    body = "OpenCode 全自动验收结果：**%d/%d 通过**。\n\n" % (passed, len(results))
    for r in results:
        body += "- %s %s\n" % ("✅" if r.get("passed") else "❌", r["id"])
    body += "\n报告：`%s`" % report_path
    subprocess.run(["bash", str(notify_sh), title, body], cwd=str(ROOT), capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default=None, help="只跑指定用例 id")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print("找不到用例：%s" % args.case, file=sys.stderr)
            return 2

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []
    for case in cases:
        print("▶ 跑用例 %s ..." % case["id"], file=sys.stderr)
        r = run_case(case, args.timeout)
        results.append(r)
        print("  %s" % ("✅ 通过" if r.get("passed") else "❌ 未通过"), file=sys.stderr)

    report = write_reports(results, ts)
    print(str(report))
    if not args.no_notify:
        notify(report, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
