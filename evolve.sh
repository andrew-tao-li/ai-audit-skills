#!/bin/bash
# 完整进化循环：跑测试 → 评分 → 健康检查 → LLM 分析 → 写 proposals → 通知 → git 持久化
# 用法：./evolve.sh [--skip-llm] [--skip-push]
#
# 架构：
#   - 测试 + 评分（无 LLM）：本脚本可独立运行
#   - LLM 分析（要 API key）：通过 call_llm.py 调用（MiniMax 优先，DeepSeek 回退）
#   - 健康检查：先 ping MiniMax，失败再 ping DeepSeek
#   - 通知：企业微信 Webhook / 邮件 / 日志
#   - launchd 后台跑：每步可独立开关

set -e
# macOS 系统自带 bash 3.2 在双引号内展开含中文的变量时会损坏多字节（multibyte bug）。
# 强制 LC_ALL=C 让 bash 按字节处理；Python 侧用 PYTHONUTF8=1 保持 UTF-8。
export LC_ALL=C
export PYTHONUTF8=1
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 可选：从仓库外的私有文件读取 GITHUB_TOKEN（密钥绝不写进仓库，也不写进 plist）。
# 用户只需：mkdir -p ~/.config/ai-audit-skills && echo 'export GITHUB_TOKEN=xxx' > ~/.config/ai-audit-skills/env
if [ -f "$HOME/.config/ai-audit-skills/env" ]; then
    # shellcheck disable=SC1090
    . "$HOME/.config/ai-audit-skills/env"
fi

# 保证能找到 Homebrew 安装的 CLI（Apple Silicon 在 /opt/homebrew/bin，Intel 在 /usr/local/bin）。
# launchd 的 PATH 通常不含这些目录，会导致 opencode 找不到 → 验收被跳过（2026-09-27 发现）。
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 版本取自仓库（不再写死 v0.2.0-baseline）
VERSION="${VERSION:-$(cat "$ROOT/VERSION" 2>/dev/null || echo unknown)}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_DIR="evolution/log"
STATE_FILE="evolution/state.json"
PROPOSALS_DIR="evolution/proposals"
NOTIFY_SCRIPT="$ROOT/evolution/notify.sh"

# 兜底：任何一步意外失败，也要发出通知。
# 2026-09-28 教训：Step 1c 冒烟瞬时失败 + set -e → 脚本静默中止，连常规日报都没发出去，
# 结果用户"什么也没收到"，而这本身反而是最难排查的故障模式。
on_error() {
    local code=$?
    local tail_log
    tail_log=$(tail -6 "$LOG_DIR/launchd-stdout.log" 2>/dev/null | tr '\n' ' ' | cut -c1-280)
    bash "$NOTIFY_SCRIPT" "[Audit Box] ⚠️ 例行任务异常退出（exit $code）" \
"evolve.sh 意外中止，**本次没有发出常规日报**。

最后几步日志：${tail_log:-（读不到日志）}

详情见 evolution/log/launchd-stdout.log" 2>/dev/null || true
}
trap on_error ERR

SKIP_LLM=0
SKIP_PUSH=0
SKIP_ACCEPTANCE=0
SKIP_SMOKE=0
for arg in "$@"; do
    case "$arg" in
        --skip-llm) SKIP_LLM=1 ;;
        --skip-push) SKIP_PUSH=1 ;;
        --skip-acceptance) SKIP_ACCEPTANCE=1 ;;
        --skip-smoke) SKIP_SMOKE=1 ;;
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
echo "▶ Step 0: 健康检查（MiniMax 优先，DeepSeek 回退）"
HEALTH_STATUS="unknown"
HEALTH_MSG=""
LLM_PROVIDER=""

ping_minimax() {
    curl -s -X POST https://api.minimax.io/anthropic/v1/messages \
        -H "Content-Type: application/json" \
        -H "X-Api-Key: $MINIMAX_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -d '{"model":"MiniMax-M3","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}' \
        -w "%{http_code}" -o /tmp/health_resp.json 2>/dev/null
}
ping_deepseek() {
    curl -s -X POST https://api.deepseek.com/chat/completions \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
        -d '{"model":"deepseek-chat","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}' \
        -w "%{http_code}" -o /tmp/health_resp.json 2>/dev/null
}

MINIMAX_CODE=""
DEEPSEEK_CODE=""
[ -n "${MINIMAX_API_KEY:-}" ] && MINIMAX_CODE=$(ping_minimax || echo "000")
[ -n "${DEEPSEEK_API_KEY:-}" ] && DEEPSEEK_CODE=$(ping_deepseek || echo "000")

if [ "$MINIMAX_CODE" = "200" ]; then
    LLM_PROVIDER="minimax"
    HEALTH_STATUS="ok"
    HEALTH_MSG="MiniMax API 可达"
    echo "  ✓ MiniMax API 可达"
elif [ "$DEEPSEEK_CODE" = "200" ]; then
    LLM_PROVIDER="deepseek"
    HEALTH_STATUS="ok"
    HEALTH_MSG="MiniMax 不可用（$MINIMAX_CODE），已回退 DeepSeek"
    echo "  ✓ DeepSeek API 可达（MiniMax 回退）"
