#!/usr/bin/env python3
"""
构建 SkillHub.cn 专用「净化版」（目标是过平台的三线安全审核）。

为什么需要单独一份：
  SkillHub 上架前会跑「内容合规过滤 + 科恩实验室漏洞扫描 + 云鼎 AI 模型安全评估」。
  canonical 版本（skills-v2/）里有两处对 GitHub 分发是合理的，但会被安全审核盯上：
    1. 反馈机制把统计 POST 到作者的固定 webhook（references/feedback.md 里有硬编码 key）
    2. SKILL.md 里的 `curl ... | bash` 一键更新指令
  另外 SkillHub 要求 SKILL.md frontmatter 含 slug / displayName / version / summary / license。

本脚本从 skills-v2/ 生成 dist-v2/skillhub/<skill>/，做以下净化：
  - 删 references/feedback.md、scripts/build_feedback.py（去掉硬编码 key 与数据外发）
  - SKILL.md：删「版本检查与一键更新」「匿名反馈」两节，换成无外发的「反馈与更新」
  - SKILL.md：frontmatter 补 SkillHub 字段，去掉超长 changelog
  - 代码：规范化 __import__("pathlib") 这类动态导入写法（避免扫描器误报）

canonical（skills-v2/）与 GitHub release 完全不受影响。

用法：
  python3 scripts/build-skillhub.py                # 构建 + 校验
  python3 scripts/build-skillhub.py --verify-only  # 只校验已构建的产物
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "skills-v2"
OUT_ROOT = ROOT / "dist-v2" / "skillhub"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skillhub_config import SKILLS, LICENSE, HOMEPAGE  # noqa: E402  分类/文案的单一来源

# 要删掉的小节（按标题前缀匹配，删到下一个 ## 之前）
DROP_SECTIONS = ["版本检查与一键更新", "匿名反馈"]

FEEDBACK_SECTION = """## 反馈与更新

