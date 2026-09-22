#!/bin/bash
# 完整进化循环：跑测试 → 评分 → 健康检查 → LLM 分析 → 写 proposals → 通知 → git 持久化
# 用法：./evolve.sh [--skip-llm] [--skip-push]
#
# 架构：
#   - 测试 + 评分（无 LLM）：本脚本可独立运行
#   - LLM 分析（要 API key）：通过 call_llm.py 直接调 MiniMax
#   - 健康检查：ping MiniMax API + token 配额
#   - 通知：企业微信 Webhook / 邮件 / 日志
#   - launchd 后台跑：每步可独立开关

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

VERSION="${VERSION:-v0.2.0-baseline}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_DIR="evolution/log"
STATE_FILE="evolution/state.json"
PROPOSALS_DIR="evolution/proposals"
NOTIFY_SCRIPT="$ROOT/evolution/notify.sh"

SKIP_LLM=0
SKIP_PUSH=0
for arg in "$@"; do
    case "$arg" in
        --skip-llm) SKIP_LLM=1 ;;
        --skip-push) SKIP_PUSH=1 ;;
    esac
done

mkdir -p "$LOG_DIR" "$PROPOSALS_DIR"

# 0. 健康检查：ping MiniMax API
echo "═══════════════════════════════════════════════"
echo "  Audit Skill Box - Daily Cycle"
echo "  Version: $VERSION"
echo "  Timestamp: $TIMESTAMP"
echo "═══════════════════════════════════════════════"

echo ""
echo "▶ Step 0: 健康检查（API 可达性 + token 配额）"
HEALTH_STATUS="unknown"
HEALTH_MSG=""
if [ -n "${MINIMAX_API_KEY:-}" ]; then
    HEALTH_RESP=$(curl -s -X POST https://api.minimax.io/anthropic/v1/messages \
        -H "Content-Type: application/json" \
        -H "X-Api-Key: $MINIMAX_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -d '{"model":"MiniMax-M3","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}' \
        -w "%{http_code}" -o /tmp/health_resp.json 2>&1)
    HEALTH_CODE="$HEALTH_RESP"
    if [ "$HEALTH_CODE" = "200" ]; then
        HEALTH_STATUS="ok"
        HEALTH_MSG="API 可达"
        echo "  ✓ MiniMax API 可达"
    elif [ "$HEALTH_CODE" = "401" ]; then
        HEALTH_STATUS="auth_error"
        HEALTH_MSG="API key 无效（401）"
        echo "  ✗ API key 认证失败"
    elif [ "$HEALTH_CODE" = "429" ]; then
        HEALTH_STATUS="rate_limited"
        HEALTH_MSG="Token 配额耗尽（429）"
        echo "  ⚠ Token 配额耗尽，LLM 步骤将跳过"
    else
        HEALTH_STATUS="unknown_error"
        HEALTH_MSG="HTTP $HEALTH_CODE"
        echo "  ⚠ API 返回 HTTP $HEALTH_CODE"
    fi
else
    HEALTH_STATUS="no_api_key"
    HEALTH_MSG="MINIMAX_API_KEY 未设置"
    echo "  ⚠ MINIMAX_API_KEY 未设置，LLM 步骤将跳过"
fi

# 如果健康检查失败且未禁用 LLM，自动跳过
if [ "$HEALTH_STATUS" != "ok" ] && [ "$SKIP_LLM" = "0" ]; then
    echo "  → 自动跳过 LLM 分析（$HEALTH_STATUS）"
    SKIP_LLM=1
fi

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

# 5. 健康信息写入 state.json
echo ""
echo "▶ Step 5: 更新 state.json（健康状态）"
python3 <<PYEOF
import json
from pathlib import Path
state_file = Path("$STATE_FILE")
state = json.loads(state_file.read_text())
state["health"] = {
    "status": "$HEALTH_STATUS",
    "message": "$HEALTH_MSG",
    "checked_at": "$TIMESTAMP",
}
state["last_modified"] = "$TIMESTAMP"
state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
PYEOF
echo "  ✓ Health status recorded: $HEALTH_STATUS"

# 6. 通知
echo ""
echo "▶ Step 6: 发送通知"
NOTIFY_BODY="**Audit Skill Box 每日报告**

- 时间: $TIMESTAMP
- 版本: $VERSION
- 健康: $HEALTH_STATUS ($HEALTH_MSG)
- 失败: $OPEN_FAILURES_COUNT 个"

if [ -f "$PROPOSALS_DIR/${TIMESTAMP}-llm-analysis.md" ]; then
    NOTIFY_BODY="$NOTIFY_BODY

- 最新提案: evolution/proposals/${TIMESTAMP}-llm-analysis.md
- 分数: expense=$(python3 -c "import json; s=json.load(open('$STATE_FILE')); print(f\"{s.get('latest_scores',{}).get('expense',{}).get('f1',0):.0%}\")")
"
fi

if [ -f "$NOTIFY_SCRIPT" ]; then
    bash "$NOTIFY_SCRIPT" "[Audit Box] $VERSION 每日报告" "$NOTIFY_BODY" 2>&1 | tail -3
else
    echo "  ⚠ notify.sh 不存在，跳过通知"
fi

# 7. Git auto-commit + push
echo ""
echo "▶ Step 7: Git auto-commit"
if [ "$SKIP_PUSH" = "0" ]; then
    git add -A 2>&1 | tail -2
    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "auto: iteration $TIMESTAMP (failures=$OPEN_FAILURES_COUNT, health=$HEALTH_STATUS)" 2>&1 | tail -2

        # 尝试 push（SSH key 或 token 均可用）
        if git remote get-url origin >/dev/null 2>&1; then
            echo "  → push 到 GitHub..."
            if git push origin main 2>&1 | tail -3; then
                echo "  ✓ push 成功"
            else
                echo "  ⚠ push 失败（SSH key / token 未配置或权限不足）"
            fi
        else
            echo "  ⚠ 没有配置 remote，跳过 push"
        fi
    else
        echo "  → 没有变化，跳过 commit"
    fi
else
    echo "  → --skip-push，跳过"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Done. View details: evolution/state.json"
if [ -d "$PROPOSALS_DIR" ]; then
    echo "  Latest proposal: $(ls -t $PROPOSALS_DIR/*.md 2>/dev/null | head -1)"
fi
echo "═══════════════════════════════════════════════"
