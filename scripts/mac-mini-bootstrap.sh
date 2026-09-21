#!/bin/bash
# Audit Skill Box - Mac mini 空白起步脚本
# 在全新 Mac mini 上跑一次（只需 5 分钟）
# 此脚本会：
#   1. 检查 git / python / openssh
#   2. 配置 git 用户名/邮箱（如果需要）
#   3. 生成 SSH key（如果还没有）
#   4. 启动 ssh-agent + add key
#   5. 显示公钥，让你贴到 GitHub

set -e
echo "═══════════════════════════════════════════════"
echo "  Mac mini 空白起步 - 准备 git + SSH"
echo "═══════════════════════════════════════════════"
echo ""

# === Step 1: 检查依赖 ===
echo "▶ Step 1: 检查依赖"
for tool in git python3 ssh-keygen ssh-add; do
    if command -v $tool >/dev/null 2>&1; then
        echo "  ✓ $tool: $(command -v $tool)"
    else
        echo "  ✗ $tool: 未找到（可能需要安装 Xcode Command Line Tools）"
        echo "    解决: xcode-select --install"
        exit 1
    fi
done
echo ""

# === Step 2: 配置 git 用户 ===
echo "▶ Step 2: 配置 git 用户名/邮箱"
NEED_CONFIG=0
if ! git config --global user.name >/dev/null 2>&1; then
    NEED_CONFIG=1
fi
if ! git config --global user.email >/dev/null 2>&1; then
    NEED_CONFIG=1
fi

if [ "$NEED_CONFIG" = "1" ]; then
    echo "  当前未配置 git 用户信息"
    read -p "  请输入 GitHub 用户名 (e.g. andrew-tao-li): " gh_user
    read -p "  请输入邮箱 (e.g. you@example.com): " gh_email
    git config --global user.name "$gh_user"
    git config --global user.email "$gh_email"
    echo "  ✓ 已配置"
else
    echo "  ✓ git user.name:  $(git config --global user.name)"
    echo "  ✓ git user.email: $(git config --global user.email)"
fi
echo ""

# === Step 3: 生成 SSH key ===
echo "▶ Step 3: SSH key"
if [ -f "$HOME/.ssh/id_ed25519" ]; then
    echo "  ✓ 已存在: $HOME/.ssh/id_ed25519"
else
    echo "  生成新的 ed25519 SSH key..."
    mkdir -p "$HOME/.ssh"
    chmod 700 "$HOME/.ssh"
    ssh-keygen -t ed25519 -C "$(git config --global user.email)" -f "$HOME/.ssh/id_ed25519" -N ""
    echo "  ✓ 已生成"
fi
echo ""

# === Step 4: 启动 ssh-agent + add key ===
echo "▶ Step 4: ssh-agent 启动"
if [ -z "$SSH_AUTH_SOCK" ]; then
    eval "$(ssh-agent -s)"
    echo "  ✓ ssh-agent 已启动"
fi
ssh-add --apple-use-keychain "$HOME/.ssh/id_ed25519" 2>/dev/null || ssh-add "$HOME/.ssh/id_ed25519"
echo "  ✓ key 已 add"
echo ""

# === Step 5: 测试 SSH 连接 GitHub ===
echo "▶ Step 5: 测试到 GitHub 的 SSH 连接"
if ssh -T -o StrictHostKeyChecking=accept-new git@github.com 2>&1 | grep -q "successfully authenticated"; then
    echo "  ✓ SSH 连接 GitHub 成功"
    echo ""
    echo "  ⚠ 你已经配置过 SSH key！可以直接 clone"
    echo ""
else
    echo "  ⚠ SSH 还未认证（首次连接会要求确认 + 公钥未加到 GitHub）"
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "  ⚠ 下一步你必须做（在 Mac mini 上）:"
    echo "═══════════════════════════════════════════════"
    echo ""
    echo "1. 复制下面的公钥："
    echo "─────────────────────────────────────"
    cat "$HOME/.ssh/id_ed25519.pub"
    echo "─────────────────────────────────────"
    echo ""
    echo "2. 浏览器打开 https://github.com/settings/keys"
    echo ""
    echo "3. 点 'New SSH key'"
    echo "   - Title: 写 'Mac mini 2026-09'（任意你记得的）"
    echo "   - Key type: Authentication Key"
    echo "   - Key: 粘贴上面的公钥"
    echo "   - 点 'Add SSH key'"
    echo ""
    echo "4. 加完后，回来跑这个脚本，验证通过："
    echo "   ssh -T git@github.com"
    echo "   （应该看到 'Hi <username>! You've successfully authenticated'）"
    echo ""
    echo "═══════════════════════════════════════════════"
    exit 0
fi

# === Step 6: clone 项目 ===
echo "▶ Step 6: clone 项目"
TARGET_DIR="$HOME/Documents/AI助力审计0201/opencode"
mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

if [ -d "ai-audit-skills" ]; then
    echo "  ✓ 已存在: $TARGET_DIR/ai-audit-skills"
    cd ai-audit-skills
    echo "  → git pull 一下"
    git pull origin main
else
    echo "  → clone 到 $TARGET_DIR/ai-audit-skills"
    git clone git@github.com:andrew-tao-li/ai-audit-skills.git
    cd ai-audit-skills
    echo "  ✓ clone 完成"
fi
echo ""

# === Step 7: 验证 ===
echo "▶ Step 7: 验证项目结构"
ls -la
echo ""
echo "  README.md 存在: $([ -f README.md ] && echo "✓" || echo "✗")"
echo "  evolve.sh 存在: $([ -x evolve.sh ] && echo "✓" || echo "✗")"
echo "  setup-mac-mini.sh 存在: $([ -x scripts/setup-mac-mini.sh ] && echo "✓" || echo "✗")"
echo ""

# === 完成 ===
echo "═══════════════════════════════════════════════"
echo "  ✓ 空白起步完成"
echo "═══════════════════════════════════════════════"
echo ""
echo "下一步："
echo "  cd $TARGET_DIR/ai-audit-skills"
echo "  ./scripts/setup-mac-mini.sh"
echo ""
echo "setup 脚本会问 API key 和企业微信 Webhook URL"
echo ""
