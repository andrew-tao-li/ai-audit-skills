#!/usr/bin/env python3
"""
LLM 自主出题 — 双引擎之一

原理：
  你是审计师。结合你的经验 + 公开知识 + 最新新闻，
  生成真实的费用/采购/调查场景 fixture。
  跟"特斯拉 FSD 用模拟路况测自动驾驶"一个思路。

用法：
  export MINIMAX_API_KEY="sk-cp-..."
  python3 evolution/scenario_generator.py --count 10 --domain expense
  python3 evolution/scenario_generator.py --count 5 --domain procurement --focus "中国制造业 2024 趋势"

输出：
  evals/blackbox/scenarios/auto-<timestamp>-<domain>-<n>.csv
  evals/blackbox/scenarios/auto-<timestamp>-<domain>-<n>.json  (ground truth)

后续：
  真实审计师 review + 选入黄金测试集
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# 允许从仓库根目录或 evolution/ 目录运行
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals" / "blackbox"))

from call_llm import get_api_key, call_llm


# ============== 领域知识（让 LLM 更准） ==============

DOMAIN_CONTEXT = {
    "expense": {
        "name": "费用审计",
        "skill": "expense-audit",
        "fields": ["expense_id","employee_id","department","expense_type","expense_date","submit_date","amount","currency","vendor_name","invoice_number","approver","business_purpose"],
        "finding_types": [
            "exact-duplicate-invoice（精确重复发票）",
            "exact-duplicate-employee-date-amount（同员工同日同金额）",
            "near-duplicate（近重复，金额微调）",
            "policy-threshold（超制度上限）",
            "split-expense（拆单规避审批）",
            "weekend-signal（周末消费弱信号）",
            "holiday-signal（节假日消费弱信号）",
            "robust-outlier（MAD 统计离群）",
            "self-approval（自审自批）",
            "cross-employee-invoice（发票跨人复用）",
            "submit-before-expense（提交日期倒挂）",
            "future-date（费用日期在未来）",
            "missing-expense-type（缺费用类型）",
            "sequential-invoice（连号发票）",
            "invoice-format-anomaly（格式异常）",
            "large-amount-low-level-approval（大额低层级审批）",
        ],
    },
    "procurement": {
        "name": "采购审计",
        "skill": "procurement-fraud",
        "fields": "见 procurement-fraud 的数据合同（多个表）",
        "finding_types": [
            "shared-bank-account（供应商共享对公账户）",
            "shared-phone/email/address/legal-representative（共享其他属性）",
            "employee-vendor-shared-phone（员工与供应商关联）",
            "price-outlier（价格离群）",
            "split-order（拆单）",
            "bid-text-similarity（投标文本雷同）",
            "bid-price-subcluster（报价子簇异常）",
            "new-vendor-large-order（新供应商接大单）",
            "overpayment（超额付款）",
            "payment-before-order（付款早于下单）",
            "process-receipt-before-approval（收货早于审批）",
        ],
    },
    "investigation": {
        "name": "调查",
        "skill": "investigation-assistant",
        "fields": "需要 scope.json + 举报信 + messages.csv + logs.csv",
        "finding_types": [
            "scope_filter（人员/日期越界排除）",
            "supporting_evidence（支持证据）",
            "contradictory_evidence（反证）",
            "missing_evidence（缺失证据）",
            "investigation-lead（待复核线索）",
        ],
    },
}


# ============== 主 prompt ==============

SCENARIO_GENERATION_PROMPT = """你是资深的中国民营制造业审计师。

生成 {count} 个真实的{domain_label}场景。

## 已知 finding 类型
{domain_finding_types}

## 已有 fixture（请避免重复）
{existing_fixtures}

## 要求
1. 真实可信（中国民营制造业常见金额、商户、日期）
2. 每个场景明确"应该触发"和"不应触发"的 finding
3. 难度：简单/中等/困难 各 1/3

## 额外关注
{focus_or_none}

## 输出 JSON（**严格按格式，不要解释**）
{{"scenarios": [{{"id": "scenario-{{n}}", "title": "...", "description": "...", "difficulty": "简单", "expected_findings": ["..."], "not_expected_findings": ["..."], "data_preview": {{"field": "value"}}, "business_scenario": "..."}}]}}
"""


# ============== 关键函数 ==============

def build_prompt(domain: str, count: int, focus: str = "") -> str:
    """批量生成的 prompt（实际未用，保留备用）"""
    ctx = DOMAIN_CONTEXT[domain]
    fixture_dir = ROOT / "evals" / "blackbox" / ctx["skill"] / "fixtures"
    existing = [f.stem for f in fixture_dir.iterdir() if f.suffix == ".csv"] if fixture_dir.exists() else []

    return SCENARIO_GENERATION_PROMPT.format(
        count=count,
        domain=domain,
        domain_label=ctx["name"],
        domain_context=json.dumps(ctx, ensure_ascii=False, indent=2),
        domain_finding_types="\n".join(f"- {ft}" for ft in ctx["finding_types"]),
        existing_fixtures=", ".join(existing[:10]) if existing else "（无）",
        focus_or_none=focus if focus else "（无特定关注，按你认为重要的来）",
    )


def parse_json_output(raw: str) -> dict:
    """从 LLM 输出中提取 JSON（容忍 markdown 包装）"""
    # 去掉可能的 markdown 包装
    text = raw.strip()
    if text.startswith("```"):
        # 去掉开头和结尾的 ```
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```"))
    # 找第一个 { 和最后一个 }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end+1]
    return json.loads(text)


def generate_scenarios(domain: str, count: int, focus: str = "") -> list:
    """循环生成多个场景（每次 1 个，避免 token 截断）"""
    all_scenarios = []
    for i in range(count):
        prompt = build_prompt_one(domain, i + 1, focus)
        try:
            raw = call_llm(prompt, max_tokens=1500, temperature=0.7)
            parsed = parse_json_output(raw)
            scenarios = parsed.get("scenarios", [parsed])
            if scenarios:
                all_scenarios.extend(scenarios if isinstance(scenarios, list) else [scenarios])
        except Exception as e:
            print(f"  ⚠ 第 {i+1} 个场景生成失败: {e}", file=sys.stderr)
    return all_scenarios


def build_prompt_one(domain: str, n: int, focus: str = "") -> str:
    """生成单个场景的 prompt（比多场景更稳）"""
    ctx = DOMAIN_CONTEXT[domain]
    fixture_dir = ROOT / "evals" / "blackbox" / ctx["skill"] / "fixtures"
    existing = [f.stem for f in fixture_dir.iterdir() if f.suffix == ".csv"] if fixture_dir.exists() else []

    return f"""你是资深中国民营制造业审计师。生成 1 个真实的{ctx["name"]}场景。

