#!/usr/bin/env python3
"""SkillHub + GitHub 数据汇总（给每日企业微信日报用）。

为什么需要它：
  我们自己那套「让用户对 Agent 说一句话 → Agent POST 到 webhook」的反馈机制很脆弱
  （有些宿主会脱敏 key，导致根本发不出去）。真正可靠的「使用数据 + 用户反馈」其实在平台上：
    · SkillHub 公开接口：下载量 / 安装量 / 收藏数 / 综合分 / 分类 / 认领状态
    · SkillHub CLI   ：评论（用户留言）、AI 评估报告、安全检测报告
    · GitHub API     ：stars / open issues
  本脚本把这些汇总成一段 markdown，塞进每日日报。

设计原则：
  · **只读**，不改任何东西；不联网写入。
  · **绝不因为网络/权限问题中断例行**（一律 graceful 降级，返回 0）。
  · 与上次相比给出**增量**（↑下载 3 / 新评论 1），没有变化就不啰嗦。

用法：
  python3 evolution/skillhub_stats.py            # 打印 markdown 块
  python3 evolution/skillhub_stats.py --json     # 机器可读
  python3 evolution/skillhub_stats.py --slot hub # 只跑 SkillHub
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATE_FILE = ROOT / "evolution" / "log" / ".platform_stats.json"
ENV_FILE = Path.home() / ".config" / "ai-audit-skills" / "env"
SKILLHUB_API = "https://api.skillhub.cn"
GH_REPO = "andrew-tao-li/ai-audit-skills"

# 我们在 SkillHub 上的四个 skill（slug 全网唯一，带作者前缀）
SKILLS = [
    ("andrew-tao-li-expense-audit", "费用报销审计"),
    ("andrew-tao-li-procurement-fraud", "采购舞弊红旗筛查"),
    ("andrew-tao-li-investigation-assistant", "授权内调查材料整理"),
    ("andrew-tao-li-cn-entity-relation", "中国工商关联排查"),
]


def load_env_file() -> None:
    """从仓库外的私有文件补充环境变量（与 evolve.sh 一致；密钥绝不进仓库）。"""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def http_json(url: str, token: str = "", timeout: int = 20):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "ai-audit-skillhub-stats")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def skillhub_stats(token: str) -> list:
    """逐个查我们自己的 skill（公开接口，不需要 token 也能读）。"""
    out = []
    for slug, name in SKILLS:
        row = {"slug": slug, "name": name, "found": False}
        try:
            data = http_json("%s/api/skills?keyword=%s&pageSize=20" % (SKILLHUB_API, slug), token)
            items = (data.get("data") or {}).get("skills") or []
            match = next((i for i in items if i.get("slug") == slug), None)
            if match:
                row.update({
                    "found": True,
                    "installs": match.get("installs", 0),
                    "downloads": match.get("downloads", 0),
                    "stars": match.get("stars", 0),
                    "score": match.get("score", 0),
                    "version": match.get("version", ""),
                    "category": (match.get("category") or "").strip() or "未分类",
                    "claim_state": match.get("claim_state", ""),
                    "verified": bool(match.get("verified")),
                })
        except Exception as e:  # noqa: BLE001
            row["error"] = str(e)[:120]
        out.append(row)
    return out


def skillhub_comments(token: str, namespace: str) -> dict:
    """用官方 CLI 拉评论数（CLI 不在或是未登录则 graceful 跳过）。"""
    cli = Path.home() / ".local" / "bin" / "skillhub"
    if not cli.exists() or not token:
        return {}
    result = {}
    for slug, _ in SKILLS:
        try:
            proc = subprocess.run(
                [str(cli), "comment", "list", slug, "--namespace", namespace, "--limit", "50", "--json"],
                capture_output=True, text=True, timeout=40, env={**os.environ, "SKILLHUB_HOST": SKILLHUB_API},
            )
            if proc.returncode != 0:
                continue
            data = json.loads(proc.stdout or "{}")
            items = data.get("comments") or data.get("items") or []
            result[slug] = {"comments": len(items)}
        except Exception:  # noqa: BLE001
            continue
    return result


def github_stats(token: str) -> dict:
    if not token:
        return {}
    try:
        repo = http_json("https://api.github.com/repos/%s" % GH_REPO, token)
        issues = http_json("https://api.github.com/repos/%s/issues?state=open&per_page=100" % GH_REPO, token)
        open_issues = [i for i in issues if "pull_request" not in i] if isinstance(issues, list) else []
        return {"stars": repo.get("stargazers_count", 0), "forks": repo.get("forks_count", 0),
                "open_issues": len(open_issues)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:120]}


def load_prev() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def delta(cur, prev, key):
    """返回 (当前值, 增量文案)。首次运行不显示增量。"""
    c = cur.get(key)
    if c is None:
        return None
    p = prev.get(key)
    if isinstance(p, (int, float)) and isinstance(c, (int, float)) and c > p:
        return "%s（↑%d）" % (c, c - p)
    return str(c)


def build_report(hub: list, comments: dict, gh: dict, prev: dict, namespace: str) -> str:
    prev_hub = {r.get("slug"): r for r in prev.get("hub", []) if isinstance(r, dict)}
    prev_gh = prev.get("github", {}) or {}
    prev_comments = prev.get("comments", {}) or {}

    lines = []

    found = [r for r in hub if r.get("found")]
    missing = [r for r in hub if not r.get("found")]
    if found or missing:
        if found:
            total_installs = sum(r.get("installs", 0) for r in found)
            total_stars = sum(r.get("stars", 0) for r in found)
            total_comments = sum((comments.get(r["slug"], {}) or {}).get("comments", 0) for r in found)
            prev_total_installs = sum(r.get("installs", 0) for r in prev.get("hub", []) if isinstance(r, dict))
            installs_txt = str(total_installs)
            if total_installs > prev_total_installs:
                installs_txt += "（↑%d）" % (total_installs - prev_total_installs)
            lines.append("**SkillHub**（@%s）: 安装 %s · 收藏 %d · 评论 %d"
                         % (namespace, installs_txt, total_stars, total_comments))
            for r in found:
                c = (comments.get(r["slug"], {}) or {}).get("comments", 0)
                cat = r.get("category") or "未分类"
                bump = ""
                pv = prev_hub.get(r["slug"], {})
                if r.get("installs", 0) > pv.get("installs", 0):
                    bump = " ↑%d" % (r["installs"] - pv.get("installs", 0))
                if c and c > prev_comments.get(r["slug"], 0):
                    bump += " 💬新 %d" % (c - prev_comments.get(r["slug"], 0))
                lines.append("  · %s：安装 %d%s · 收藏 %d · 评论 %d｜%s" % (
                    r["name"], r.get("installs", 0), bump, r.get("stars", 0), c, cat))
        else:
            lines.append("**SkillHub**（@%s）: 暂时读不到数据" % namespace)
        if missing:
            lines.append("  · 另有 %d 个尚未公开（审核中）：%s" % (
                len(missing), "、".join(r["name"] for r in missing)))

    if gh and not gh.get("error"):
        s = delta(gh, prev_gh, "stars")
        i = delta(gh, prev_gh, "open_issues")
        lines.append("**GitHub**: ★ %s · fork %s · 未关闭 Issue %s" % (s, gh.get("forks", 0), i))
    elif gh.get("error"):
        lines.append("**GitHub**: 读取失败（%s）" % gh["error"])

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--slot", choices=["all", "hub", "github"], default="all")
    ap.add_argument("--namespace", default=os.environ.get("SKILLHUB_NAMESPACE", "indiv-ai-audit"))
    args = ap.parse_args()

    load_env_file()
    hub_token = os.environ.get("SKILLHUB_TOKEN", "")
    gh_token = os.environ.get("GITHUB_TOKEN", "")

    hub = skillhub_stats(hub_token) if args.slot in ("all", "hub") else []
    comments = skillhub_comments(hub_token, args.namespace) if args.slot in ("all", "hub") else {}
    gh = github_stats(gh_token) if args.slot in ("all", "github") else {}

    prev = load_prev()
    report = build_report(hub, comments, gh, prev, args.namespace)

    if args.json:
        print(json.dumps({"hub": hub, "comments": comments, "github": gh, "report": report},
                         ensure_ascii=False, indent=2))
    else:
        print(report)

    # 记录本次快照（下次用于算增量）
    save_state({
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "hub": hub,
        "comments": {k: (v or {}).get("comments", 0) for k, v in comments.items()},
        "github": gh,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
