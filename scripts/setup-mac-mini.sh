#!/bin/bash
# Audit Skill Box - Mac mini 一键部署脚本
# 用法：在 Mac mini 上 clone 项目后，执行 ./scripts/setup-mac-mini.sh
# 此脚本会：
#   1. 检查 Python 版本
#   2. 安装缺失的依赖
#   3. 写入 MINIMAX_API_KEY 到 ~/.zshrc
#   4. 安装 launchd 后台任务
#   5. 配置企业微信 Webhook（可选）
#   6. 立即跑一次验证

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "═══════════════════════════════════════════════"
echo "  Audit Skill Box - Mac mini Setup"
echo "═══════════════════════════════════════════════"
echo ""

# === Step 1: 检查 Python ===
echo "▶ Step 1: 检查 Python 版本"
PYTHON_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
echo "  当前 Python: $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "  ⚠ Python 3.10+ 必需，需要升级"
    if command -v brew >/dev/null 2>&1; then
        echo "  建议：brew install python@3.11"
    else
        echo "  请先装 Homebrew: https://brew.sh"
        echo "  然后: brew install python@3.11"
        exit 1
    fi
else
    echo "  ✓ Python 版本满足"
fi
echo ""

# === Step 2: 安装依赖 ===
echo "▶ Step 2: 检查 Python 依赖"
if ! python3 -c "import openpyxl" 2>/dev/null; then
    echo "  安装 openpyxl..."
    python3 -m pip install openpyxl
else
    echo "  ✓ openpyxl 已装"
fi
echo ""

# === Step 3: API key 配置 ===
echo "▶ Step 3: 配置 MINIMAX_API_KEY"
if [ -n "${MINIMAX_API_KEY:-}" ]; then
    echo "  ✓ 当前 shell 已有 API key（从环境变量读）"
elif grep -q "MINIMAX_API_KEY" ~/.zshrc 2>/dev/null; then
    echo "  ✓ ~/.zshrc 已有 API key 配置"
else
    echo "  当前 ~/.zshrc 没有 API key 配置"
    echo ""
    read -p "  请粘贴 MINIMAX_API_KEY (sk-cp-...): " api_key
    if [ -z "$api_key" ]; then
        echo "  ERROR: API key 不能为空"
        exit 1
    fi
    echo "" >> ~/.zshrc
    echo "# Audit Skill Box - MiniMax API key (added $(date -u +%Y-%m-%d))" >> ~/.zshrc
    echo "export MINIMAX_API_KEY=\"$api_key\"" >> ~/.zshrc
    echo "  ✓ 已写入 ~/.zshrc"
    echo "  ⚠ 请执行: source ~/.zshrc 或重启 shell 让变量生效"
fi
echo ""

# === Step 4: launchd 部署 ===
echo "▶ Step 4: 部署 launchd 后台任务"
PLIST_TEMPLATE="$ROOT/evolution/com.audit.skill.box.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.audit.skill.box.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

if [ ! -f "$PLIST_TEMPLATE" ]; then
    echo "  ERROR: 找不到 plist 模板: $PLIST_TEMPLATE"
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS_DIR"

# 替换 plist 里的路径（确保是当前用户的 home）
sed "s|/Users/taoli|$HOME|g" "$PLIST_TEMPLATE" > "$PLIST_DEST"

# 在 plist 里写入 API key（确保 launchd 后台进程有权限读）
# 先卸载（如果已存在）
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# 用 PlistBuddy 写入 API key
/usr/libexec/PlistBuddy -c "Delete :EnvironmentVariables:MINIMAX_API_KEY" "$PLIST_DEST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:MINIMAX_API_KEY string '${MINIMAX_API_KEY}'" "$PLIST_DEST" 2>/dev/null || {
    # fallback：从 ~/.zshrc 读
    api_key_from_zshrc=$(grep "MINIMAX_API_KEY" ~/.zshrc | sed -E 's/.*"(.*)".*/\1/' | head -1)
    if [ -n "$api_key_from_zshrc" ]; then
        /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:MINIMAX_API_KEY string '$api_key_from_zshrc'" "$PLIST_DEST"
    fi
}

echo "  ✓ Plist 已部署: $PLIST_DEST"

# 验证 plist 语法
plutil -lint "$PLIST_DEST" >/dev/null 2>&1 && echo "  ✓ Plist 语法正确" || echo "  ⚠ Plist 语法警告"

# 加载任务
launchctl load "$PLIST_DEST"
echo "  ✓ launchd 任务已加载"
echo ""

# === Step 5: 企业微信 Webhook 配置（可选） ===
echo "▶ Step 5: 配置企业微信 Webhook（可选）"
NOTIFY_CONFIG="$ROOT/evolution/notify_config.json"
if [ -f "$NOTIFY_CONFIG" ] && grep -q "wecom_webhook" "$NOTIFY_CONFIG" 2>/dev/null; then
    echo "  ✓ 企业微信 Webhook 已配置"
else
    echo "  企业微信群机器人 webhook URL 类似："
    echo "  https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx"
    echo "  （在企业微信群里添加机器人可获得）"
    echo ""
    read -p "  粘贴 Webhook URL（直接回车跳过邮件通知）: " wecom_url
    if [ -n "$wecom_url" ]; then
        cat > "$NOTIFY_CONFIG" <<EOF
{
  "wecom_webhook": "$wecom_url",
  "enabled": true,
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
        echo "  ✓ 企业微信 Webhook 已配置"
    else
        cat > "$NOTIFY_CONFIG" <<EOF
{
  "wecom_webhook": "",
  "enabled": false,
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
        echo "  ⚠ 未配置企业微信，将只用邮件或仅写日志"
    fi
fi
echo ""

# === Step 6: 立即跑一次验证 ===
echo "▶ Step 6: 立即跑一次验证"
echo "  (确保整个闭环跑通)"
echo ""
./evolve.sh
echo ""

# === Step 7: 总结 ===
echo "═══════════════════════════════════════════════"
echo "  ✓ Setup 完成"
echo "═══════════════════════════════════════════════"
echo ""
echo "已配置:"
echo "  ✓ Python + 依赖"
echo "  ✓ MINIMAX_API_KEY (在 ~/.zshrc)"
echo "  ✓ launchd 后台任务 (每天 9:00 自动跑)"
echo "  ✓ 通知机制 ($(if [ -f "$NOTIFY_CONFIG" ] && grep -q '"wecom_webhook"' "$NOTIFY_CONFIG" && [ -n "$(grep 'wecom_webhook' $NOTIFY_CONFIG | grep -o 'https://[^"]*')" ]; then echo "企业微信"; else echo "邮件/日志"; fi))"
echo ""
echo "日常无需操作。每天 9:00 launchd 自动跑 ./evolve.sh"
echo "有问题看邮件/企业微信通知"
echo ""
echo "建议今天做一次完整验证："
echo "  1. 重启 shell 让 .zshrc 生效: source ~/.zshrc"
echo "  2. 等到明天 9:00 看通知是否到"
echo "  3. 或者现在手动跑: launchctl start com.audit.skill.box"
echo ""
echo "查看所有文件："
echo "  - 架构文档: $ROOT/evolution/ARCHITECTURE.md"
echo "  - 路线图: $ROOT/evolution/ROADMAP.md"
echo "  - 部署指南: $ROOT/evolution/MIGRATION.md"
echo "  - 审计师指南: $ROOT/docs/FOR-AUDITORS.md"
