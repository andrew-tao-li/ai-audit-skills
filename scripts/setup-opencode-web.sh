#!/bin/bash
# 安装 OpenCode 网页服务为 launchd 常驻后台（开机自启、崩溃重启）
# 用法：
#   ./scripts/setup-opencode-web.sh [密码]
#     - 不传密码：自动生成强随机密码
#     - 传密码：用你指定的密码
# 装完后浏览器访问 http://<Tailscale-IP 或局域网 IP>:4096 ，用户名 opencode，密码见输出。
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$ROOT/evolution/com.opencode.web.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.opencode.web.plist"
LABEL="com.opencode.web"

if [ ! -f "$PLIST_SRC" ]; then
    echo "ERROR: 找不到模板 $PLIST_SRC"
    exit 1
fi

# 密码：优先用命令行参数，其次环境变量，否则自动生成
PASSWORD="${1:-${OPENCODE_SERVER_PASSWORD:-}}"
if [ -z "$PASSWORD" ]; then
    PASSWORD=$(openssl rand -base64 24 | tr -d '\n')
    echo "  已自动生成强密码"
fi

mkdir -p "$HOME/Library/LaunchAgents"

# 复制模板并注入密码（模板里占位符是 CHANGE_ME，用 PlistBuddy 直接替换）
cp "$PLIST_SRC" "$PLIST_DST"
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:OPENCODE_SERVER_PASSWORD '$PASSWORD'" "$PLIST_DST"

# 卸载旧实例再加载
launchctl unload "$PLIST_DST" 2>/dev/null || true
plutil -lint "$PLIST_DST" >/dev/null 2>&1 && echo "  ✓ Plist 语法正确" || { echo "  ✗ Plist 语法错误"; exit 1; }

launchctl load "$PLIST_DST"
echo "  ✓ launchd 服务已加载: $LABEL"

# 等它起来并验证
sleep 3
TAILSCALE_IP=$(/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4 2>/dev/null || tailscale ip -4 2>/dev/null || echo "")
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")

echo ""
echo "═══════════════════════════════════════════════"
echo "  OpenCode 网页服务已启动"
echo "═══════════════════════════════════════════════"
echo ""
echo "  用户名: opencode"
echo "  密码:   $PASSWORD"
echo ""
[ -n "$TAILSCALE_IP" ] && echo "  🌐 任何地方（Tailscale）: http://$TAILSCALE_IP:4096"
[ -n "$LAN_IP" ]      && echo "  🏠 局域网:               http://$LAN_IP:4096"
echo "  💻 本机:                 http://127.0.0.1:4096"
echo ""
echo "  管理命令："
echo "    launchctl list | grep opencode   # 看状态"
echo "    launchctl stop com.opencode.web  # 停止"
echo "    launchctl start com.opencode.web # 启动"
echo "    日志: ~/Library/Logs/opencode-serve.log / .err"
echo "═══════════════════════════════════════════════"
