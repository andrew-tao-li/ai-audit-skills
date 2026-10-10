#!/bin/bash
# install.sh — Install AI Audit Skills by andrew-tao-li (latest)
#
# 一行命令（粘贴给 agent / shell）：
#   curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
#
# 可选环境变量：
#   HOST=auto|opencode|workbuddy|lobsterai|doubao  默认 auto（自动探测已存在的 skills 目录）
#   PREFIX=...                          覆盖默认安装目录
#   VERSION=v0.X.Y                      锁定版本（默认：releases/latest）
#   MIRROR=https://my.mirror/           下载源前缀（github.com 被墙/超时时用；可选）
#
# 只装部分 skill（位置参数；不传 = 装全部）：
#   curl .../install.sh | bash -s -- expense-audit-v2
#   curl .../install.sh | bash -s -- expense-audit-v2 investigation-assistant-v2
#   # 想换 Agent 只需加 HOST=workbuddy ...
#   # 打错字会立刻报错并给出可选列表（防止拼错→404→静默失败）
#
# 自检（不联网、不安装，只打印解析出的目标目录）：
#   bash install.sh --detect-only
#
# 卸载：rm -rf $PREFIX/<skill-name>
#
# ⚠ Windows 用户：本脚本是 bash，需要 Git Bash / WSL。若机器上没有 bash，请改用同目录的
#   install.ps1（Windows PowerShell 5.1+ / PowerShell 7+）。
set -e

REPO="andrew-tao-li/ai-audit-skills"
ALL_SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2 cn-entity-relation-check audit-sql-builder)

# 是否显式指定了 PREFIX（用于头部标签显示 custom，避免误导）
PREFIX_EXPLICIT=0
[ -n "${PREFIX:-}" ] && PREFIX_EXPLICIT=1

# 豆包有**两个不同产品**，两套数据目录（2026-10 由真实审计师实机纠正）：
#   ① 豆包（个人版）      应用目录 Doubao       → profile 目录 .doubao
#   ② 豆包工作（办公版）  应用目录 DoubaoWork   → profile 目录 .doubaowork
# 二者都是 Electron 应用，workspace 结构相同：
#   <应用目录>/User Data/Default/<profile>/agent_mode/workspace
# Windows 用 LOCALAPPDATA；macOS 用 Application Support。
# 来源：豆包官方帮助中心 + 真实审计师实机路径（2026-10，Windows 豆包工作：
#   %LOCALAPPDATA%\DoubaoWork\User Data\Default\.doubaowork\agent_mode\workspace）。
# 顺序：豆包工作（办公/Agent 场景，目标用户最可能用）→ 豆包（个人版）。
DOUBAO_WORKSPACE=""
DOUBAO_FLAVOR=""
for _ap in "DoubaoWork:.doubaowork" "Doubao:.doubao"; do
    _app="${_ap%%:*}"; _profile="${_ap##*:}"
    for _base in "${LOCALAPPDATA:-$HOME/AppData/Local}" "$HOME/Library/Application Support"; do
        _d="$_base/$_app/User Data/Default/$_profile/agent_mode/workspace"
        if [ -d "$_d" ]; then DOUBAO_WORKSPACE="$_d"; DOUBAO_FLAVOR="$_app"; break 2; fi
    done
done
# 兜底：workspace 尚未创建（刚装豆包、还没进过「工作任务」模式）时，只要应用数据目录存在就认它，
# 后面 mkdir -p 会把 workspace/.user_skills 建出来。
if [ -z "$DOUBAO_WORKSPACE" ]; then
    for _ap in "DoubaoWork:.doubaowork" "Doubao:.doubao"; do
        _app="${_ap%%:*}"; _profile="${_ap##*:}"
        for _base in "${LOCALAPPDATA:-$HOME/AppData/Local}" "$HOME/Library/Application Support"; do
            if [ -d "$_base/$_app/User Data/Default" ]; then
                DOUBAO_WORKSPACE="$_base/$_app/User Data/Default/$_profile/agent_mode/workspace"
                DOUBAO_FLAVOR="$_app"; break 2
            fi
        done
    done
fi
# 需要 export：host_dirs 在命令替换的子 shell 中执行，未导出的变量读不到
export DOUBAO_WORKSPACE DOUBAO_FLAVOR

