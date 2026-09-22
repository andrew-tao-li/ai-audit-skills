#!/bin/bash
# Audit Skill Box - 通知机制
# 支持：
#   1. 企业微信群机器人 Webhook（推荐，零配置）
#   2. macOS 本地 mail 命令（需要 SMTP 配置）
#   3. 仅写日志（如果都没配）
#
# 用法：
#   ./evolution/notify.sh "标题" "正文 markdown"
#   echo "测试" | ./evolution/notify.sh "test" -
#
# 配置：evolution/notify_config.json

set -e
# macOS bash 3.2 multibyte bug：双引号内展开含中文变量会损坏字节。按字节处理 + Python UTF-8 模式。
export LC_ALL=C
export PYTHONUTF8=1
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$ROOT/evolution/notify_config.json"

# === 读取配置 ===
WECOM_URL=""
if [ -f "$CONFIG_FILE" ]; then
    WECOM_URL=$(python3 -c "
import json
try:
    c = json.load(open('$CONFIG_FILE'))
    if c.get('enabled') and c.get('wecom_webhook'):
        print(c['wecom_webhook'])
except: pass
" 2>/dev/null)
fi

# === 读入消息 ===
TITLE="${1:-Audit Skill Box 通知}"
shift || true
if [ $# -gt 0 ]; then
    BODY="$*"
else
    BODY=$(cat)
fi

# === Markdown 转纯文本（企业微信 text 类型不支持 markdown） ===
SIMPLE_BODY=$(printf '%s' "$BODY" | python3 -c '
import sys, re
text = sys.stdin.read()
text = re.sub(r"#{1,6}\s+", "", text)
text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
text = re.sub(r"\*([^*]+)\*", r"\1", text)
text = re.sub(r"`([^`]+)`", r"\1", text)
text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
print(text.strip())
')

# === 1. 优先：企业微信 Webhook ===
SENT=0
if [ -n "$WECOM_URL" ]; then
    # 用 sys.argv 传入标题/正文，避免环境变量作用域与引号转义问题
    MSG_JSON=$(python3 -c '
import json, sys
title = sys.argv[1]
body = sys.argv[2]
content = "【" + title + "】\n\n" + body
print(json.dumps({"msgtype": "markdown", "markdown": {"content": content}}, ensure_ascii=False))
' "$TITLE" "$SIMPLE_BODY")
    HTTP_CODE=$(curl -s -o /tmp/wecom_notify_resp.json -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$MSG_JSON" \
        "$WECOM_URL" 2>&1 || echo "000")
    # 企业微信即使 HTTP 200 也可能返回 errcode != 0，需校验
    ERRCODE=$(python3 -c "import json; print(json.load(open('/tmp/wecom_notify_resp.json')).get('errcode','-1'))" 2>/dev/null || echo "-1")
    if [ "$HTTP_CODE" = "200" ] && [ "$ERRCODE" = "0" ]; then
        echo "[notify] WeCom sent: $TITLE" >&2
        SENT=1
    else
        echo "[notify] WeCom failed (HTTP $HTTP_CODE, errcode $ERRCODE)" >&2
    fi
fi

# === 2. fallback：邮件 ===
if [ "$SENT" = "0" ] && command -v mail >/dev/null 2>&1; then
    MAIL_RECIPIENT="${AUDIT_BOX_MAIL:-$(whoami)@$(hostname -f 2>/dev/null || echo localhost)}"
    if echo "$BODY" | mail -s "[Audit Box] $TITLE" "$MAIL_RECIPIENT" 2>/dev/null; then
        echo "[notify] mail sent to $MAIL_RECIPIENT: $TITLE" >&2
        SENT=1
    else
        echo "[notify] mail failed (SMTP 未配置), falling back to log" >&2
    fi
fi

# === 3. 兜底：写日志 ===
if [ "$SENT" = "0" ]; then
    LOG_FILE="$ROOT/evolution/log/notifications.log"
    mkdir -p "$(dirname "$LOG_FILE")"
    TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    {
        echo "===== [$TIMESTAMP] $TITLE ====="
        echo "$BODY"
        echo ""
    } >> "$LOG_FILE"
    echo "[notify] written to log: $LOG_FILE" >&2
fi
