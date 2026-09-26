#!/usr/bin/env python3
"""
定期主动巡检：即使没有失败，也定期让 Agent 审视 skill 并**提议一条具体的小改进**（开 PR 供人工审批）。

和 propose_fix.py 的区别：
  - propose_fix.py：有「失败」时，针对失败做修复。
  - patrol.py     ：没失败时，主动找一个「可改进点」，做**最小必要**的改动。

为避免乱改，每次巡检只看**一个审视角度（lens）**，按周轮换；且强约束「只做最小必要改动、不改测试期望、一个 PR 只解决一件事」。

需要 GITHUB_TOKEN。用法：
  GITHUB_TOKEN=... python3 evolution/patrol.py            # 按本周 lens 巡检
  GITHUB_TOKEN=... python3 evolution/patrol.py --lens 2   # 指定 lens
  GITHUB_TOKEN=... python3 evolution/patrol.py --dry-run  # 只看会怎么做
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from propose_fix import ROOT, gh_api, has_open_proposal, run, start_proposal_branch, finish_proposal  # noqa: E402

LAST_PATROL = HERE / "log" / ".last_patrol"

LENSES = [
    ("描述与触发准确性",
     "审视 4 个 skill 的 description（`SKILL.md` frontmatter + `manifest.json`）：触发词是否有歧义、是否漏了常见说法、是否过宽（会误触发无关请求）。只做最小必要的措辞修正。"),
    ("文档一致性",
     "审视 `README.md` / `README.zh.md` / `install.md` / 各 `SKILL.md`：版本号、目录结构、skill 数量、命令示例是否一致、是否过时。只做最小必要修正。"),
    ("规则覆盖盲点",
     "审视 expense / procurement 的规则目录与 `references/rule-catalog.md`，指出**一个**最明显的覆盖盲点，并只做**最小**的文档说明或规则骨架（不要大改、不要动测试期望）。"),
    ("审计语言可用性",
     "审视 `summary.md` / `dashboard.html` / findings 的文案，是否还有技术术语或不友好表述（英文 key、MAD、peer group 之类）。只做最小必要的措辞修正。"),
]


def week_number():
    return int(datetime.now(timezone.utc).strftime("%V"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lens", type=int, default=None, help="指定审视角度编号（0-3）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-notify", action="store_true", help="不发通知（测试用，避免打扰）")
    ap.add_argument("--force", action="store_true", help="忽略「距上次不足 7 天」的限制")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if token and not args.dry_run and has_open_proposal(token):
        print("已有未关闭的 proposal PR，跳过巡检（避免刷屏）。")
        return 0

    lens_idx = args.lens if args.lens is not None else (week_number() % len(LENSES))
    lens_name, lens_prompt = LENSES[lens_idx]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    branch = "patrol/%s" % ts
    print("本周巡检角度：%s（#%d）" % (lens_name, lens_idx))

    if args.dry_run:
        print("[dry-run] 将建分支 %s，用 OpenCode 按上述角度找一条改进，若有改动则开 PR。" % branch)
        return 0

    # 隔离工作区 + 建分支
    stashed, ok = start_proposal_branch(branch)
    if not ok:
        print("建分支失败", file=sys.stderr)
        return 1

    prompt = (
        "你是本审计技能包的维护助手。现在做一次**定期主动巡检**，只关注一个角度：\n\n"
        "## 审视角度：%s\n%s\n\n"
        "## 硬约束（务必遵守）\n"
        "1. **只做最小必要的改动**，一个 PR 只解决一件事。\n"
        "2. **不要改测试期望**来掩盖问题；如果发现的问题无法用最小改动解决，就**不做改动**并说明原因。\n"
        "3. 不改与本次角度无关的文件。\n"
        "4. 改完后**不要 git 提交**，只改工作区文件。\n"
        "5. 如果没找到值得改的点，就什么都不改。\n"
    ) % (lens_name, lens_prompt)
    run(["opencode", "run", prompt, "--auto"], timeout=args.timeout)

    changed = run(["git", "status", "--porcelain"]).stdout.strip()
    if not changed:
        print("本次巡检未发现值得改的点，放弃提案。")
        finish_proposal(stashed)
        run(["git", "branch", "-D", branch])
        return 0

    run(["git", "add", "-A"])
    run(["git", "commit", "-m", "patrol: 定期巡检改进建议（%s，待人工审批）" % lens_name])
    push = run(["git", "push", "-u", "origin", branch])
    if push.returncode != 0:
        print("push 失败：%s" % push.stderr[:300], file=sys.stderr)
        return 1

    body = (
        "本 PR 由**定期主动巡检**生成（不是因为有失败），**需要人工审批**（合并即采纳，关闭即拒绝）。\n\n"
        "## 巡检角度\n\n%s\n\n"
        "## 审批前请确认\n\n"
        "- [ ] diff 确实**最小必要**、只解决这一件事\n"
        "- [ ] CI（F1 + 单测）全绿\n"
        "- [ ] 没有为了过测试而改测试期望\n" % lens_name
    )
    try:
        pr = gh_api("POST", "/repos/andrew-tao-li/ai-audit-skills/pulls", token, {
            "title": "[定期巡检 %s] %s" % (ts, lens_name),
            "head": branch, "base": "main", "body": body,
        })
        pr_url = pr.get("html_url", "")
        if pr.get("number"):
            try:
                gh_api("POST", "/repos/andrew-tao-li/ai-audit-skills/issues/%d/labels" % pr["number"], token, {"labels": ["proposal", "patrol"]})
            except Exception:
                pass
        print(pr_url)
        notify_sh = HERE / "notify.sh"
        if (not args.no_notify) and notify_sh.exists():
            body = ("定期巡检（{lens}）提出了 1 个改进 PR（#{num}）。\n\n"
                    "在 GitHub 的 **Pull requests** 里审阅：**合并 = 采纳，关闭 = 拒绝**。\n"
                    "{url}\n\n"
                    "全部待审批 PR：https://github.com/andrew-tao-li/ai-audit-skills/pulls?q=is%3Apr+is%3Aopen").format(
                        lens=lens_name, num=pr.get("number", "?"), url=pr_url)
            subprocess.run(["bash", str(notify_sh), "[Audit Box] 有 1 个待审批的 Pull Request", body],
                           cwd=str(ROOT), capture_output=True, text=True)
        finish_proposal(stashed)
        LAST_PATROL.parent.mkdir(parents=True, exist_ok=True)
        LAST_PATROL.write_text(ts, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print("开 PR 失败：%s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
