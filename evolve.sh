#!/bin/bash
# 完整进化循环：跑测试 → 评分 → LLM 分析 → 写 proposals → 通知
# 用法：./evolve.sh [--skip-llm]
#
# 架构：
#   - 测试 + 评分（无 LLM）：本脚本可独立运行
#   - LLM 分析（要 API key）：通过 call_llm.py 直接调 MiniMax
#   - launchd 后台跑：每步可独立开关

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VERSION="${VERSION:-v0.2.0-baseline}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_DIR="evolution/log"
STATE_FILE="evolution/state.json"
PROPOSALS_DIR="evolution/proposals"

SKIP_LLM=0
if [ "$1" = "--skip-llm" ]; then
    SKIP_LLM=1
fi

mkdir -p "$LOG_DIR" "$PROPOSALS_DIR"

echo "═══════════════════════════════════════════════"
echo "  Audit Skill Box - Daily Cycle"
echo "  Version: $VERSION"
echo "  Timestamp: $TIMESTAMP"
echo "  Skip LLM: $SKIP_LLM"
echo "═══════════════════════════════════════════════"

# 1. 跑测试（不需要 LLM）
echo ""
echo "▶ Step 1: Running blackbox tests..."
python3 evals/blackbox/score_blackbox.py --version "$VERSION"

# 2. 提取最新分数，更新 state.json
echo ""
echo "▶ Step 2: Updating state..."
LATEST_LOG=$(ls -t "$LOG_DIR"/*-test-"$VERSION".json 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "ERROR: No log file found"
    exit 1
fi

# 用 Python 安全地更新 state.json（stdout 只输出数字）
OPEN_FAILURES_COUNT=$(python3 <<PYEOF
import json
from pathlib import Path

state_file = Path("$STATE_FILE")
log_file = Path("$LATEST_LOG")

state = json.loads(state_file.read_text())
log = json.loads(log_file.read_text())

state["current_version"] = "$VERSION"
state["last_action"] = {
    "type": "test",
    "timestamp": "$TIMESTAMP",
    "run_by": "launchd" if "${LAUNCHD_JOB:-}" != "" else "manual",
    "summary": f"precision={log['summary'].get('expense', {}).get('precision', 0):.0%} "
               f"recall={log['summary'].get('expense', {}).get('recall', 0):.0%}",
}
state["latest_scores"] = log["summary"]
state["last_modified"] = "$TIMESTAMP"
state["iteration_count"] = state.get("iteration_count", 0) + 1

state["open_failures"] = []
for skill, results in log["results"].items():
    for r in results:
        if r.get("f1", 1) < 1.0 and "error" not in r:
            for fp in r.get("fp", []):
                state["open_failures"].append({
                    "skill": skill,
                    "fixture": r["fixture"],
                    "type": "false_positive",
                    "detail": fp,
                })
            for fn in r.get("fn", []):
                state["open_failures"].append({
                    "skill": skill,
                    "fixture": r["fixture"],
                    "type": "false_negative",
                    "detail": fn,
                })

if not state.get("baseline_scores"):
    state["baseline_scores"] = log["summary"]

all_perfect = all(
    s.get("f1", 0) >= 1.0
    for s in log["summary"].values() if "f1" in s
)
if all_perfect and state.get("baseline_scores"):
    state["baseline_warning"] = (
        "Baseline 100% 通过，但所有 fixture 都是'单 finding'设计。"
        "建议增加复合场景 fixture 来测试真正的业务复杂度。"
    )
else:
    state.pop("baseline_warning", None)

state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
# 只输出数字到 stdout（其他输出到 stderr）
import sys
print(f"  State updated. Open failures: {len(state['open_failures'])}", file=sys.stderr)
print(len(state['open_failures']))
PYEOF
)

# 3. 输出简报
echo ""
echo "▶ Step 3: Summary"
python3 <<PYEOF
import json
state = json.loads(open("$STATE_FILE").read())
s = state.get("latest_scores", {})
for skill_name in ["expense", "procurement", "investigation"]:
    sd = s.get(skill_name, {})
    print(f"  {skill_name:15s} precision={sd.get('precision', 0):.0%}  recall={sd.get('recall', 0):.0%}  F1={sd.get('f1', 0):.0%}")
n = len(state.get("open_failures", []))
print(f"  Open failures: {n}")
if state.get("baseline_warning"):
    print(f"  ⚠ WARNING: {state['baseline_warning']}")
PYEOF

# 4. 如果有失败且未禁用 LLM，调 LLM 分析
if [ "$SKIP_LLM" = "0" ] && [ "$OPEN_FAILURES_COUNT" -gt 0 ]; then
    echo ""
    echo "▶ Step 4: LLM analysis of $OPEN_FAILURES_COUNT failures..."
    if [ -z "${MINIMAX_API_KEY:-}" ]; then
        echo "  SKIP: MINIMAX_API_KEY not set"
    else
        PROMPT_PATH=$(mktemp /tmp/audit-prompt.XXXXXX.txt)
        PROP_PATH="$PROPOSALS_DIR/${TIMESTAMP}-llm-analysis.md"
        python3 <<PROMPTEOF
import json
state = json.loads(open("$STATE_FILE").read())
failures = state.get("open_failures", [])
prompt = f"""你是审计 Skill 进化助手。请分析以下 11 个失败案例，给出根因 + 修复方向 + 风险评估。

## 失败列表
{json.dumps(failures, indent=2, ensure_ascii=False)}

## 当前 Skill 结构
- expense-audit: scripts/run_expense_audit.py
- procurement-fraud: scripts/run_procurement_audit.py
- investigation-assistant: scripts/build_case_workspace.py

## 任务
对每个失败：
1. **根因推测**：（基于 finding_type 和 fixture 名称定位代码可能的 bug）
2. **修复方向**：（具体到代码段）
3. **风险评估**：（修复可能引入的副作用）

## 输出格式
Markdown，按失败编号列出。
"""
open("$PROMPT_PATH", "w").write(prompt)
PROMPTEOF

        if python3 evals/blackbox/call_llm.py --prompt-file "$PROMPT_PATH" --out "$PROP_PATH" 2>&1 | tail -3; then
            echo "  Saved proposal: $PROP_PATH"

            # 更新 state.json：记录 proposal 路径
            python3 -c "
import json
from pathlib import Path
state = json.loads(open('$STATE_FILE').read())
if 'proposals' not in state:
    state['proposals'] = []
state['proposals'].append({
    'timestamp': '$TIMESTAMP',
    'path': '$PROP_PATH',
    'open_failure_count': $OPEN_FAILURES_COUNT,
    'trigger': 'auto-evolve.sh',
})
state['last_action'] = {
    'type': 'llm-analysis',
    'timestamp': '$TIMESTAMP',
    'summary': f'LLM analyzed {$OPEN_FAILURES_COUNT} failures → $PROP_PATH',
}
open('$STATE_FILE', 'w').write(json.dumps(state, indent=2, ensure_ascii=False))
"
        fi
        rm -f "$PROMPT_PATH"
    fi
elif [ "$OPEN_FAILURES_COUNT" = "0" ]; then
    echo ""
    echo "▶ Step 4: SKIP (no failures to analyze)"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Done. View details: evolution/state.json"
if [ -d "$PROPOSALS_DIR" ]; then
    echo "  Latest proposal: $(ls -t $PROPOSALS_DIR/*.md 2>/dev/null | head -1)"
fi
echo "═══════════════════════════════════════════════"