# 各 host 的候选 skills 目录（供探测与「多 host 提示」共用）
host_dirs() {
    case "$1" in
        opencode)  printf '%s\n' "$HOME/.config/opencode/skills" ;;
        workbuddy) printf '%s\n' "$HOME/.workbuddy/skills" ;;
        lobsterai) printf '%s\n' "$HOME/Library/Application Support/LobsterAI/SKILLs" "$HOME/.lobsterai/skills" ;;
        # 豆包：用 workspace 目录是否存在来判断「装了豆包」——.user_skills 可能尚未创建
        doubao)    [ -n "$DOUBAO_WORKSPACE" ] && printf '%s\n' "$DOUBAO_WORKSPACE" ;;
    esac
}

# Auto-detect Agent host（OpenCode → WorkBuddy → LobsterAI → Doubao，找第一个已存在的 skills 目录）
# 注意：Doubao 追加在**最后**，因此不会改变任何既有平台的探测结果。
# 不传 HOST 或传 HOST=auto 走探测；显式传 opencode/workbuddy/lobsterai/doubao/<path> 走指定。
if [ -z "$HOST" ] || [ "$HOST" = "auto" ]; then
    detected=""
    found_list=""
    for h in opencode workbuddy lobsterai doubao; do
        while IFS= read -r d; do
            [ -n "$d" ] || continue
            if [ -d "$d" ]; then
                found_list="$found_list $h"
                [ -z "$detected" ] && detected="$h"
            fi
        done <<EOF
$(host_dirs "$h")
EOF
    done
    HOST="${detected:-opencode}"
    # 弱匹配兜底：豆包/豆包工作已安装（应用数据目录在）但 workspace 尚未创建（没进过「工作任务」模式），
    # 且机器上没有任何其他 Agent 目录 —— 此时装到豆包比装到并不存在的 opencode 更合理（后面会 mkdir）。
    if [ -z "$detected" ] && [ -n "$DOUBAO_WORKSPACE" ]; then
        HOST="doubao"
        echo "ℹ 未发现其他 Agent；检测到豆包（${DOUBAO_FLAVOR}，workspace 尚未创建，将自动创建）。" >&2
    fi
    # 机器上同时存在多个 Agent 目录时给出提示（不改变结果，只让人知道还能装到别处）
    _n=$(printf '%s' "$found_list" | wc -w | tr -d ' ')
    if [ "$_n" -gt 1 ]; then
        echo "ℹ 检测到多个 Agent 目录：${found_list# }。已按优先级装到 ${HOST}；如需装到别的，加 HOST=<名称> 或 PREFIX=<路径>。" >&2
    fi
fi
case "$HOST" in
    opencode)   PREFIX="${PREFIX:-$HOME/.config/opencode/skills}" ;;
    workbuddy)  PREFIX="${PREFIX:-$HOME/.workbuddy/skills}" ;;
    lobsterai)  PREFIX="${PREFIX:-$HOME/Library/Application Support/LobsterAI/SKILLs}" ;;
    doubao)
        if [ -n "$DOUBAO_WORKSPACE" ]; then
            PREFIX="${PREFIX:-$DOUBAO_WORKSPACE/.user_skills}"
            [ "$PREFIX_EXPLICIT" = "0" ] && echo "ℹ 检测到豆包（${DOUBAO_FLAVOR}）：${DOUBAO_WORKSPACE}" >&2
        else
            echo "⚠ 未找到豆包数据目录（已探测两套：DoubaoWork/.doubaowork 与 Doubao/.doubao）。" >&2
            echo "  请确认已安装「豆包」或「豆包工作」桌面客户端，并进入过「工作任务」模式；" >&2
            echo "  或用 PREFIX=<豆包技能目录> 显式指定。" >&2
            PREFIX="${PREFIX:-$HOME/.doubao/skills}"
        fi
        ;;
    *)          PREFIX="${PREFIX:-$HOST}" ;;
esac
# 头部标签：显式 PREFIX 时显示 custom，否则显示探测到的 host
if [ "$PREFIX_EXPLICIT" = "1" ]; then HOST_LABEL="custom"; else HOST_LABEL="$HOST"; fi

# --detect-only：只解析安装目标并打印，不联网、不安装。供用户自检与自动化测试用。
if [ "${1:-}" = "--detect-only" ]; then
    echo "HOST=${HOST}"
    echo "PREFIX=${PREFIX}"
    if [ -n "$DOUBAO_FLAVOR" ]; then echo "DOUBAO_FLAVOR=${DOUBAO_FLAVOR}"; fi
    exit 0
