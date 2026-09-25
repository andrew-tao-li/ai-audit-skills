#!/bin/bash
# 把 4 个 skill 发布到 ClawHub（发布前必须先 `clawhub login`）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="https://github.com/andrew-tao-li/ai-audit-skills"
SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2 cn-entity-relation-check)

# 前置：确认已登录
if ! clawhub whoami >/dev/null 2>&1; then
    echo "✗ 未登录 ClawHub。请先运行：clawhub login" >&2
    exit 1
fi
echo "✓ 已登录 ClawHub：$(clawhub whoami 2>&1 | head -1)"
echo ""

for s in "${SKILLS[@]}"; do
    v=$(grep -m1 '^version:' "$ROOT/skills-v2/$s/SKILL.md" | tr -d ' ' | sed 's/version://')
    echo "▶ ClawHub 发布 $s@$v …"
    clawhub publish "$ROOT/skills-v2/$s" \
        --slug "$s" \
        --version "$v" \
        --source-repo "$REPO" \
        --source-path "skills-v2/$s" \
        --tags "audit,compliance"
    echo ""
done

echo "✓ ClawHub 发布完成（4 个 skill）"
echo "  查看：clawhub search expense-audit-v2"
