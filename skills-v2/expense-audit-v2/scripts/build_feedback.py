#!/usr/bin/env python3
"""
构建匿名反馈内容（离线，不联网）。

读取一次审计运行的 run_manifest.json + findings.jsonl，组装**非敏感统计**，
以企业微信 markdown 形式打印到 stdout。由宿主 Agent 捕获后 POST 到反馈 webhook。

绝不包含员工、供应商、发票号、金额、币种、事由等任何敏感字段——只上传：
发现数、发现类型计数、风险优先级分布、跳过的规则、警告、skill 版本。

用法：
  python3 scripts/build_feedback.py --output <审计输出目录> --rating <satisfied|neutral|unsatisfied>
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RATING_LABEL = {"satisfied": "满意", "neutral": "一般", "unsatisfied": "不满意"}


def load_manifest(out: Path) -> dict:
    m = out / "run_manifest.json"
    if not m.exists():
        raise SystemExit("找不到 run_manifest.json，请确认 --output 指向审计输出目录")
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, help="审计输出目录")
    p.add_argument("--rating", required=True, choices=list(RATING_LABEL))
    args = p.parse_args()

    out = Path(args.output)
    manifest = load_manifest(out)
    finding_stats = count_findings(out)

    lines = [
        "**【AI Audit 反馈】** %s v%s · %s" % (
            manifest.get("skill", "?"), manifest.get("skill_version", "?"),
            RATING_LABEL.get(args.rating, args.rating),
        ),
        "",
        "- Findings：%d" % finding_stats["total"],
        "- 发现类型：`%s`" % json.dumps(finding_stats["by_type"], ensure_ascii=False),
        "- 风险分布：`%s`" % json.dumps(finding_stats["by_priority"], ensure_ascii=False),
    ]
    skipped = manifest.get("skipped_rules", [])
    warnings = manifest.get("warnings", [])
    if skipped:
        lines.append("- 跳过规则：`%s`" % json.dumps(skipped, ensure_ascii=False))
    if warnings:
        lines.append("- 警告：`%s`" % json.dumps(warnings, ensure_ascii=False))
    lines.append("- 提交时间：`%s`" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
