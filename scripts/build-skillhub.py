#!/usr/bin/env python3
"""
构建 SkillHub.cn 上架用的版本（目标是**平台适配 + 内容合规守卫**）。

背景（2026-10 更新）：
  原先 canonical 里有两处会被安全审核盯上的东西——硬编码反馈 webhook 与 curl|bash 一键更新；
  因此当时做了「净化版」。2026-10 一次企业安全审查驳回后（见 docs/reported-issues.md #2），
  按用户决定：**canonical 本身已移除这两类内容**。

所以本脚本现在只做**平台适配**，不再做「安全净化」（canonical 已合规）：
  - frontmatter 补 SkillHub 要求的 slug / displayName / summary / license / homepage / tags
  - 去掉超长 changelog（对 marketplace 是噪声，且含已删除功能的描述）
  - 代码规范化：__import__("pathlib") → 常规 import（避免扫描器误报「动态导入」）

并**校验**产物不含以下内容（守卫，防止将来回归）：
  - 任何 webhook 地址或密钥
  - 「下载后管道交给解释器」的写法（curl … | sh/bash）
  - 动态导入写法

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

# 扫描器敏感的写法 → 规范化（canonical 保持原样）
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


# 禁用内容（守卫）：出现在产物里即报错
FORBIDDEN = [
    ("qyapi.weixin.qq.com", "硬编码 webhook 地址"),
    ("__import__", "动态导入写法"),
]
# 用正则抓「webhook 地址/密钥」与「下载后管道执行」，避免把字面量写进本文件
WEBHOOK_KEY = re.compile(r"webhook/send\?key=[0-9A-Za-z-]{8,}")
REMOTE_EXEC = re.compile(r"curl[^\n]*\|[^\n]*\b(?:sh|bash)\b")


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

    return "---\n" + fm + "\n---\n" + body


def build_one(skill: str, cfg: dict) -> Path:
    src, dst = SRC_ROOT / skill, OUT_ROOT / skill
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    # SKILL.md 平台适配
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
        # 1. 禁用内容 / 合规守卫
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
            if WEBHOOK_KEY.search(t):
                problems.append("%s: %s → 命中 webhook 密钥" % (skill, f.relative_to(d)))
            if REMOTE_EXEC.search(t):
                problems.append("%s: %s → 命中「下载后管道执行」写法" % (skill, f.relative_to(d)))
        # 2. 前置风险披露必须在（用户 2026-10-09 要求：SkillHub 上不许隐瞒）
        md = (d / "SKILL.md").read_text(encoding="utf-8")
        if "联网与风险" not in md:
            problems.append("%s: SKILL.md 缺少「联网与风险」前置披露" % skill)
        # 3. frontmatter 字段齐全
        fm = re.match(r"^---\n(.*?)\n---\n", md, re.S)
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
    print("SkillHub 版校验")
    print("=" * 60)
    problems = verify()
    if problems:
        for p in problems:
            print("  ❌ " + p)
        print("\n结果：%d 个问题" % len(problems))
        return 1
    print("  ✅ 无 webhook 地址/密钥 / 无「下载后管道执行」/ 无动态导入")
    print("  ✅ 含「联网与风险」前置披露")
    print("  ✅ frontmatter 含 slug/displayName/version/summary/license/homepage/tags")
    print("  ✅ 核心脚本与文档完整")
    print("\n结果：全部通过（%d 个 skill）" % len(SKILLS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
