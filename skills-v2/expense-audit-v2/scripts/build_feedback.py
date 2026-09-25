#!/usr/bin/env python3
"""
构建匿名反馈内容（离线，不联网）。

读取一次审计运行的 run_manifest.json + findings.jsonl，组装**非敏感统计**，
以企业微信 markdown 形式打印到 stdout。由宿主 Agent 捕获后 POST 到反馈 webhook。

绝不包含员工、供应商、发票号、金额、币种、事由等任何敏感字段——只上传：
发现数、发现类型计数、风险优先级分布、跳过的规则、警告、skill 版本、本轮耗时、用户的备注。

用法：
  python3 scripts/build_feedback.py --output <审计输出目录> --rating <satisfied|neutral|unsatisfied> [--note "<用户评价>"]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RATING_LABEL = {"satisfied": "满意", "neutral": "一般", "unsatisfied": "不满意"}

# 风险等级英文 → 中文
PRIORITY_ZH = {"critical": "严重", "high": "高风险", "medium": "中风险", "low": "低风险"}

# finding_type 英文 key → 中文显示名（与 dashboard 一致）
TYPE_ZH = {
    "exact-duplicate-invoice": "发票号重复",
    "exact-duplicate-employee-date-amount": "同员工同日同金额",
    "near-duplicate": "金额近似",
    "policy-threshold": "超制度上限",
    "split-expense": "拆单报销",
    "weekend-signal": "周末消费",
    "holiday-signal": "节假日消费",
    "robust-outlier": "异常高额",
    "self-approval": "自审自批",
    "cross-employee-invoice": "发票跨人复用",
    "submit-before-expense": "提交早于消费",
    "future-date": "未来日期",
    "missing-expense-type": "缺费用类型",
    "sequential-invoice": "发票连号",
    "invoice-format-anomaly": "发票格式异常",
    "large-amount-low-level-approval": "大额低层级审批",
    "space-time-conflict": "时空冲突",
    "cross-period": "跨期入账",
    "high-frequency-small-amount": "高频小额",
}

# 单条消息 body 上限 ~4 KB；留余地
NOTE_MAX_LEN = 500


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


def duration_seconds(manifest: dict):
    """从 run_manifest 算本轮耗时（秒），缺失字段返回 None。"""
    try:
        s = datetime.fromisoformat(manifest["started_at"])
        f = datetime.fromisoformat(manifest["finished_at"])
    except (KeyError, ValueError):
        return None
    delta = (f - s).total_seconds()
    return round(delta, 1)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True, help="审计输出目录")
    p.add_argument("--rating", required=True, choices=list(RATING_LABEL), help="本次体验评级")
    p.add_argument("--note", default="", help="可选：用户的简短评价（如「速度偏慢」「结果不错」）")
    args = p.parse_args()

    out = Path(args.output)
    manifest = load_manifest(out)
    finding_stats = count_findings(out)
    duration = duration_seconds(manifest)

    lines = [
        "**【AI Audit 反馈】** %s v%s · %s" % (
            manifest.get("skill", "?"), manifest.get("skill_version", "?"),
            RATING_LABEL.get(args.rating, args.rating),
        ),
        "",
        "- Findings：%d" % finding_stats["total"],
        "- 发现类型：`%s`" % json.dumps({TYPE_ZH.get(k, k): v for k, v in finding_stats["by_type"].items()}, ensure_ascii=False),
        "- 风险分布：`%s`" % json.dumps({PRIORITY_ZH.get(k, k): v for k, v in finding_stats["by_priority"].items()}, ensure_ascii=False),
    ]
    if duration is not None:
        lines.append("- 耗时：%s 秒" % duration)
    skipped = manifest.get("skipped_rules", [])
    warnings = manifest.get("warnings", [])
    if skipped:
        lines.append("- 跳过规则：`%s`" % json.dumps(skipped, ensure_ascii=False))
    if warnings:
        lines.append("- 警告：`%s`" % json.dumps(warnings, ensure_ascii=False))
    if args.note.strip():
        lines.append("- 备注：%s" % args.note.strip()[:NOTE_MAX_LEN])
    lines.append("- 提交时间：`%s`" % datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
