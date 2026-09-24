#!/usr/bin/env python3
"""
构建匿名反馈内容（离线，不联网）。

读取一次调查工作空间的 run_manifest.json + findings.jsonl，组装**非敏感统计**，
以企业微信 markdown 形式打印到 stdout。由宿主 Agent 捕获后 POST 到反馈 webhook。

绝不包含案卷内容、当事人姓名、IP、邮箱、门禁号等任何敏感字段——只上传：
finding 数、类型计数、风险优先级分布、警告、skill 版本、本轮耗时、用户的备注。

用法：
  python3 scripts/build_feedback.py --output <工作空间目录> --rating <satisfied|neutral|unsatisfied> [--note "<用户评价>"]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RATING_LABEL = {"satisfied": "满意", "neutral": "一般", "unsatisfied": "不满意"}
NOTE_MAX_LEN = 500


def load_manifest(out: Path) -> dict:
    m = out / "run_manifest.json"
    if not m.exists():
        raise SystemExit("找不到 run_manifest.json，请确认 --output 指向工作空间目录")
    return json.loads(m.read_text(encoding="utf-8"))


def count_findings(out: Path) -> dict:
    counts = {}
    priorities = {}
    total = 0
    f = out / "findings.jsonl"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fd = json.loads(line)
            total += 1
            t = fd.get("finding_type", "?")
            counts[t] = counts.get(t, 0) + 1
            p = fd.get("risk_priority", "?")
            priorities[p] = priorities.get(p, 0) + 1
    return {"total": total, "by_type": counts, "by_priority": priorities}


def duration_seconds(manifest: dict):
    try:
        s = datetime.fromisoformat(manifest["started_at"])
        f = datetime.fromisoformat(manifest["finished_at"])
    except (KeyError, ValueError):
        return None
    return round((f - s).total_seconds(), 1)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, help="工作空间目录")
    p.add_argument("--rating", required=True, choices=list(RATING_LABEL), help="本次体验评级")
    p.add_argument("--note", default="", help="可选：用户的简短评价")
    args = p.parse_args()

    out = Path(args.output)
    manifest = load_manifest(out)
    stats = count_findings(out)
    dur = duration_seconds(manifest)

    lines = [
        "**【AI Audit 反馈】** %s v%s · %s" % (
            manifest.get("skill", "?"), manifest.get("skill_version", "?"),
            RATING_LABEL.get(args.rating, args.rating),
        ),
        "",
        "- Findings：%d" % stats["total"],
        "- 发现类型：`%s`" % json.dumps(stats["by_type"], ensure_ascii=False),
        "- 风险分布：`%s`" % json.dumps(stats["by_priority"], ensure_ascii=False),
    ]
    if dur is not None:
        lines.append("- 耗时：%s 秒" % dur)
    warnings = manifest.get("warnings", [])
    if warnings:
        lines.append("- 警告：`%s`" % json.dumps(warnings, ensure_ascii=False))
    if args.note.strip():
        lines.append("- 备注：%s" % args.note.strip()[:NOTE_MAX_LEN])
    lines.append("- 提交时间：`%s`" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
