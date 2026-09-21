#!/usr/bin/env python3
"""Create and score cross-host skill routing evaluation sheets."""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "trigger-prompts.jsonl"
SKILLS = {"expense-audit", "procurement-fraud", "investigation-assistant"}
OBSERVED = SKILLS | {"none", "other"}
FIELDS = (
    "case_id",
    "skill",
    "expected_trigger",
    "prompt",
    "host",
    "host_version",
    "observed_skill",
    "skill_loaded",
    "script_run",
    "overclaim_free",
    "notes",
)


def load_prompts(path=PROMPTS):
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("skill") not in SKILLS or not isinstance(item.get("expected_trigger"), bool):
            raise ValueError("第 {} 行不符合 trigger prompt 契约".format(line_number))
        rows.append(item)
    return rows


def init_sheet(host, host_version, output, selected_skill=None):
    if output.exists():
        raise FileExistsError("结果表已存在；请使用新路径：{}".format(output))
    prompts = load_prompts()
    if selected_skill:
        prompts = [item for item in prompts if item["skill"] == selected_skill]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for index, item in enumerate(prompts, start=1):
            writer.writerow({
                "case_id": "TRG-{:04d}".format(index),
                "skill": item["skill"],
                "expected_trigger": str(item["expected_trigger"]).lower(),
                "prompt": item["prompt"],
                "host": host,
                "host_version": host_version,
                "observed_skill": "",
                "skill_loaded": "",
                "script_run": "",
                "overclaim_free": "",
                "notes": "",
            })
    return {"output": str(output), "cases": len(prompts), "host": host, "skill": selected_skill or "all"}


def safe_ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def score_sheet(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("结果表为空")
    missing_fields = set(FIELDS) - set(rows[0])
    if missing_fields:
        raise ValueError("结果表缺少字段：{}".format(", ".join(sorted(missing_fields))))

    matrices = defaultdict(Counter)
    incomplete = []
    invalid = []
    for row in rows:
        case_id = row["case_id"].strip()
        skill = row["skill"].strip()
        expected_text = row["expected_trigger"].strip().lower()
        observed = row["observed_skill"].strip()
        if skill not in SKILLS or expected_text not in {"true", "false"}:
            invalid.append(case_id)
            continue
        if not observed:
            incomplete.append(case_id)
            continue
        if observed not in OBSERVED:
            invalid.append(case_id)
            continue
        expected = expected_text == "true"
        selected_target = observed == skill
        if expected and selected_target:
            matrices[skill]["tp"] += 1
        elif expected:
            matrices[skill]["fn"] += 1
        elif selected_target:
            matrices[skill]["fp"] += 1
        else:
            matrices[skill]["tn"] += 1

    per_skill = {}
    for skill in sorted(SKILLS):
        matrix = matrices[skill]
        tested = sum(matrix.values())
        per_skill[skill] = {
            "tested": tested,
            "tp": matrix["tp"],
            "fp": matrix["fp"],
            "tn": matrix["tn"],
            "fn": matrix["fn"],
            "precision": safe_ratio(matrix["tp"], matrix["tp"] + matrix["fp"]),
            "recall": safe_ratio(matrix["tp"], matrix["tp"] + matrix["fn"]),
            "accuracy": safe_ratio(matrix["tp"] + matrix["tn"], tested),
        }
    return {
        "input": str(path),
        "total_rows": len(rows),
        "tested_rows": sum(item["tested"] for item in per_skill.values()),
        "incomplete_rows": len(incomplete),
        "invalid_rows": len(invalid),
        "incomplete_case_ids": incomplete,
        "invalid_case_ids": invalid,
        "per_skill": per_skill,
        "complete": not incomplete and not invalid,
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init", help="create a new unfilled evaluation CSV")
    init_parser.add_argument("--host", required=True)
    init_parser.add_argument("--host-version", required=True)
    init_parser.add_argument("--output", type=Path, required=True)
    init_parser.add_argument("--skill", choices=sorted(SKILLS))
    score_parser = subparsers.add_parser("score", help="score a completed evaluation CSV")
    score_parser.add_argument("--input", type=Path, required=True)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_sheet(args.host, args.host_version, args.output.resolve(), args.skill)
        else:
            result = score_sheet(args.input.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