## 已知 finding 类型
{chr(10).join(f"- {ft}" for ft in ctx["finding_types"])}

## 已有 fixture（请避免重复）
{", ".join(existing[:10]) if existing else "（无）"}

## 额外关注
{focus if focus else "（无）"}

## 难度
{random_difficulty(n)}

## 输出 JSON（只输出 JSON，不解释）
{{"scenarios": [{{"id": "scenario-{n}", "title": "一句话标题（业务背景）", "description": "一段话场景描述（含人物、动机、金额）", "difficulty": "简单|中等|困难", "expected_findings": ["finding-type"], "not_expected_findings": ["误报类型"], "data_preview": {{"field1": "value1", "field2": "value2"}}, "business_scenario": "这是该场景反映的真实业务问题"}}]}}"""


def random_difficulty(n: int) -> str:
    """简单/中等/困难 循环"""
    levels = ["简单", "中等", "困难"]
    return levels[(n - 1) % 3]


def scenario_to_files(scenario: dict, domain: str) -> tuple:
    """场景转 (CSV 路径, JSON 路径)"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    skill = DOMAIN_CONTEXT[domain]["skill"]
    out_dir = ROOT / "evals" / "blackbox" / "scenarios" / f"auto-{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = scenario.get("id", "scenario-X").split("-")[-1]

    # 写场景描述（人类可读）
    desc_path = out_dir / f"{idx}-description.md"
    with desc_path.open("w", encoding="utf-8") as f:
        f.write(f"# {scenario.get('title', scenario.get('id',''))}\n\n")
        f.write(f"**难度**: {scenario.get('difficulty', '')}\n\n")
        f.write(f"**场景描述**: {scenario.get('description', '')}\n\n")
        f.write(f"**预期 finding**: {', '.join(scenario.get('expected_findings', []))}\n\n")
        f.write(f"**不应触发**: {', '.join(scenario.get('not_expected_findings', []))}\n\n")
        f.write(f"**数据预览**:\n```json\n{json.dumps(scenario.get('data_preview', {}), ensure_ascii=False, indent=2)}\n```\n")

    # 写 ground truth
    gt_path = out_dir / f"{idx}-ground-truth.json"
    with gt_path.open("w", encoding="utf-8") as f:
        json.dump({
            "scenario_id": scenario.get("id", ""),
            "domain": domain,
            "skill": skill,
            "title": scenario.get("title", ""),
            "difficulty": scenario.get("difficulty", ""),
            "expected_findings": scenario.get("expected_findings", []),
            "not_expected_findings": scenario.get("not_expected_findings", []),
            "data_preview": scenario.get("data_preview", {}),
            "needs_full_data": True,  # 标记：需要后续生成完整 fixture
            "generated_at": timestamp,
        }, f, indent=2, ensure_ascii=False)

    return desc_path, gt_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=list(DOMAIN_CONTEXT.keys()),
                        required=True, help="生成哪个领域的场景")
    parser.add_argument("--count", type=int, default=5, help="生成几个场景")
    parser.add_argument("--focus", default="", help="额外关注点（如'中国制造业 2024 趋势'）")
    args = parser.parse_args()

    if not os.environ.get("MINIMAX_API_KEY"):
        print("ERROR: MINIMAX_API_KEY 未设置", file=sys.stderr)
        sys.exit(1)

    print(f"[scenario-generator] domain={args.domain}, count={args.count}, focus={args.focus!r}", file=sys.stderr)
    scenarios = generate_scenarios(args.domain, args.count, args.focus)
    print(f"[scenario-generator] LLM 返回 {len(scenarios)} 个场景描述", file=sys.stderr)

    print(f"\n{'='*60}")
    for scenario in scenarios:
        title = scenario.get("title", scenario.get("id", ""))
        diff = scenario.get("difficulty", "?")
        expected = ", ".join(scenario.get("expected_findings", []))
        print(f"\n[{diff}] {title}")
        print(f"  Expected: {expected}")
        desc_path, gt_path = scenario_to_files(scenario, args.domain)
        print(f"  → {desc_path.name}")
        print(f"  → {gt_path.name}")

    print(f"\n{'='*60}")
    print(f"输出在: evals/blackbox/scenarios/auto-*/")
    print(f"⚠ 注意: 这只是场景描述和 ground truth，没有完整 fixture 数据")
    print(f"  下一步：人工 review 后，由 fixture_generator.py 补全 CSV")


if __name__ == "__main__":
    main()
