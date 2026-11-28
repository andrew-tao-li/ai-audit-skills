#!/bin/bash
# 把 4 个 skill 发布到 ClawHub（国际 / OpenClaw 生态）
#
# 关键点：
#   1. 发布的是 `dist-v2/skillhub/<skill>/`（平台适配版）。
#      2026-10 安全整改后 **canonical 本身已合规范**（无外发 webhook / 无 curl|bash / 无隐瞒措辞，
#      见 docs/reported-issues.md #2），所以「适配版」与 canonical 的差异只剩 frontmatter 等平台字段。
#      ClawHub 的安全审计关注「凭据暴露 / 不安全执行 / 过度代理」——三个关注点现已从根本上不成立。
#   2. 分类/主题用 **ClawHub 自己那套**（与 SkillHub 不同），单一来源是 scripts/skillhub_config.py。
#
# 前置：clawhub login（必须本人 GitHub 授权）
#   npm i -g clawhub && clawhub login
#
# 注意：官方要求「GitHub 账号足够老才能过上传闸门」；账号太新可能被挡。

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2 cn-entity-relation-check audit-sql-builder)

# 演练模式：DRY_RUN=1 bash scripts/publish-clawhub.sh → 只打印命令，不真发
DRY_RUN="${DRY_RUN:-0}"

if ! command -v clawhub >/dev/null 2>&1; then
    echo "✗ 未安装 clawhub CLI。请先：npm i -g clawhub" >&2
    exit 1
fi
if ! clawhub whoami >/dev/null 2>&1; then
    if [ "$DRY_RUN" = "1" ]; then
        echo "⚠ 未登录 ClawHub（演练模式跳过登录检查；正式发布前需先 clawhub login）"
    else
        echo "✗ 未登录 ClawHub。请先运行：clawhub login" >&2
        exit 1
    fi
else
    echo "✓ 已登录 ClawHub：$(clawhub whoami 2>&1 | head -1)"
fi
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
    # slug 必须用「平台 slug」（andrew-tao-li-*），不能用裸 skill id：
    #   ClawHub 的 slug 会同步成 SkillHub 的 publicSlug，用裸 id 会生成
    #   expense-audit-v2 这种**新条目**，与现有的 andrew-tao-li-expense-audit 并存（重复）。
    #   用平台 slug → 认领时原地接管现有条目，下载量不丢。
    SLUG=$(python3 - "$s" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("c", "scripts/skillhub_config.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.SKILLS[sys.argv[1]]["slug"])
PY
)
    NAME=$(python3 - "$s" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("c", "scripts/skillhub_config.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.SKILLS[sys.argv[1]]["display_name"])
PY
)
    # 源 commit：平台据此把 listing 关联回 GitHub 仓库（githubAuthorLogin 的依据）
    COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo "")

    echo "▶ ClawHub 发布 $s@$v  slug=$SLUG  分类=$CATS  主题=$TOPICS"
    ARGS=(
        --slug "$SLUG"
        --name "$NAME"
        --version "$v"
        --categories "$CATS"
        --topics "$TOPICS"
        --source-repo "https://github.com/andrew-tao-li/ai-audit-skills"
        --source-path "skills-v2/$s"
        --changelog "首次发布：面向审计/合规/财务的离线确定性审计技能（纯本地、零外传、不联网）"
    )
    [ -n "$COMMIT" ] && ARGS+=(--source-commit "$COMMIT" --source-ref main)
    if [ "$DRY_RUN" = "1" ]; then
        # 用 CLI 自带的 --dry-run：本地校验 slug 规则、分类、必填项，不发网络请求
        clawhub skill publish "$DIR" "${ARGS[@]}" --dry-run
    else
        clawhub skill publish "$DIR" "${ARGS[@]}"
    fi
    echo ""
done

echo "✓ ClawHub 发布完成（${#SKILLS[@]} 个 skill，已进入安全审计）"
echo "  查看：clawhub search andrew-tao-li-expense-audit"
echo "  审计页：https://clawhub.ai/<your-handle>/skills/<slug>/security-audit"
