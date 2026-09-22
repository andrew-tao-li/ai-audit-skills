#!/bin/bash
# install.sh — Install AI Audit Skills by andrew-tao-li (latest)
#
# 一行命令（粘贴给 agent / shell）：
#   curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
#
# 可选环境变量：
#   HOST=auto|opencode|workbuddy|lobsterai  默认 auto（自动探测已存在的 skills 目录）
#   PREFIX=...                          覆盖默认安装目录
#   VERSION=v0.X.Y                      锁定版本（默认：releases/latest）
#
# 只装部分 skill（位置参数；其余留空 = 装全部 3 个）：
#   curl .../install.sh | bash -s -- expense-audit-v2
#   curl .../install.sh | bash -s -- expense-audit-v2 investigation-assistant-v2
#   # 想换 Agent 只需加 HOST=workbuddy ...
#   # 打错字会立刻报错并给出可选列表（防止拼错→404→静默失败）
#
# 卸载：rm -rf $PREFIX/<skill-name>
set -e

REPO="andrew-tao-li/ai-audit-skills"
ALL_SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2)

# 是否显式指定了 PREFIX（用于头部标签显示 custom，避免误导）
PREFIX_EXPLICIT=0
[ -n "${PREFIX:-}" ] && PREFIX_EXPLICIT=1

# Auto-detect Agent host（OpenCode → WorkBuddy → LobsterAI，找第一个已存在的 skills 目录）
# 不传 HOST 或传 HOST=auto 走探测；显式传 opencode/workbuddy/lobsterai/<path> 走指定。
if [ -z "$HOST" ] || [ "$HOST" = "auto" ]; then
    detected=""
    for h in opencode workbuddy lobsterai; do
        case "$h" in
            opencode)   dirs=("$HOME/.config/opencode/skills") ;;
            workbuddy)  dirs=("$HOME/.workbuddy/skills") ;;
            # LobsterAI 的 macOS 真实路径在 Library/Application Support 下（SKILLs 大写）；保留 ~/.lobsterai/skills 作兜底
            lobsterai)  dirs=("$HOME/Library/Application Support/LobsterAI/SKILLs" "$HOME/.lobsterai/skills") ;;
        esac
        for d in "${dirs[@]}"; do
            if [ -d "$d" ]; then detected="$h"; break 2; fi
        done
    done
    HOST="${detected:-opencode}"
fi
case "$HOST" in
    opencode)   PREFIX="${PREFIX:-$HOME/.config/opencode/skills}" ;;
    workbuddy)  PREFIX="${PREFIX:-$HOME/.workbuddy/skills}" ;;
    lobsterai)  PREFIX="${PREFIX:-$HOME/Library/Application Support/LobsterAI/SKILLs}" ;;
    *)          PREFIX="${PREFIX:-$HOST}" ;;
esac
# 头部标签：显式 PREFIX 时显示 custom，否则显示探测到的 host
if [ "$PREFIX_EXPLICIT" = "1" ]; then HOST_LABEL="custom"; else HOST_LABEL="$HOST"; fi