elif [ -z "${MINIMAX_API_KEY:-}" ] && [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    HEALTH_STATUS="no_api_key"
    HEALTH_MSG="MINIMAX_API_KEY 和 DEEPSEEK_API_KEY 均未设置"
    echo "  ⚠ 无 API key，LLM 步骤将跳过"
else
    if [ "$MINIMAX_CODE" = "401" ] || [ "$DEEPSEEK_CODE" = "401" ]; then
        HEALTH_STATUS="auth_error"
        HEALTH_MSG="API key 认证失败"
    elif [ "$MINIMAX_CODE" = "429" ] || [ "$MINIMAX_CODE" = "402" ] || [ "$DEEPSEEK_CODE" = "429" ] || [ "$DEEPSEEK_CODE" = "402" ]; then
        HEALTH_STATUS="rate_limited"
        HEALTH_MSG="配额/余额不足"
    else
        HEALTH_STATUS="unknown_error"
        HEALTH_MSG="API 不可用"
    fi
    echo "  ⚠ 无可用 LLM：MiniMax=$MINIMAX_CODE, DeepSeek=$DEEPSEEK_CODE"
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

# 1b. OpenCode 全自动验收（需要 opencode CLI + 模型；--skip-acceptance 可跳过）
ACCEPTANCE_LINE=""
NOT_RUN=""
if [ "$SKIP_ACCEPTANCE" = "0" ]; then
    echo ""
    echo "▶ Step 1b: OpenCode 全自动验收..."
    if command -v opencode >/dev/null 2>&1; then
        ACCEPT_LOG=$(python3 evals/cross-agent/run_acceptance.py --no-notify 2>/dev/null | tail -1)
        if [ -n "$ACCEPT_LOG" ] && [ -f "$ACCEPT_LOG" ]; then
            ACCEPT_MARK=$(grep -m1 "结果：" "$ACCEPT_LOG" | sed 's/.*结果：//;s/\*\*//g')
            ACCEPT_FAILED=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('failed','?'))" "${ACCEPT_LOG%.md}.json" 2>/dev/null || echo "?")
            if [ "$ACCEPT_FAILED" = "0" ]; then
                ACCEPTANCE_LINE="✅ $ACCEPT_MARK"
            else
                ACCEPTANCE_LINE="⚠️ $ACCEPT_MARK"
                NOT_RUN="$NOT_RUN OpenCode验收"
            fi
            echo "  验收：$ACCEPTANCE_LINE"
        else
            echo "  ⚠ 验收未产出报告"
            ACCEPTANCE_LINE="⚠️ 未产出报告"
            NOT_RUN="$NOT_RUN OpenCode验收"
        fi
    else
        echo "  ⚠ 未找到 opencode CLI，跳过验收"
        ACCEPTANCE_LINE="⚠️ 跳过（未找到 opencode）"
        NOT_RUN="$NOT_RUN OpenCode验收"
    fi
else
    ACCEPTANCE_LINE="⚠️ 跳过（--skip-acceptance）"
    NOT_RUN="$NOT_RUN OpenCode验收"
fi