- **更新**：本技能通过 SkillHub 发布，版本由平台管理；如需更新，请在 SkillHub 中更新该技能。
- **反馈**：欢迎在 GitHub 仓库提交 Issue：<https://github.com/andrew-tao-li/ai-audit-skills/issues>
- 本技能的离线脚本**不做任何网络请求**，也**不会上传任何数据**。
"""

# 扫描器敏感的写法 → 规范化（净化版专用；canonical 保持原样）
CODE_RULES = [
    (re.compile(r'__import__\("pathlib"\)\.Path\(([^)]*)\)'), r"Path(\1)"),
]


def ensure_pathlib_import(text: str) -> str:
    """规范化后若用到 Path 但没导入，补一行 import（插在第一段 import 块末尾，保持分组顺序）。"""
    if re.search(r"(?m)^from pathlib import Path\s*$", text):
        return text
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if re.match(r"^(import |from )\S", l)), None)
    if start is None:
        return "from pathlib import Path\n" + text
    last, i = start, start
    while i < len(lines):
        line = lines[i]
        if re.match(r"^(import |from )\S", line):
            last = i
        elif line.strip() == "" and i > start:
            break
        elif line.strip():
            break
        i += 1
    lines.insert(last + 1, "from pathlib import Path")
    return "\n".join(lines)

FORBIDDEN = [
    ("qyapi.weixin.qq.com", "硬编码 webhook 地址"),
    ("d8dcd436", "硬编码 webhook key"),
    ("build_feedback", "反馈外发脚本引用"),
    ("__import__", "动态导入写法"),
]

# curl ... | bash / sh 形式的远程执行（单独用正则，避免 Markdown 表格里的 `| bash` 误报）
REMOTE_EXEC = re.compile(r"curl[^\n]*\|[^\n]*\b(?:sh|bash)\b")


def drop_section(text: str, prefix: str) -> tuple:
    pat = re.compile(r"\n## " + re.escape(prefix) + r"[^\n]*\n.*?(?=\n## )", re.S)
    new, n = pat.subn("\n", text)
    return new, n


def transform_skill_md(text: str, cfg: dict) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError("SKILL.md 缺少 frontmatter")
    fm, body = m.group(1), text[m.end():]

    # 去掉超长 changelog（内部细节多，且含已删除功能的描述）
    fm = re.sub(r"\n[ \t]+changelog:.*", "", fm)

    extra = ("\nslug: %s\ndisplayName: %s\nsummary: %s\nlicense: %s\nhomepage: %s\ntags: [%s]"
             % (cfg["slug"], cfg["display_name"], cfg["summary"], LICENSE, HOMEPAGE, ", ".join(cfg["tags"])))
    fm = re.sub(r"(?m)^(version:.*)$", lambda mm: mm.group(1) + extra, fm, count=1)

    # 删两节 → 插入新的「反馈与更新」
    for prefix in DROP_SECTIONS:
        body, _ = drop_section(body, prefix)
    if re.search(r"(?m)^## References", body):
        body = re.sub(r"(?m)^## References", FEEDBACK_SECTION + "\n## References", body, count=1)
    else:
        body = body.rstrip("\n") + "\n\n" + FEEDBACK_SECTION

    return "---\n" + fm + "\n---\n" + body


def build_one(skill: str, cfg: dict) -> Path:
    src, dst = SRC_ROOT / skill, OUT_ROOT / skill
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    # 删掉外发相关文件
    for rel in ("references/feedback.md", "scripts/build_feedback.py"):
        p = dst / rel
        if p.exists():
            p.unlink()

    # SKILL.md 净化
    p = dst / "SKILL.md"
    p.write_text(transform_skill_md(p.read_text(encoding="utf-8"), cfg), encoding="utf-8")

    # 代码规范化（动态导入 → 常规 import，并补上 import 行）
    for py in dst.rglob("*.py"):
        t = py.read_text(encoding="utf-8")
        orig = t
        for pat, rep in CODE_RULES:
            t = pat.sub(rep, t)
        if t != orig:
            t = ensure_pathlib_import(t)
            py.write_text(t, encoding="utf-8")
    return dst


def verify() -> list:
    problems = []
    for skill, cfg in SKILLS.items():
        d = OUT_ROOT / skill
        if not d.exists():
            problems.append("%s: 产物不存在" % skill)
            continue
        # 1. 禁用内容
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            try:
                t = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for needle, why in FORBIDDEN:
                if needle in t:
                    problems.append("%s: %s → 命中 '%s'" % (skill, f.relative_to(d), needle))
            if REMOTE_EXEC.search(t):
                problems.append("%s: %s → 命中 curl|bash 远程执行" % (skill, f.relative_to(d)))
        # 2. 外发文件已删
        for rel in ("references/feedback.md", "scripts/build_feedback.py"):
            if (d / rel).exists():
                problems.append("%s: 未删除 %s" % (skill, rel))
        # 3. frontmatter 字段齐全
        fm = re.match(r"^---\n(.*?)\n---\n", (d / "SKILL.md").read_text(encoding="utf-8"), re.S)
        fmtext = fm.group(1) if fm else ""
        for field in ("slug:", "displayName:", "version:", "summary:", "license:", "homepage:", "tags:"):
            if field not in fmtext:
                problems.append("%s: frontmatter 缺 %s" % (skill, field))
        if cfg["slug"] not in fmtext:
            problems.append("%s: slug 与预期不符" % skill)
        # 4. 核心脚本仍在
        for rel in ("SKILL.md", "manifest.json"):
            if not (d / rel).exists():
                problems.append("%s: 缺 %s" % (skill, rel))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    if not args.verify_only:
        OUT_ROOT.mkdir(parents=True, exist_ok=True)
        for skill, cfg in SKILLS.items():
            d = build_one(skill, cfg)
            print("✓ 构建 %s → %s" % (skill, d.relative_to(ROOT)))

    print("\n" + "=" * 60)
    print("净化版校验")
    print("=" * 60)
    problems = verify()
    if problems:
        for p in problems:
            print("  ❌ " + p)
        print("\n结果：%d 个问题" % len(problems))
        return 1
    print("  ✅ 无硬编码 key / 无数据外发 / 无 curl|bash / 无动态导入")
    print("  ✅ frontmatter 含 slug/displayName/version/summary/license/homepage/tags")
    print("  ✅ 核心脚本与文档完整")
    print("\n结果：全部通过（%d 个 skill）" % len(SKILLS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
