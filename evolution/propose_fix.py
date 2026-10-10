#!/usr/bin/env python3
"""
把「测试/验收失败」变成一条**可审批的修复提案（Pull Request）**。

审批 = 在 GitHub 上合并这个 PR（GitHub 原生 diff 审阅 + CI 校验 + 合并即生效）。
拒绝 = 关闭 PR（不改任何东西）。

流程：
  1. 读失败（state.json 的 open_failures + 最近一次验收结果的失败用例）。
  2. 若无失败 → 直接退出。
  3. 若已有未关闭的 proposal PR → 不重复开（避免每天刷屏）。
  4. 建分支 → 用 OpenCode（`opencode run --auto`）尝试修复 → 有改动才继续。
  5. commit + push + 开 PR（含失败详情 + 校验结果）。
  6. 企业微信通知：有新的待审批提案 + PR 链接。

需要环境变量：GITHUB_TOKEN（拉 PR / push 用）。绝不写进仓库。
用法：
  GITHUB_TOKEN=... python3 evolution/propose_fix.py            # 真的开 PR
  GITHUB_TOKEN=... python3 evolution/propose_fix.py --dry-run  # 只打印将要做什么
"""
import argparse
import json
import sys
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_classify import split_acceptance  # noqa: E402

STATE_FILE = ROOT / "evolution" / "state.json"
ACCEPT_DIR = ROOT / "evals" / "cross-agent" / "results"
REPO = "andrew-tao-li/ai-audit-skills"
API = "https://api.github.com"


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, **kw)


def collect_failures():
    """汇总失败：F1 的 open_failures + 最近一次验收的**真实**失败用例。

    v2026-10-10：网络类错误与"检测未完成"归入 not_run，**不计入失败、不触发提案**
    （此前把当晚的 GitHub TLS 抖动当成代码缺陷，误开了 PR #6）。
    """
    failures = {"blackbox": [], "acceptance": [], "not_run": []}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        failures["blackbox"] = state.get("open_failures", [])
    # 最近一次验收结果
    if ACCEPT_DIR.exists():
        jsons = sorted(ACCEPT_DIR.glob("*.json"))
        if jsons:
            latest = json.loads(jsons[-1].read_text(encoding="utf-8"))
            split = split_acceptance(latest.get("results", []))
            failures["acceptance"] = [
                {"id": r["id"], "prompt": r.get("prompt", ""),
                 "failed_checks": [c["name"] for c in r.get("checks", []) if not c.get("ok")],
                 "error": r.get("error")}
                for r in split["real"]
            ]
            failures["not_run"] = [
                {"id": r["id"], "reason": "网络抖动 / 检测未完成（不判为代码缺陷）"}
                for r in split["not_run"]
            ]
    return failures


def total(failures):
    return len(failures["blackbox"]) + len(failures["acceptance"])


def gh_api(method, path, token, body=None):
    import urllib.request
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Authorization": "Bearer %s" % token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "audit-propose-fix",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def has_open_proposal(token, label="proposal"):
    try:
        prs = gh_api("GET", "/repos/%s/pulls?state=open&per_page=100" % REPO, token)
        return any(label in [l["name"] for l in pr.get("labels", [])] for pr in prs)
    except Exception:
        return False


def push_branch(branch):
    """推分支：先走默认 remote（SSH），失败则回退到 token 认证的 HTTPS。

    2026-09-29 教训：本机代理会偶发劫持 SSH（解析到 198.18.x.x），
    无人值守的自动化如果只依赖 SSH，就会静默推不上去。
    """
    import os as _os
    r = run(["git", "push", "-u", "origin", branch])
    if r.returncode == 0:
        return r
    token = _os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return r
    url = "https://x-access-token:%s@github.com/%s.git" % (token, REPO)
    return run(["git", "push", "-u", url, branch])


def start_proposal_branch(branch):
    """隔离工作区：先把无关改动 stash 起来，再建提案分支。

    否则 `git add -A` 会把工作区里所有未提交的东西（如例行写出的 state.json、日志、
    甚至未提交的手工改动）一起扫进 PR。返回 (是否需要恢复 stash, 建分支是否成功)。
    """
    dirty = run(["git", "status", "--porcelain"]).stdout.strip()
    stashed = False
    if dirty:
        r = run(["git", "stash", "push", "-u", "-m", "pre-proposal-isolation"])
        stashed = r.returncode == 0
    ok = run(["git", "checkout", "-b", branch]).returncode == 0
    return stashed, ok