# 1c. 安装冒烟测试（用户真正的安装路径：release → install.sh → 跑）
SMOKE_DISPLAY=""
if [ "$SKIP_SMOKE" = "0" ]; then
    echo ""
    echo "▶ Step 1c: 安装冒烟测试（release → 安装 → 运行）"
    SMOKE_OUT=$(python3 evals/install_smoke.py --no-notify 2>&1 || true)
    SMOKE_LINE=$(printf '%s' "$SMOKE_OUT" | grep -m1 "安装冒烟测试：" | sed 's/^安装冒烟测试：//')
    SMOKE_OK=$(printf '%s' "$SMOKE_LINE" | python3 -c "
import sys, re
m = re.match(r'(\d+)/(\d+)\s*通过', sys.stdin.read().strip())
print('1' if (m and m.group(1) == m.group(2)) else '0')
" 2>/dev/null || echo 0)
    if [ "$SMOKE_OK" = "1" ]; then
        SMOKE_DISPLAY="✅ $SMOKE_LINE"
    else
        SMOKE_DISPLAY="⚠️ ${SMOKE_LINE:-未产出结果}"
        NOT_RUN="$NOT_RUN 安装冒烟"
        # 把失败项写进日志：否则只看到"没通过"，不知道坏在哪
        printf '%s\n' "$SMOKE_OUT" | grep "❌" | head -6 || true
    fi
    echo "  冒烟：$SMOKE_DISPLAY"
else
    SMOKE_DISPLAY="⚠️ 跳过（--skip-smoke）"
    NOT_RUN="$NOT_RUN 安装冒烟"
fi

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
    if [ -z "$LLM_PROVIDER" ]; then
        echo "  SKIP: 无可用 LLM provider"
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

        if python3 evals/blackbox/call_llm.py --provider "$LLM_PROVIDER" --prompt-file "$PROMPT_PATH" --out "$PROP_PATH" 2>&1 | tail -3; then
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

# 4b. 若有失败，生成修复提案（PR），供人工在 GitHub 审批
echo ""
echo "▶ Step 4b: 生成修复提案（如有失败）"
if [ -n "${GITHUB_TOKEN:-}" ]; then
    python3 evolution/propose_fix.py 2>&1 | tail -3
else
    echo "  SKIP: 未设置 GITHUB_TOKEN（无法开 PR）；如需，请在 launchd/环境里配置"
    NOT_RUN="$NOT_RUN 修复提案(无token)"
fi

# 4c. 定期主动巡检（每 7 天一次；即使无失败也找一条改进）
echo ""
echo "▶ Step 4c: 定期主动巡检（如距上次 ≥7 天）"
if [ -n "${GITHUB_TOKEN:-}" ]; then
    RUN_PATROL=$(python3 - <<'PYEOF'
from pathlib import Path
from datetime import datetime, timezone
f = Path("evolution/log/.last_patrol")
if not f.exists():
    print("1")
else:
    try:
        d = datetime.strptime(f.read_text().strip(), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        print("1" if (datetime.now(timezone.utc) - d).days >= 7 else "0")
    except Exception:
        print("1")
PYEOF
)
    if [ "$RUN_PATROL" = "1" ]; then
        python3 evolution/patrol.py 2>&1 | tail -3
    else
        echo "  未到 7 天，跳过"
    fi
else
    echo "  SKIP: 未设置 GITHUB_TOKEN"
    NOT_RUN="$NOT_RUN 定期巡检(无token)"
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
    "provider": "$LLM_PROVIDER",
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

# 「未执行」要显眼：否则「失败: 0」会掩盖「这一项根本没跑」
if [ -n "$NOT_RUN" ]; then
    NOTIFY_BODY="$NOTIFY_BODY
- ⚠️ 未执行:$NOT_RUN"
fi

if [ -n "$ACCEPTANCE_LINE" ]; then
    NOTIFY_BODY="$NOTIFY_BODY
- OpenCode 验收: $ACCEPTANCE_LINE"
fi

if [ -n "$SMOKE_DISPLAY" ]; then
    NOTIFY_BODY="$NOTIFY_BODY
- 安装冒烟: $SMOKE_DISPLAY"
fi

# 待审批 PR（让通知里提到的 GitHub 状态可核对；"issue" 一律指 PR，本仓库不用 Issue）
if [ -n "${GITHUB_TOKEN:-}" ]; then
    OPEN_PRS_LINE=$(python3 - <<'PYEOF'
import json, os, urllib.request
try:
    req = urllib.request.Request("https://api.github.com/repos/andrew-tao-li/ai-audit-skills/pulls?state=open&per_page=100")
    req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "audit-skill-box")
    with urllib.request.urlopen(req, timeout=15) as r:
        prs = json.loads(r.read().decode("utf-8"))
    if not prs:
        print("0 个（当前无需审批）")
    else:
        lines = ["%d 个 —— 合并 = 采纳，关闭 = 拒绝" % len(prs)]
        for p in prs[:5]:
            lines.append("  PR #%s %s" % (p["number"], p["title"][:50]))
        lines.append("  https://github.com/andrew-tao-li/ai-audit-skills/pulls?q=is%3Apr+is%3Aopen")
        print("\n".join(lines))
except Exception as e:
    print("查询失败: %s" % e)
PYEOF
)
else
    OPEN_PRS_LINE="未配置 GITHUB_TOKEN —— 本机不会自动开 PR"
fi
NOTIFY_BODY="$NOTIFY_BODY
- 待审批 PR: $OPEN_PRS_LINE"

# 平台数据（SkillHub + GitHub）——只读；失败绝不中断例行
echo ""
echo "▶ Step 6b: 平台数据（SkillHub / GitHub）"
PLATFORM_BLOCK=$(python3 evolution/skillhub_stats.py 2>/dev/null || true)
if [ -n "$PLATFORM_BLOCK" ]; then
    echo "$PLATFORM_BLOCK" | sed 's/^/  /'
    NOTIFY_BODY="$NOTIFY_BODY

$PLATFORM_BLOCK"
else
    echo "  ⚠ 未能取得平台数据（不影响其余步骤）"
fi

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

        # 尝试 push：先走默认 remote（SSH），失败再回退到 token 认证的 HTTPS
        # （2026-09-29 教训：本机代理会偶发劫持 SSH，导致无人值守的例行推送静默失败）
        if git remote get-url origin >/dev/null 2>&1; then
            echo "  → push 到 GitHub..."
            if git push origin main 2>&1 | tail -3; then
                echo "  ✓ push 成功"
            elif [ -n "${GITHUB_TOKEN:-}" ]; then
                echo "  ⚠ SSH push 失败，回退到 HTTPS + token..."
                if git push "https://x-access-token:${GITHUB_TOKEN}@github.com/andrew-tao-li/ai-audit-skills.git" main 2>&1 | tail -3; then
                    echo "  ✓ push 成功（HTTPS 回退）"
                else
                    echo "  ⚠ push 失败（SSH 与 HTTPS 都不通）"
                fi
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
