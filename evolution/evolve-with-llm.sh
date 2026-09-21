#!/bin/bash
# 调用 OpenCode HTTP server 跑 LLM 分析
# 架构说明：
#   - OpenCode 后台跑着（http://127.0.0.1:61844）
#   - 每次调用：创建 session → 发 prompt → 等回复
#   - 但需要从 OpenCode 拿到密码（OpenCode 自动生成，存在内存里）
#
# 备选方案 A：从 macOS keychain 读（OpenCode 可能存了）
# 备选方案 B：直接调 MiniMax API（需要 API key）
#
# 当前实现：先尝试 OpenCode HTTP API（通过 keychain 或环境变量拿密码）

set -e

# 1. 取密码（多种来源）
get_password() {
    # 优先：环境变量
    if [ -n "$OPENCODE_SERVER_PASSWORD" ]; then
        echo "$OPENCODE_SERVER_PASSWORD"
        return 0
    fi
    # 次选：macOS keychain
    if command -v security >/dev/null 2>&1; then
        local pwd=$(security find-generic-password -s "opencode-server" -w 2>/dev/null || true)
        if [ -n "$pwd" ]; then
            echo "$pwd"
            return 0
        fi
    fi
    # 备选：固定文件（用户手工设置）
    if [ -f ~/.opencode-server-password ]; then
        cat ~/.opencode-server-password
        return 0
    fi
    return 1
}

PASSWORD=$(get_password) || {
    echo "ERROR: 无法获取 OpenCode server 密码"
    echo "请设置 OPENCODE_SERVER_PASSWORD 环境变量"
    echo "或在 ~/.opencode-server-password 文件写入密码"
    exit 1
}

# 2. 找 OpenCode server 端口
find_opencode_port() {
    # 从 OpenCode 数据目录的最近日志找
    local log_file=$(ls -t ~/Library/Application\ Support/ai.opencode.desktop/logs/*/main.log 2>/dev/null | head -1)
    if [ -n "$log_file" ]; then
        grep -oE "127\.0\.0\.1:[0-9]+" "$log_file" | head -1 | cut -d: -f2
    fi
}

PORT="${OPENCODE_SERVER_PORT:-$(find_opencode_port)}"
if [ -z "$PORT" ]; then
    echo "ERROR: 无法找到 OpenCode server 端口"
    echo "请设置 OPENCODE_SERVER_PORT 环境变量"
    exit 1
fi

URL="http://127.0.0.1:${PORT}"
AUTH="opencode:${PASSWORD}"

echo ">>> OpenCode server: $URL"

# 3. 健康检查
echo ">>> Health check..."
HEALTH=$(curl -s -u "$AUTH" "$URL/global/health" 2>&1)
if [ $? -ne 0 ] || [ -z "$HEALTH" ]; then
    echo "ERROR: Health check failed"
    echo "Response: $HEALTH"
    exit 1
fi
echo "Health: $HEALTH"

# 4. 读 state.json
STATE_FILE="${1:-evolution/state.json}"
PROMPT="你是审计 Skill 进化助手。读取 $STATE_FILE，分析 open_failures 列表中的失败案例，输出：
1. 每个失败案例的根因推测（基于 finding_type 和 fixture 名称）
2. 建议的代码修复方向（具体到代码段）
3. 风险评估（修复可能引入的副作用）

输出 Markdown 格式。"

# 5. 创建 session
echo ">>> Creating session..."
SESSION_RESP=$(curl -s -X POST "$URL/session" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"audit-skill-evolve\"}")
SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id', ''))")
if [ -z "$SESSION_ID" ]; then
    echo "ERROR: Failed to create session"
    echo "Response: $SESSION_RESP"
    exit 1
fi
echo "Session: $SESSION_ID"

# 6. 发 prompt
echo ">>> Sending prompt..."
PROMPT_RESP=$(curl -s -X POST "$URL/session/$SESSION_ID/message" \
    -u "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "
import json, sys
prompt = open('$STATE_FILE').read()
print(json.dumps({'content': '''$PROMPT\n\nState file content:\n\`\`\`\n''' + prompt + '''\n\`\`\'''', 'model': 'MiniMax-M3'}))
")")

# 7. 等待回复（轮询）
echo ">>> Waiting for response..."
for i in {1..60}; do
    sleep 5
    MESSAGES=$(curl -s -u "$AUTH" "$URL/session/$SESSION_ID/messages" 2>&1)
    # 找最后一个 assistant message
    LAST=$(echo "$MESSAGES" | python3 -c "
import json, sys
try:
    msgs = json.load(sys.stdin)
    for m in reversed(msgs):
        if m.get('role') == 'assistant':
            print(m.get('content', ''))
            sys.exit(0)
    print('')
except:
    print('')
" 2>&1)
    if [ -n "$LAST" ]; then
        echo "Response received:"
        echo "$LAST"
        # 保存到 proposal 文件
        TS=$(date -u +"%Y%m%dT%H%M%SZ")
        OUT="evolution/proposals/${TS}-llm-analysis.md"
        echo "$LAST" > "$OUT"
        echo "Saved: $OUT"
        exit 0
    fi
done

echo "TIMEOUT: 5 分钟内未收到完整回复"
exit 1
