#!/usr/bin/env python3
"""
安装冒烟测试：验证「用户真正的安装路径」能走通。

背景：用户/测试者是从 GitHub release 装的，**不是**从 main 分支。所以除了「仓库代码能不能跑」，
还必须验证「发出去、装下来的那份能不能跑」。这一步以前完全没有覆盖，已因此踩过两次坑
（传错 release、改了 main 忘记重打包重传）。

端到端检查：
  1. release 与 main 版本一致            —— 抓「改了代码忘记重打包/重传 release」
  2. release zip 与本机 dist 的 sha256 一致 —— 抓「上传了错的 zip」
  3. install.sh 能把 skill 装到临时目录     —— 走真实的安装脚本
  4. 装好的 skill 能在自带样例上跑出预期产出 —— 走真实的运行路径
  5. 装好的 dashboard 含新版首屏标记         —— 抓「release 里其实是旧代码」

用法：
  python3 evals/install_smoke.py                       # 全部 skill
  python3 evals/install_smoke.py --skill expense-audit-v2
  python3 evals/install_smoke.py --no-notify
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = "andrew-tao-li/ai-audit-skills"
SKILLS = [
    "expense-audit-v2",
    "procurement-fraud-v2",
    "investigation-assistant-v2",
    "cn-entity-relation-check",
]
DIST_DIR = ROOT / "dist-v2" / "zips"
UA = "ai-audit-install-smoke"

# 新版 dashboard 必须具备的首屏标记（抓「release 里是旧代码」）
DASHBOARD_MARKERS = ["firstpage", "建议下一步"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def http_get(url: str, dest: Path) -> None:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def version_in_skill_md(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return ""


def check_release(skill: str, expected_version: str, tmp: Path, results: list) -> None:
    """下载 release zip，核对版本与 sha256。"""
    url = "https://github.com/%s/releases/latest/download/%s.zip" % (REPO, skill)
    dest = tmp / ("%s.zip" % skill)
    try:
        http_get(url, dest)
    except Exception as e:  # noqa: BLE001
        results.append((skill, "下载 release", False, str(e)))
        return

    with zipfile.ZipFile(dest) as z:
        try:
            md = z.read("SKILL.md").decode("utf-8")
        except KeyError:
            results.append((skill, "release 含 SKILL.md", False, "zip 内没有 SKILL.md"))
            return
        has_feedback_ref = any(n.endswith("references/feedback.md") for n in z.namelist())
    rel_v = version_in_skill_md(md)
    results.append((skill, "release 版本 == main(VERSIONS.json)",
                    rel_v == expected_version, "release=%s / main=%s" % (rel_v, expected_version)))
    results.append((skill, "release 含 references/feedback.md", has_feedback_ref, ""))

    local_zip = DIST_DIR / ("%s.zip" % skill)
    if local_zip.exists():
        # 注意：刚重传过 release 资产时，releases/latest/download 可能短暂返回**旧字节**（CDN 缓存），
        # 此时这里会误报。等一两分钟重跑即可；持续不一致才是「传错 zip」。
        same = sha256(local_zip) == sha256(dest)
        results.append((skill, "release sha256 == 本机 dist", same, "" if same else "zip 不一致（可能传错）"))


def install_all(tmp: Path, results: list) -> Path:
    """用 install.sh 把全部 skill 装到临时 PREFIX（真实安装脚本）。"""
    prefix = tmp / "installed"
    prefix.mkdir(parents=True, exist_ok=True)
    env = {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", "HOME": str(Path.home())}
    proc = subprocess.run(
        ["bash", str(ROOT / "install.sh")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        env={**env, "PREFIX": str(prefix), "HOST": "opencode"},
    )
    ok = proc.returncode == 0
    results.append(("(install.sh)", "install.sh 退出码 0", ok, (proc.stderr or "")[-200:] if not ok else ""))
    return prefix


def run_installed_expense(prefix: Path, tmp: Path, results: list) -> None:
    """用「装好的」expense 跑自带样例，核对产出。"""
    skill_dir = prefix / "expense-audit-v2"
    script = skill_dir / "scripts" / "run_expense_audit.py"
    example = skill_dir / "examples" / "input"
    if not script.exists():
        results.append(("expense-audit-v2", "装好后能找到脚本", False, str(script)))
        return
    out = tmp / "run"
    proc = subprocess.run(
        ["python3", str(script), "--input", str(example / "expenses.csv"),
         "--policy", str(example / "policy.json"), "--output", str(out)],
        capture_output=True, text=True, timeout=180,
    )
    results.append(("expense-audit-v2", "装好的脚本能跑通", proc.returncode == 0, (proc.stderr or "")[-200:]))
    for name in ("findings.csv", "summary.md", "dashboard.html"):
        results.append(("expense-audit-v2", "产出 %s" % name, (out / name).exists(), ""))
    dash = out / "dashboard.html"
    if dash.exists():
        html = dash.read_text(encoding="utf-8")
        for m in DASHBOARD_MARKERS:
            results.append(("expense-audit-v2", "dashboard 含「%s」" % m, m in html, ""))

    # ★ 安全整改回归（2026-10-09，见 docs/reported-issues.md #2）：
    #    装出来的版本必须【不含外发通道 / 不含远程执行写法 / 不含隐瞒措辞 / 含前置风险披露】。
    md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    texts = []
    for f in sorted(skill_dir.rglob("*")):
        if f.is_file():
            try:
                texts.append(f.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                pass
    blob = "\n".join(texts)
    results.append(("expense-audit-v2", "装出来的版本无硬编码 webhook 地址/密钥",
                    ("qyapi.weixin.qq.com" not in blob) and ("webhook/send?key=" not in blob),
                    "发现外发地址或密钥"))
    results.append(("expense-audit-v2", "无「下载后管道交给解释器」写法",
                    re.search(r"curl[^\n]*\|[^\n]*\b(?:sh|bash)\b", blob) is None, "发现管道执行写法"))
    results.append(("expense-audit-v2", "无「不要向用户复述」类隐瞒措辞",
                    all(w not in blob for w in ("不要向用户", "不要向测试者", "不必再问一遍")),
                    "发现隐瞒措辞"))
    results.append(("expense-audit-v2", "含「联网与风险」前置披露", "联网与风险" in md, "缺披露"))
    results.append(("expense-audit-v2", "未混入 SkillHub 字段 slug:",
                    re.search(r"(?m)^slug:", md) is None, "有 → SkillHub 版混进了安装路径"))
    install_sh = (ROOT / "install.sh").read_text(encoding="utf-8").lower()
    results.append(("(install.sh)", "安装路径不引用净化版(skillhub)",
                    "skillhub" not in install_sh, "install.sh 里出现了 skillhub"))


def notify(passed: int, total: int) -> None:
    notify_sh = ROOT / "evolution" / "notify.sh"
    if not notify_sh.exists():
        return
    title = "[Audit Box] 安装冒烟 %d/%d" % (passed, total)
    body = "安装冒烟测试（从 release 装 + 跑）：**%d/%d 通过**。" % (passed, total)
    if passed != total:
        body += "\n\n⚠️ 有失败项——多半是「改了 main 忘记重打包/重传 release」，或传错了 zip。"
    subprocess.run(["bash", str(notify_sh), title, body], cwd=str(ROOT), capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", default=None, help="只测某个 skill 的 release 校验")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    versions = json.loads((ROOT / "VERSIONS.json").read_text(encoding="utf-8"))["skills"]
    skills = [args.skill] if args.skill else SKILLS

    results = []
    tmp = Path(tempfile.mkdtemp(prefix="install-smoke-"))
    try:
        for s in skills:
            check_release(s, versions.get(s, "?"), tmp, results)
        prefix = install_all(tmp, results)
        if "expense-audit-v2" in skills:
            run_installed_expense(prefix, tmp, results)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, _, ok, _ in results if ok)
    total = len(results)
    print("=" * 60)
    print("安装冒烟测试：%d/%d 通过" % (passed, total))
    print("=" * 60)
    for scope, name, ok, detail in results:
        mark = "✅" if ok else "❌"
        line = "  %s [%s] %s" % (mark, scope, name)
        if detail and not ok:
            line += "  ← %s" % detail
        print(line)

    if not args.no_notify and passed != total:
        notify(passed, total)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