# 决定安装哪些 skill：
#   - 无位置参数 → 装全部 3 个
#   - 位置参数为指定的 skill 名（必须与 ALL_SKILLS 完全一致，打错字会立刻报错并给出可选列表）
TOTAL=${#ALL_SKILLS[@]}
if [ "$#" -eq 0 ]; then
    SKILLS=("${ALL_SKILLS[@]}")
    MODE="all"
else
    SELECTED=()
    for arg in "$@"; do
        matched=""
        for s in "${ALL_SKILLS[@]}"; do
            [ "$arg" = "$s" ] && matched="$s" && break
        done
        if [ -z "$matched" ]; then
            echo "✗ 未知的 skill 名：\"$arg\"" >&2
            echo "  可选（共 $TOTAL 个）：" >&2
            for s in "${ALL_SKILLS[@]}"; do
                echo "    - $s" >&2
            done
            echo "  用法：$0 [skill-name ...]   # 不传 = 装全部" >&2
            exit 2
        fi
        SELECTED+=("$matched")
    done
    SKILLS=("${SELECTED[@]}")
    MODE="subset"
fi
N=${#SKILLS[@]}

# 解析最新 tag（除非用户锁定 VERSION）。
# 方案 A：GitHub API，加 User-Agent（GitHub API 无 UA 会 403）；用 sed 提 tag_name（不依赖 python3，
#   因为 Windows 上裸 python3 常是商店 stub，会导致解析失败）。
# 方案 B：回退到 /releases/latest 的 302 重定向（GET 跟随到 tag 页，无速率限制）。
if [ -z "$VERSION" ]; then
    VERSION=$(curl -sLf -H "Accept: application/vnd.github+json" \
        -H "User-Agent: ai-audit-installer" \
        "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null \
        | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1) || VERSION=""
fi
if [ -z "$VERSION" ]; then
    RELEASE_URL=$(curl -sL -o /dev/null -w '%{url_effective}\n' \
        "https://github.com/${REPO}/releases/latest" 2>/dev/null) || RELEASE_URL=""
    # 形如 https://github.com/<owner>/<repo>/releases/tag/v0.2.0
    VERSION="${RELEASE_URL##*/tag/}"
fi
if [ -z "$VERSION" ]; then
    echo "⚠ 无法获取最新版本（GitHub API 与重定向都失败/返回非 tag 页）。请设置 VERSION=v0.X.Y 重试。" >&2
    exit 1
fi

# 头部摘要：明确告诉用户要装几个、装哪些、装到哪个 Agent
if [ "$MODE" = "all" ]; then
    echo "▶ 安装 AI Audit Skills ${VERSION} → ${PREFIX}  (host=${HOST_LABEL})"
    echo "  范围：全部 $N 个 skill"
else
    echo "▶ 安装 AI Audit Skills ${VERSION} → ${PREFIX}  (host=${HOST_LABEL})"
    echo "  范围：选中 $N/$TOTAL 个 skill（${SKILLS[*]}）"
fi
for s in "${SKILLS[@]}"; do
    echo "  · $s"
done

mkdir -p "$PREFIX"

# 下载临时 zip 直接写到目标目录内（不用 mktemp / /tmp）：Windows/WorkBuddy 沙箱会拦截 mktemp
# 建的 /tmp 子目录写入，导致 curl(23)「系统找不到指定的文件」。目标目录是用户自己的 skills 目录，可写。
for s in "${SKILLS[@]}"; do
    URL="https://github.com/${REPO}/releases/download/${VERSION}/${s}.zip"
    mkdir -p "${PREFIX}/${s}"
    TMP_ZIP="${PREFIX}/${s}.zip.downloading"
    if ! curl -sLf --connect-timeout 15 -o "$TMP_ZIP" "$URL"; then
        rm -f "$TMP_ZIP"
        echo "✗ 下载失败：$URL" >&2
        exit 1
    fi
    unzip -oq "$TMP_ZIP" -d "${PREFIX}/${s}"
    rm -f "$TMP_ZIP"
done

# 收尾：明确区分「全装」 vs 「装子集」，列出已装 / 未装
if [ "$MODE" = "all" ]; then
    echo ""
    echo "✓ 完成（${VERSION}）。已装全部 $N 个 skill 到：${PREFIX}"
else
    # 计算未装的（ALL_SKILLS - SKILLS）
    NOT_INSTALLED=()
    for s in "${ALL_SKILLS[@]}"; do
        is_in=0
        for k in "${SKILLS[@]}"; do [ "$s" = "$k" ] && is_in=1 && break; done
        [ "$is_in" -eq 0 ] && NOT_INSTALLED+=("$s")
    done
    echo ""
    echo "✓ 完成（${VERSION}）。本次装到 $N 个 skill 到：${PREFIX}"
    echo "  装的：${SKILLS[*]}"
    if [ "${#NOT_INSTALLED[@]}" -gt 0 ]; then
        echo "  未装的（${#NOT_INSTALLED[@]} 个）：${NOT_INSTALLED[*]}"
        echo "  想全装请直接跑：curl ... | bash（不要带参数）"
    fi
fi
echo "  当前内容："
ls -1 "$PREFIX" 2>/dev/null | sed 's/^/    /'