fi

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
        [ "$arg" = "--check" ] && continue
        [ "$arg" = "--detect-only" ] && continue
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
# 方案 C：回退到 raw.githubusercontent 上的 VERSION 文件（github.com 主站被墙、但 raw 可通的网络；
#   真实审计师 2026-10 就遇到过这种环境）。
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
    case "$RELEASE_URL" in
        */tag/*) VERSION="${RELEASE_URL##*/tag/}" ;;
        *)       VERSION="" ;;
    esac
fi
if [ -z "$VERSION" ]; then
    VERSION=$(curl -sLf "https://raw.githubusercontent.com/${REPO}/main/VERSION" 2>/dev/null | tr -d '[:space:]') || VERSION=""
    case "$VERSION" in
        v[0-9]*) ;;
        *)       VERSION="" ;;
    esac
fi
if [ -z "$VERSION" ]; then
    echo "⚠ 无法获取最新版本（GitHub API / 重定向 / raw 三种方式都失败）。请设置 VERSION=v0.X.Y 重试。" >&2
    exit 1
fi

# --check：只检查版本，不安装
if [ "$1" = "--check" ]; then
    echo "▶ 最新包版本：$VERSION"
    echo "▶ 已安装（$PREFIX）："
    for s in "${ALL_SKILLS[@]}"; do
        if [ -f "$PREFIX/$s/SKILL.md" ]; then
            local_v=$(grep -m1 '^version:' "$PREFIX/$s/SKILL.md" 2>/dev/null | tr -d ' ' | sed 's/version://')
            echo "  · $s: ${local_v:-未知}"
        else
            echo "  · $s: 未安装"
        fi
    done
    echo "  （新版会自动覆盖，重跑安装命令即更新）"
    exit 0
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
#
# 下载带**网络降级**（真实审计师 2026-10 的机器：github.com 超时，但 api.github.com / CDN 通）：
#   ① MIRROR=<前缀>（若设置）→ <MIRROR>/<VERSION>/<skill>.zip
#   ② github.com 直连（最快）
#   ③ GitHub API 资产接口（跟随 302 到 objects.githubusercontent.com）
# 三者都失败才报错，并给出可照做的替代路径。
download_skill() {
    local s="$1" out="$2" rc=1 u
    local urls=()
    [ -n "${MIRROR:-}" ] && urls+=("${MIRROR%/}/${VERSION}/${s}.zip")
    urls+=("https://github.com/${REPO}/releases/download/${VERSION}/${s}.zip")
    for u in "${urls[@]}"; do
        if curl -sLf --connect-timeout 15 -o "$out" "$u" 2>/dev/null; then rc=0; break; fi
        rm -f "$out"
    done
    if [ "$rc" -ne 0 ]; then
        # GitHub API 资产接口：release JSON 里 "url" 在 "name" 之前，可一次正则取出该资产的 API URL。
        local asset_api
        asset_api=$(curl -sLf -H "Accept: application/vnd.github+json" \
                -H "User-Agent: ai-audit-installer" \
                "https://api.github.com/repos/${REPO}/releases/tags/${VERSION}" 2>/dev/null \
            | tr -d ' \n' \
            | grep -oE "\"url\":\"[^\"]*/releases/assets/[0-9]+\"[^{}]*\"name\":\"${s}\.zip\"" \
            | sed -n 's/^"url":"\([^"]*\)".*/\1/p' | head -1)
        if [ -n "$asset_api" ]; then
            echo "  ℹ github.com 直连失败，改用 GitHub API 资产接口…" >&2
            if curl -sLf -H "Accept: application/octet-stream" -H "User-Agent: ai-audit-installer" \
                -o "$out" "$asset_api" 2>/dev/null; then rc=0; fi
        fi
    fi
    [ "$rc" -eq 0 ] || rm -f "$out"
    return $rc
}

for s in "${SKILLS[@]}"; do
    mkdir -p "${PREFIX}/${s}"
    TMP_ZIP="${PREFIX}/${s}.zip.downloading"
    if ! download_skill "$s" "$TMP_ZIP"; then
        echo "✗ 下载失败：${s}（版本 ${VERSION}）" >&2
        echo "  可照做的替代方案（任选其一）：" >&2
        echo "    1) 设置镜像后重试：MIRROR=<镜像前缀> bash install.sh ..." >&2
        echo "    2) 手动下载：https://github.com/${REPO}/releases/tag/${VERSION}" >&2
        echo "       下载 ${s}.zip，解压到 ${PREFIX}/${s}/" >&2
        echo "    3) 换网络/开代理后重试；或先设置 VERSION 指定版本排除版本解析问题" >&2
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
