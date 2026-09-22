#!/bin/bash
# install.sh — Install AI Audit Skills by andrew-tao-li (latest)
#
# 一行命令（粘贴到 agent / shell）：
#   curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
#
# 可选环境变量：
#   HOST=opencode|workbuddy|lobsterai   默认 opencode
#   PREFIX=...                          覆盖默认安装目录
#   VERSION=v0.X.Y                      锁定版本（默认：releases/latest）
#
# 只装部分 skill（空格分隔）：
#   curl .../install.sh | bash -s -- expense-audit-v2 investigation-assistant-v2
#
# 卸载：rm -rf $PREFIX/<skill-name>
set -e

REPO="andrew-tao-li/ai-audit-skills"
ALL_SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2)

HOST="${HOST:-opencode}"
case "$HOST" in
    opencode)   PREFIX="${PREFIX:-$HOME/.config/opencode/skills}" ;;
    workbuddy)  PREFIX="${PREFIX:-$HOME/.workbuddy/skills}" ;;
    lobsterai)  PREFIX="${PREFIX:-$HOME/.lobsterai/skills}" ;;
    *)          PREFIX="${PREFIX:-$HOST}" ;;
esac

# 决定安装哪些 skill：位置参数覆盖默认全装
if [ "$#" -gt 0 ] && [ "$1" != "install" ]; then
    SKILLS=("$@")
else
    SKILLS=("${ALL_SKILLS[@]}")
fi

# 解析最新 tag（除非用户锁定 VERSION）
# 优先 GitHub API（拿 tag_name）；被速率限制时回退到 /releases/latest 的 302 重定向（无速率限制）。
if [ -z "$VERSION" ]; then
    VERSION=$(curl -sLf -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/${REPO}/releases/latest" \
        2>/dev/null \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null) || VERSION=""
fi
if [ -z "$VERSION" ]; then
    # Fallback: redirect of /releases/latest gives the actual tag page URL
    RELEASE_URL=$(curl -sLI -o /dev/null -w '%{url_effective}\n' \
        "https://github.com/${REPO}/releases/latest" 2>/dev/null) || RELEASE_URL=""
    # 形如 https://github.com/<owner>/<repo>/releases/tag/v0.2.0
    VERSION="${RELEASE_URL##*/tag/}"
fi
if [ -z "$VERSION" ]; then
    echo "⚠ 无法获取最新版本（GitHub API 与重定向都失败/返回非 tag 页）。请设置 VERSION=v0.X.Y 重试。" >&2
    exit 1
fi

echo "▶ 安装 AI Audit Skills ${VERSION} → ${PREFIX}"
mkdir -p "$PREFIX"

WORKDIR="$(mktemp -d -t aiaudit-install-XXXXXX)"
trap 'rm -rf "$WORKDIR"' EXIT

for s in "${SKILLS[@]}"; do
    echo "  · $s"
    URL="https://github.com/${REPO}/releases/download/${VERSION}/${s}.zip"
    if ! curl -sLf --connect-timeout 15 -o "$WORKDIR/$s.zip" "$URL"; then
        echo "  ✗ 下载失败：$URL" >&2
        exit 1
    fi
    mkdir -p "${PREFIX}/${s}"
    unzip -oq "$WORKDIR/$s.zip" -d "${PREFIX}/${s}"
done

echo ""
echo "✓ 完成（${VERSION}）。已装到：${PREFIX}"
ls -1 "$PREFIX" 2>/dev/null | sed 's/^/  /'
