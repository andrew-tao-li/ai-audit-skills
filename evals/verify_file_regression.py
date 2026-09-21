#!/usr/bin/env python3
"""Independently verify file-regression outputs produced by an Agent host."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = PACK_ROOT / "evals" / "fixtures"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def classify(manifest):
    skill = manifest.get("skill")
    parameters = manifest.get("parameters", {})
    if skill == "expense-audit":
        version = parameters.get("policy_version", "")
        if "CLEAN" in version:
            return "expense-clean"
        if "DIRTY" in version:
            return "expense-dirty"
    if skill == "procurement-fraud":
        version = parameters.get("config_version", "")
        if "CLEAN" in version:
            return "procurement-clean"
        if "DIRTY" in version:
            return "procurement-dirty"
    if skill == "investigation-assistant" and manifest.get("case_id") == "CASE-SYNTHETIC-SCOPE-001":
        return "investigation-scope"
    return None


def discover(root, errors):
    scenarios = {}
    for path in root.rglob("run_manifest.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        scenario = classify(manifest)
        if not scenario:
            continue
        if scenario in scenarios:
            errors.append("场景 %s 出现多个 manifest：%s 与 %s" % (scenario, scenarios[scenario][0], path))
            continue
        scenarios[scenario] = (path.parent, manifest)
    return scenarios


def verify_expense(name, output, manifest, errors):
    fixture_name = "clean-control" if name == "expense-clean" else "dirty-input"
    expected = json.loads((FIXTURES / "expense-audit" / fixture_name / "expectations.json").read_text(encoding="utf-8"))
    clean = read_csv(output / "clean_expenses.csv")
    bad = read_csv(output / "bad_rows.csv")
    findings = read_jsonl(output / "findings.jsonl")
    evidence = read_jsonl(output / "evidence.jsonl")
    require(len(clean) == expected["expected_valid_rows"], "%s valid_rows 不符" % name, errors)
    require(len(bad) == expected["expected_bad_rows"], "%s bad_rows 不符" % name, errors)
    require(len(findings) == expected["expected_findings"], "%s findings 不符" % name, errors)
    if "expected_evidence" in expected:
        require(len(evidence) == expected["expected_evidence"], "%s evidence 不符" % name, errors)
    require(manifest.get("network_access") is False, "%s network_access 不是 false" % name, errors)
    if name == "expense-clean":
        require(manifest.get("field_mapping", {}).get("expense_id") == "费用编号", "expense-clean 未识别中文费用编号", errors)
        require(manifest.get("parameters", {}).get("policy_version") == expected["required_policy_version"], "expense-clean policy_version 不符", errors)
    else:
        require(clean[1].get("currency") == expected["expected_defaulted_currency"], "expense-dirty 缺失币种未默认 CNY", errors)
        reasons = "\n".join(row["reasons"] for row in bad)
        for reason in expected["required_bad_row_reasons"]:
            require(reason in reasons, "expense-dirty 缺少坏行原因：%s" % reason, errors)


def verify_procurement(name, output, manifest, errors):
    fixture_name = "clean-control" if name == "procurement-clean" else "dirty-input"
    expected = json.loads((FIXTURES / "procurement-fraud" / fixture_name / "expectations.json").read_text(encoding="utf-8"))
    findings = read_jsonl(output / "findings.jsonl")
    bad = read_csv(output / "bad_rows.csv")
    handoff = json.loads((output / "investigation_handoff.json").read_text(encoding="utf-8"))
    require(len(findings) == expected["expected_findings"], "%s findings 不符" % name, errors)
    require(len(bad) == expected["expected_bad_rows"], "%s bad_rows 不符" % name, errors)
    require(handoff.get("status") == expected["expected_handoff_status"], "%s handoff 状态不符" % name, errors)
    require(manifest.get("network_access") is False, "%s network_access 不是 false" % name, errors)
    if name == "procurement-clean":
        loaded = {item["table"] for item in manifest.get("input_files", []) if item.get("table") != "config"}
        require(loaded == set(expected["expected_loaded_tables"]), "procurement-clean loaded_tables 不符", errors)
    else:
        reasons = "\n".join(row["reasons"] for row in bad)
        for reason in expected["required_bad_row_reasons"]:
            require(reason in reasons, "procurement-dirty 缺少坏行原因：%s" % reason, errors)
        for table, count in expected["expected_valid_rows"].items():
            require(len(read_csv(output / ("normalized_%s.csv" % table))) == count, "procurement-dirty %s 有效行数不符" % table, errors)
        skipped = manifest.get("skipped_modules", [])
        for table in expected["expected_not_provided_tables"]:
            require(table + " 模块：未提供输入" in skipped, "procurement-dirty 未记录缺失表：%s" % table, errors)
            require(not (output / ("normalized_%s.csv" % table)).exists(), "procurement-dirty 意外生成可选表：%s" % table, errors)


def verify_investigation(output, manifest, errors):
    expected = json.loads((FIXTURES / "investigation-assistant" / "scope-filter" / "expectations.json").read_text(encoding="utf-8"))
    require(len(read_csv(output / "timeline.csv")) == expected["expected_timeline_rows"], "investigation-scope timeline_rows 不符", errors)
    require(len(read_csv(output / "out_of_scope_rows.csv")) == expected["expected_out_of_scope_rows"], "investigation-scope out_of_scope_rows 不符", errors)
    require(len(read_jsonl(output / "findings.jsonl")) == expected["expected_findings"], "investigation-scope findings 不符", errors)
    require(len(read_csv(output / "evidence_matrix.csv")) == expected["expected_issue_rows"], "investigation-scope issue_rows 不符", errors)
    inventory = read_jsonl(output / "evidence_inventory.jsonl")
    require(len(inventory) == expected["expected_raw_files"], "investigation-scope raw_files 不符", errors)
    fixture = FIXTURES / "investigation-assistant" / "scope-filter"
    for item in inventory:
        source = fixture / item["relative_path"]
        raw_copy = output / "evidence" / "raw" / item["relative_path"]
        require(sha256(source) == sha256(raw_copy), "investigation-scope hash 不符：%s" % item["relative_path"], errors)
        require(raw_copy.stat().st_mode & 0o222 == 0, "investigation-scope raw 非只读：%s" % item["relative_path"], errors)
    require(manifest.get("network_access") is False, "investigation-scope network_access 不是 false", errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="host file-regression output root")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = []
    require(root.is_dir(), "输出根目录不存在：%s" % root, errors)
    scenarios = discover(root, errors) if root.is_dir() else {}
    expected_scenarios = {"expense-clean", "expense-dirty", "procurement-clean", "procurement-dirty", "investigation-scope"}
    require(set(scenarios) == expected_scenarios, "成功场景集合不符：%s" % sorted(scenarios), errors)
    for name, (output, manifest) in scenarios.items():
        if name.startswith("expense-"):
            verify_expense(name, output, manifest, errors)
        elif name.startswith("procurement-"):
            verify_procurement(name, output, manifest, errors)
        else:
            verify_investigation(output, manifest, errors)
    denied_names = ["investigation-assistant-authorization-denied", "investigation-authorization-denied", "investigation-denied", "authorization-denied"]
    for name in denied_names:
        require(not (root / name).exists(), "未授权场景不应创建输出目录：%s" % name, errors)
    result = {
        "root": str(root),
        "status": "fail" if errors else "pass",
        "verified_scenarios": sorted(scenarios),
        "authorization_denied_output_absent": not any((root / name).exists() for name in denied_names),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