def finish_proposal(stashed):
    """回到 main（或原分支）并恢复之前 stash 的改动。"""
    cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if cur != "main":
        run(["git", "checkout", "main"])
    if stashed:
        run(["git", "stash", "pop"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-notify", action="store_true", help="不发通知（测试用，避免打扰）")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    failures = collect_failures()
    n = total(failures)
    print("失败汇总：F1=%d，验收=%d（另有 %d 条未执行，不计入），合计=%d" % (len(failures["blackbox"]), len(failures["acceptance"]), len(failures.get("not_run", [])), n))
    if n == 0:
        print("无失败，无需提案。")
        return 0

    if not token:
        print("⚠ 未设置 GITHUB_TOKEN，无法开 PR（dry-run 继续）。", file=sys.stderr)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    branch = "proposal/%s" % ts

    if not args.dry_run and token and has_open_proposal(token):
        print("已有未关闭的 proposal PR，跳过（避免重复）。")
        return 0

    if args.dry_run:
        print("[dry-run] 将建分支 %s，用 OpenCode 尝试修复 %d 条失败，然后开 PR。" % (branch, n))
        print(json.dumps(failures, ensure_ascii=False, indent=2)[:1500])
        return 0

    # 1. 隔离工作区 + 建分支
    stashed, ok = start_proposal_branch(branch)
    if not ok:
        print("建分支失败（可能已存在）", file=sys.stderr)
        return 1

    # 2. 用 OpenCode 尝试修复（只在必要时改文件）
    prompt = (
        "以下是本项目的测试/验收失败。请先理解失败原因，**只在必要时**修改最少的文件来修复。"
        "不要重写无关代码，不要改测试期望来掩盖问题。修完后不要提交，只改工作区文件。\n\n"
        "## F1 失败\n%s\n\n## OpenCode 验收失败\n%s\n"
        % (json.dumps(failures["blackbox"], ensure_ascii=False, indent=2)[:4000],
           json.dumps(failures["acceptance"], ensure_ascii=False, indent=2)[:4000])
    )
    run(["opencode", "run", prompt, "--auto"], timeout=args.timeout)

    # 3. 有改动吗？
    changed = run(["git", "status", "--porcelain"]).stdout.strip()
    if not changed:
        print("OpenCode 未产生改动，放弃提案。")
        finish_proposal(stashed)
        run(["git", "branch", "-D", branch])
        return 0

    # 4. commit + push
    run(["git", "add", "-A"])
    run(["git", "commit", "-m", "proposal: 自动修复建议 %s（待人工审批）" % ts])
    push = push_branch(branch)
    if push.returncode != 0:
        print("push 失败：%s" % push.stderr[:300], file=sys.stderr)
        return 1

    # 5. 开 PR
    body_lines = ["本 PR 由自动化生成，**需要人工审批**（合并即采纳，关闭即拒绝）。", "",
                  "## 触发原因", "",
                  "- F1 失败：%d 条" % len(failures["blackbox"]),
                  "- OpenCode 验收失败：%d 条" % len(failures["acceptance"]), ""]
    if failures["acceptance"]:
        body_lines.append("## 验收失败明细")
        for f in failures["acceptance"]:
            body_lines.append("- `%s`：%s" % (f["id"], "、".join(f.get("failed_checks") or [f.get("error") or "未通过"])))
        body_lines.append("")
    body_lines += ["## 审批前请确认", "",
                   "- [ ] diff 只改了必要的文件",
                   "- [ ] CI（F1 + 单元测试）全绿",
                   "- [ ] 没有为了过测试而改测试期望", ""]
    try:
        pr = gh_api("POST", "/repos/%s/pulls" % REPO, token, {
            "title": "[改进提案 %s] 自动修复 %d 条失败" % (ts, n),
            "head": branch, "base": "main", "body": "\n".join(body_lines),
        })
        pr_url = pr.get("html_url", "")
        # 打标签
        if pr.get("number"):
            try:
                gh_api("POST", "/repos/%s/issues/%d/labels" % (REPO, pr["number"]), token, {"labels": ["proposal"]})
            except Exception:
                pass
        print(pr_url)
        # 6. 通知
        notify_sh = ROOT / "evolution" / "notify.sh"
        if (not args.no_notify) and notify_sh.exists():
            body = ("自动生成了 1 个修复 PR（针对 {n} 条失败）。\n\n"
                    "在 GitHub 的 **Pull requests** 里审阅：**合并 = 采纳，关闭 = 拒绝**。\n"
                    "{url}\n\n"
                    "全部待审批 PR：https://github.com/andrew-tao-li/ai-audit-skills/pulls?q=is%3Apr+is%3Aopen").format(
                        n=n, url=pr_url)
            subprocess.run(["bash", str(notify_sh), "[Audit Box] 有 1 个待审批的 Pull Request", body],
                           cwd=str(ROOT), capture_output=True, text=True)
        # 回到 main + 恢复工作区
        finish_proposal(stashed)
    except Exception as e:  # noqa: BLE001
        print("开 PR 失败：%s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
