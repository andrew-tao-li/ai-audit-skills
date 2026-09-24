#!/usr/bin/env python3
"""
构建匿名反馈内容（离线，不联网）。

读取一次关联排查的结果 JSON（cli.py 输出），组装**非敏感统计**，
以企业微信 markdown 形式打印到 stdout。由宿主 Agent 捕获后 POST 到反馈 webhook。

绝不包含主体名称、统一社会信用代码、证据细节等敏感字段——只上传：
结论状态、路径数、警告数、skill 版本、用户的备注。

用法：
  python3 scripts/cli.py --a "..." --b "..." --graph evidence.json > result.json
  python3 scripts/build_feedback.py --result result.json --rating <satisfied|neutral|unsatisfied> [--note "<用户评价>"]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RATING_LABEL = {"satisfied": "满意", "neutral": "一般", "unsatisfied": "不满意"}
NOTE_MAX_LEN = 500


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--result", required=True, help="cli.py 输出的结果 JSON 文件路径")
    p.add_argument("--rating", required=True, choices=list(RATING_LABEL), help="本次体验评级")
    p.add_argument("--note", default="", help="可选：用户的简短评价")
    args = p.parse_args()

    path = Path(args.result)
    if not path.exists():
        raise SystemExit("找不到结果 JSON：%s" % path)
    result = json.loads(path.read_text(encoding="utf-8"))

    lines = [
        "**【AI Audit 反馈】** %s v%s · %s" % (
            result.get("skill", "cn-entity-relation-check"),
            result.get("skill_version", "?"),
            RATING_LABEL.get(args.rating, args.rating),
        ),
        "",
        "- 结论状态：%s" % result.get("display_status", result.get("status", "?")),
        "- 关联路径数：%d" % len(result.get("paths", [])),
        "- 警告数：%d" % len(result.get("warnings", [])),
    ]
    if args.note.strip():
        lines.append("- 备注：%s" % args.note.strip()[:NOTE_MAX_LEN])
    lines.append("- 提交时间：`%s`" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
