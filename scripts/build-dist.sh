#!/bin/bash
# 重新打包 dist-v2 的三个 skill ZIP + 校验和（发布前必须重跑，确保 ZIP 与 skills-v2 代码一致）
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKILLS=(expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2 cn-entity-relation-check audit-sql-builder)

echo "▶ 重新打包 skills-v2 → dist-v2/zips/"
rm -f dist-v2/zips/*.zip dist-v2/lobsterai/*.zip dist-v2/workbuddy/*.zip
for skill in "${SKILLS[@]}"; do
    (cd "skills-v2/$skill" && zip -q -r -X "$ROOT/dist-v2/zips/$skill.zip" . \
        -x '*/__pycache__/*' -x '*.pyc' -x '*/.DS_Store' -x '.DS_Store')
    echo "  ✓ $skill.zip ($(du -h "dist-v2/zips/$skill.zip" | cut -f1))"
done

echo "▶ 生成「沙箱/云宿主」专用包 → dist-v2/sandbox/（单顶层文件夹，内容与原包一致）"
rm -rf dist-v2/sandbox && mkdir -p dist-v2/sandbox
for skill in "${SKILLS[@]}"; do
    tmpdir="$(mktemp -d)"
    unzip -q "dist-v2/zips/$skill.zip" -d "$tmpdir/$skill"
    # 归一化时间戳 → 保证同一输入必然产出同一字节（可复现）
    find "$tmpdir/$skill" -exec touch -t 202001010000 {} + 2>/dev/null
    (cd "$tmpdir" && zip -qrX "$ROOT/dist-v2/sandbox/$skill-sandbox.zip" "$skill")
    rm -rf "$tmpdir"
    echo "  ✓ $skill-sandbox.zip"
done
(cd dist-v2/sandbox && shasum -a 256 *.zip > SHA256SUMS)

echo "▶ 复制到 lobsterai/ 与 workbuddy/"
for host in lobsterai workbuddy; do
    cp dist-v2/zips/*.zip "dist-v2/$host/"
    echo "  ✓ dist-v2/$host/"
done

echo "▶ 重新生成校验和"
(cd dist-v2/zips && shasum -a 256 *.zip > ../SHA256SUMS)
(cd dist-v2/lobsterai && shasum -a 256 *.zip > checksums.txt)
(cd dist-v2/workbuddy && shasum -a 256 *.zip > checksums.txt)

echo ""
echo "完成。校验："
cat dist-v2/SHA256SUMS
