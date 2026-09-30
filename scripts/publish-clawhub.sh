#!/bin/bash
# 把 4 个 skill 发布到 ClawHub（国际 / OpenClaw 生态）
#
# 两个关键点：
#   1. **发布的是净化版**（dist-v2/skillhub/<skill>/），不是 canonical——
#      canonical 里有「反馈外发 webhook」和 `curl|bash` 更新指令，
#      ClawHub 的安全审计会盯「凭据暴露 / 不安全执行 / 过度代理」。
#      与 SkillHub 同一逻辑：**市场版 = 净化版，GitHub canonical = 全功能版**。
#   2. 分类/主题用 **ClawHub 自己那套**（与 SkillHub 不同），单一来源是 scripts/skillhub_config.py。
#
# 前置：clawhub login（必须本人 GitHub 授权）
#   npm i -g clawhub && clawhub login
#
# 注意：官方要求「GitHub 账号足够老才能过上传闸门」；账号太新可能被挡。

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2 cn-entity-relation-check)

if ! command -v clawhub >/dev/null 2>&1; then
    echo "✗ 未安装 clawhub CLI。请先：npm i -g clawhub" >&2
    exit 1
fi
if ! clawhub whoami >/dev/null 2>&1; then
    echo "✗ 未登录 ClawHub。请先运行：clawhub login" >&2
    exit 1
fi
echo "✓ 已登录 ClawHub：$(clawhub whoami 2>&1 | head -1)"
echo ""

# 确保净化版是最新的
python3 scripts/build-skillhub.py >/dev/null
echo "✓ 净化版已重建"
echo ""

for s in "${SKILLS[@]}"; do
    DIR="$ROOT/dist-v2/skillhub/$s"
    [ -f "$DIR/SKILL.md" ] || { echo "✗ 缺净化版产物：$DIR" >&2; exit 1; }
    v=$(grep -m1 '^version:' "$DIR/SKILL.md" | tr -d ' ' | sed 's/version://')

    # 从配置源读 ClawHub 的分类与主题
    CATS=$(python3 - "$s" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("c", "scripts/skillhub_config.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(",".join(m.SKILLS[sys.argv[1]].get("clawhub_categories", [])))
PY
)
    TOPICS=$(python3 - "$s" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("c", "scripts/skillhub_config.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(",".join(m.SKILLS[sys.argv[1]].get("clawhub_topics", [])))
PY
)

    echo "▶ ClawHub 发布 $s@$v  分类=$CATS  主题=$TOPICS"
    clawhub skill publish "$DIR" \
        --slug "$s" \
        --version "$v" \
        --categories "$CATS" \
        --topics "$TOPICS" \
        --source-repo "https://github.com/andrew-tao-li/ai-audit-skills" \
        --source-path "skills-v2/$s" \
        --changelog "首次发布：面向审计/合规/财务的离线确定性审计技能（纯本地、零外传、不联网）"
    echo ""
done

echo "✓ ClawHub 发布完成（4 个 skill，已进入安全审计）"
echo "  查看：clawhub search expense-audit-v2"
echo "  审计页：https://clawhub.ai/<your-handle>/skills/<slug>/security-audit"
