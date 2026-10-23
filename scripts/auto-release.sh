#!/bin/bash
# 每 5 分钟探测 GitHub；通了就自动发 v0.3.34（幂等：已存在则补传缺失资产；失败自动删 release 重来）
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT" || exit 1
. "$HOME/.config/ai-audit-skills/env"
R=andrew-tao-li/ai-audit-skills; TAG=v0.3.34
LOG="$ROOT/evolution/log/auto-release-$TAG.log"
mkdir -p "$(dirname "$LOG")"
say(){ echo "[$(date '+%F %T')] $*" >>"$LOG"; }
say "启动：每 5 分钟探测一次，最多 48 次（4 小时）"

for attempt in $(seq 1 48); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 20 https://api.github.com 2>/dev/null)
  if [ "$code" != "200" ] && [ "$code" != "403" ]; then
    say "第 $attempt 次：网络不可用（$code）→ 等 5 分钟"
    sleep 300; continue
  fi
  say "第 $attempt 次：网络可用（$code）→ 开始发布"

  rc=$(curl -s -o /tmp/ar-rel.json -w '%{http_code}' -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" -H "User-Agent: x" "https://api.github.com/repos/$R/releases/tags/$TAG" --max-time 40)
  if [ "$rc" != "200" ]; then
    printf '%s' '{"tag_name":"v0.3.34","name":"v0.3.34","draft":false,"prerelease":false,"body":"## v0.3.34 — expense-audit-v2 0.2.32（示例数据增强，不改规则）\n\n- 住宿补 check_in/check_out（3 晚那行还补 nights/room_number）\n- 机票 2 行带 flight_no/pnr/issue_date\n- 新增出租车×2、停车、快递、通讯；expense_date 带具体时间\n- 原有 15 行一行未删\n\n默认不参与规则；命中仍是 11 findings / 72 evidence。"}' > /tmp/ar-body.json
    rc2=$(curl -s -o /tmp/ar-rel.json -w '%{http_code}' -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" -H "User-Agent: x" -H "Content-Type: application/json" --data @/tmp/ar-body.json "https://api.github.com/repos/$R/releases" --max-time 90)
    [ "$rc2" = "201" ] || { say "创建 release 失败（$rc2）→ 等 5 分钟"; sleep 300; continue; }
    say "已创建 release"
  fi
  RID=$(python3 -c "import json;print(json.load(open('/tmp/ar-rel.json'))['id'])" 2>/dev/null)
  [ -n "$RID" ] || { say "取不到 release id → 等 5 分钟"; sleep 300; continue; }

  fails=0
  for f in dist-v2/zips/*.zip dist-v2/sandbox/*.zip; do
    n=$(basename "$f")
    python3 -c "import json,sys;d=json.load(open('/tmp/ar-rel.json'));sys.exit(0 if any(a['name']=='$n' for a in d.get('assets',[])) else 1)" && continue
    up=000
    for t in 1 2 3 4; do
      up=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $GITHUB_TOKEN" -H "User-Agent: x" -H "Content-Type: application/zip" --data-binary @"$f" "https://uploads.github.com/repos/$R/releases/$RID/assets?name=$n" --max-time 300)
      [ "$up" = "201" ] && break; sleep 5
    done
    if [ "$up" = "201" ]; then say "  上传 ✓ $n"; else say "  上传 ✗ $n（$up）"; fails=$((fails+1)); fi
  done

  cnt=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" -H "User-Agent: x" "https://api.github.com/repos/$R/releases/$RID" --max-time 40 | python3 -c "import json,sys;print(len(json.load(sys.stdin).get('assets',[])))" 2>/dev/null)
  if [ "$fails" = "0" ] && [ "$cnt" = "10" ]; then
    say "✓ 10 个资产齐全"
    python3 scripts/publish-skillhub.py expense-audit-v2 --changelog "示例数据增强：住宿补 check_in/check_out，新增机票/出租车/停车/快递/通讯（带具体时间）" >>"$LOG" 2>&1 && say "✓ SkillHub 已提交" || say "⚠️ SkillHub 提交失败（不影响 release）"
    git push "https://x-access-token:${GITHUB_TOKEN}@github.com/$R.git" main >>"$LOG" 2>&1 && say "✓ 已推送 main" || say "⚠️ 推送失败（下次例行会推）"
    say "✅ 全部完成（$TAG）"
    echo DONE > "$ROOT/evolution/log/auto-release-$TAG.done"
    exit 0
  fi
  say "资产不齐（$cnt 个 / 失败 $fails）→ 删除 release 保护 latest，5 分钟后重来"
  curl -s -o /dev/null -X DELETE -H "Authorization: Bearer $GITHUB_TOKEN" -H "User-Agent: x" "https://api.github.com/repos/$R/releases/$RID" --max-time 60
  sleep 300
done
say "❌ 4 小时内未成功，停止（需人工介入）"
exit 1
