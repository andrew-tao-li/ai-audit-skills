#!/usr/bin/env python3
"""下载归因表：把 SkillHub 的每日下载增量与「那周发生了什么运营动作」并排放。

为什么需要它
  SkillHub 的公开接口**只给 skill 级累计下载**（stats.downloads），没有来源维度、
  没有按版本/按渠道的拆分（实测确认：stats 里只有 comments/downloads/installs/stars/
  versions 个数）。所以「这波下载是谁带来的」只能靠**把平台数字和运营台账对齐**得出。

  本脚本把两边的台账拼成一张周表：
    · 平台侧：从 evolution/log/launchd-stdout.log 里解析每天 09:00 的 SkillHub 下载采样
      → 日增量 → 周汇总（并区分「费用报销审计」与其余四个）
    · 运营侧：知识星球项目的发布日志 / 分组通知台账 / 直播资料目录 → 那周做了什么
  → 一眼能看出「下载尖峰出现在哪一周、那周我们做了什么」。

用法
  python3 evolution/attribution.py              # 最近 8 周
  python3 evolution/attribution.py --weeks 12   # 更长
  python3 evolution/attribution.py --json       # 机器可读

数据源缺失时优雅降级（只缺哪边就少哪边，不报错）。
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOG = HERE / "log" / "launchd-stdout.log"
PLANET = Path.home() / "Documents" / "知识星球"

SKILLS = ["费用报销审计", "采购舞弊红旗筛查", "授权内调查材料整理",
          "中国工商关联排查", "审计取数 SQL 生成器"]
MAIN = "费用报销审计"          # 主推 skill，单独列
WEEKDAY_CN = "一二三四五六日"


# ---------------------------------------------------------------- 平台侧
def parse_skillhub_daily() -> dict:
    """从 launchd 日志里解析每日 09:00 的 SkillHub 下载采样。

    日志里每天一次例行运行会打一行形如：
        · 费用报销审计：下载 697 ↑42 · 收藏 1 · 评论 0｜professional
    同一天可能打多次 → 取当天最后一次观测（当日累计值）。
    """
    if not LOG.exists():
        return {}
    daily = defaultdict(dict)
    cur = None
    for line in LOG.read_text(encoding="utf-8", errors="ignore").split("\n"):
        m = re.search(r"(20\d\d-\d\d-\d\d) \d\d:\d\d:\d\d", line)
        if m:
            cur = m.group(1)
        if not cur:
            continue
        ms = re.search(r"· (.+?)：下载 (\d+)", line)
        if ms:
            daily[cur][ms.group(1)] = int(ms.group(2))
    return {d: v for d, v in daily.items() if v}


def weekly_deltas(daily: dict, weeks: int):
    """返回 [(周一日期, {skill: 该周增量})]，周增量 = 周末值 - 上周末值。"""
    if not daily:
        return []
    dates = sorted(daily)
    # 每周取一次采样（取该周最后一天有采样的日子）
    by_week = {}
    for d in dates:
        y, m, dd = map(int, d.split("-"))
        wk = date(y, m, dd) - timedelta(days=date(y, m, dd).weekday())
        by_week[wk] = (d, daily[d])          # 同周内后一天覆盖前面 → 保留周末值
    weeks_sorted = sorted(by_week)
    rows = []
    for i, wk in enumerate(weeks_sorted):
        if i == 0:
            prev = None
        else:
            prev = by_week[weeks_sorted[i - 1]][1]
        cur = by_week[wk][1]
        delta = {}
        for s in SKILLS:
            if s in cur and prev and s in prev:
                delta[s] = cur[s] - prev[s]
            elif s in cur:
                delta[s] = None            # 上一周没这个 skill，无法算增量
        rows.append((wk, delta))
    return rows[-weeks:]


# ---------------------------------------------------------------- 运营侧
def planet_events() -> dict:
    """读知识星球项目的台账，拿到「哪周做了什么」。读不到就返回空。"""
    ev = defaultdict(list)
    if not PLANET.is_dir():
        return ev

    # 1) 发布日志：每条主题
    csv = PLANET / "发布日志.csv"
    if csv.exists():
        for line in csv.read_text(encoding="utf-8", errors="ignore").split("\n")[1:]:
            f = [x.strip() for x in line.split(",")]
            if len(f) < 6 or not f[0]:
                continue
            try:
                d = date.fromisoformat(f[0].split(" ")[0])
            except ValueError:
                continue
            wk = d - timedelta(days=d.weekday())
            title = f[5][:28]
            ev[wk].append(f"发帖·{title}")

    # 2) 分组通知台账
    push = PLANET / "运营" / "智能体" / "推送记录.md"
    if push.exists():
        for m in re.finditer(r"^##\s+(20\d\d-\d\d-\d\d)\s+(\d\d:\d\d)[^\n]*\n(?:\n- 人群：[^\n]*\n)?- 内容：([^\n]*)",
                             push.read_text(encoding="utf-8", errors="ignore"), re.M):
            d = date.fromisoformat(m.group(1))
            wk = d - timedelta(days=d.weekday())
            ev[wk].append(f"分组通知·{m.group(3).strip()[:24]}")

    # 3) 直播资料目录（文件名带日期）
    live = PLANET / "上载星球内容" / "直播"
    if live.is_dir():
        for f in live.iterdir():
            m = re.match(r"(20\d\d-\d\d-\d\d)", f.name)
            if m:
                d = date.fromisoformat(m.group(1))
                wk = d - timedelta(days=d.weekday())
                ev[wk].append("直播资料")
    return ev


def manual_events() -> dict:
    """手记事件日历（课程期次、线下场次等不在星球台账里的动作）。

    格式：每行 `YYYY-MM-DD  事件描述`，# 开头为注释。
    """
    ev = defaultdict(list)
    f = HERE / "attribution_events.md"
    if not f.exists():
        return ev
    for line in f.read_text(encoding="utf-8", errors="ignore").split("\n"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"(20\d\d-\d\d-\d\d)\s+(.*)$", s)
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        wk = d - timedelta(days=d.weekday())
        ev[wk].append(m.group(2).strip()[:40])
    return ev


def daily_deltas(daily: dict):
    """日增量：[(日期, {skill: 增量})]"""
    dates = sorted(daily)
    out = []
    prev = None
    for d in dates:
        cur = daily[d]
        if prev is not None:
            delta = {s: (cur[s] - prev[s]) for s in SKILLS if s in cur and s in prev}
            out.append((d, delta))
        prev = cur
    return out


# ---------------------------------------------------------------- 输出
def build_markdown(rows, events, dailies) -> str:
    out = []
    out.append("## 下载归因表（SkillHub 增量 × 运营动作）\n")
    out.append("> 平台侧只有 skill 级累计下载（无来源维度、无按版本拆分），故用「日增量 × 周」与运营台账对齐。")
    out.append("> 「费用报销」= 费用报销审计；「其余4」= 采购舞弊/授权内调查/中国工商/审计取数 合计增量。")
    out.append("> 「节律」= 该周内费用报销审计增量最高的两天（尖峰通常落在周六 = 课程作业那一档）。\n")
    hdr = "| 周 | 费用报销 | 其余4 | 合计 | 节律（费用报销 Top2 天） | 那周发生了什么 |"
    out.append(hdr)
    out.append("|---|---|---|---|---|---|")
    # 日增量按周归拢，用于节律
    by_week = defaultdict(list)
    for d, delta in dailies:
        dt = date.fromisoformat(d)
        by_week[dt - timedelta(days=dt.weekday())].append((d, delta.get(MAIN, 0)))
    for wk, delta in rows:
        main = delta.get(MAIN)
        others = sum(v for k, v in delta.items() if k != MAIN and isinstance(v, int))
        others_n = sum(1 for k, v in delta.items() if k != MAIN and isinstance(v, int))
        acts = "、".join(dict.fromkeys(events.get(wk, []))) or "—"
        top = sorted(by_week.get(wk, []), key=lambda x: -x[1])[:2]
        rhythm = "、".join("%s +%d" % (d[5:], v) for d, v in top if v > 0) or "—"
        out.append("| %s~%s | %s | %s | %s | %s | %s |" % (
            wk.strftime("%m-%d"), (wk + timedelta(days=6)).strftime("%m-%d"),
            ("+%d" % main) if isinstance(main, int) else "—",
            ("+%d（%d个）" % (others, others_n)) if others_n else "—",
            ("+%d" % (main + others)) if isinstance(main, int) and others_n else "—",
            rhythm, acts))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    daily = parse_skillhub_daily()
    if not daily:
        print("✗ 读不到 launchd 日志（%s）" % LOG, file=sys.stderr)
        return 1
    rows = weekly_deltas(daily, args.weeks)
    events = planet_events()
    if not events:
        print("⚠ 读不到知识星球台账（%s），只出平台侧" % PLANET, file=sys.stderr)
    # 手记事件（课程期次等星球台账里没有的动作）与星球台账合并
    for wk, acts in manual_events().items():
        events[wk].extend(acts)
    dailies = daily_deltas(daily)

    if args.json:
        print(json.dumps({
            "weeks": [{"week": wk.isoformat(), "delta": delta,
                       "events": events.get(wk, [])} for wk, delta in rows],
        }, ensure_ascii=False, indent=2))
    else:
        print(build_markdown(rows, events, dailies))
    return 0


if __name__ == "__main__":
    sys.exit(main())
