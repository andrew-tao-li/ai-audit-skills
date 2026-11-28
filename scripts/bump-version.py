#!/usr/bin/env python3
"""统一升 skill 版本号（4 处必须对齐）+ 追加 changelog 条目。

为什么需要这个工具
  版本号散在 4 个地方，历史上踩过「脚本里的 VERSION 忘了升」的坑
  （见 CHANGELOG v0.2.46：脚本内 VERSION 停在 0.2.43）。这里一处改、4 处齐升，
  并在结束时自检一致性。

改动的地方（每个 skill）：
  1. skills-v2/<s>/SKILL.md      frontmatter 的 version:
  2. skills-v2/<s>/manifest.json  version
  3. skills-v2/<s>/scripts/*.py   VERSION = "..."
  4. VERSIONS.json                skills.<name>

用法
  python3 scripts/bump-version.py --map expense-audit-v2=0.2.49 --changelog "说明文字"
  python3 scripts/bump-version.py --bump expense-audit-v2 --changelog "说明文字"   # 自动 +1 补丁号
  python3 scripts/bump-version.py --check                                          # 只查一致性
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills-v2"


def bump_patch(v: str) -> str:
    """0.2.48 → 0.2.49；0.1.9 → 0.1.10（补丁位进位）。"""
    parts = v.split(".")
    if len(parts) != 3:
        raise ValueError("版本号格式不对: %s" % v)
    major, minor, patch = parts
    return "%s.%s.%d" % (major, minor, int(patch) + 1)


def set_skill_version(skill: str, new_v: str, changelog: str) -> str:
    """把一个 skill 的 4 处版本号对齐，返回旧版本号。"""
    d = SKILLS_DIR / skill
    if not d.is_dir():
        raise SystemExit("✗ 没有这个 skill: %s" % skill)

    # 1) SKILL.md frontmatter（只动顶层 version 行；changelog 追加到 metadata.changelog 开头）
    sk = d / "SKILL.md"
    t = sk.read_text(encoding="utf-8")
    m = re.search(r"(?m)^version:[ \t]*(\S+)[ \t]*$", t)
    if not m:
        raise SystemExit("✗ %s/SKILL.md 里找不到 version 行" % skill)
    old_v = m.group(1)
    t = t[:m.start()] + "version: %s" % new_v + t[m.end():]
    # changelog：插到 metadata.changelog 开头（单行长字符串格式）
    mc = re.search(r'(?m)^([ \t]*)changelog:[ \t]*"(.*)"[ \t]*$', t)
    if mc:
        new_entry = "v%s: %s | " % (new_v, changelog)
        t = t[:mc.start()] + '%schangelog: "%s%s"' % (mc.group(1), new_entry, mc.group(2)) + t[mc.end():]
    sk.write_text(t, encoding="utf-8")

    # 2) manifest.json
    mf = d / "manifest.json"
    m2 = json.loads(mf.read_text(encoding="utf-8"))
    m2["version"] = new_v
    mf.write_text(json.dumps(m2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 3) 脚本里的 VERSION 常量
    for py in sorted((d / "scripts").glob("*.py")):
        s = py.read_text(encoding="utf-8")
        s2, n = re.subn(r'(?m)^(VERSION\s*=\s*")[^"]+(")', rf'\g<1>{new_v}\g<2>', s, count=1)
        if n:
            py.write_text(s2, encoding="utf-8")

    # 4) VERSIONS.json
    vf = ROOT / "VERSIONS.json"
    v = json.loads(vf.read_text(encoding="utf-8"))
    v["skills"][skill] = new_v
    vf.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return old_v


def check() -> int:
    """自检：4 处版本号是否一致。"""
    vf = ROOT / "VERSIONS.json"
    v = json.loads(vf.read_text(encoding="utf-8"))
    bad = 0
    for skill, want in v.get("skills", {}).items():
        d = SKILLS_DIR / skill
        got = {}
        sk = d / "SKILL.md"
        m = re.search(r"(?m)^version:[ \t]*(\S+)[ \t]*$", sk.read_text(encoding="utf-8"))
        got["SKILL.md"] = m.group(1) if m else "?"
        mf = d / "manifest.json"
        got["manifest.json"] = json.loads(mf.read_text(encoding="utf-8")).get("version", "?")
        script_vs = []
        for py in sorted((d / "scripts").glob("*.py")):
            s = py.read_text(encoding="utf-8")
            mm = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', s)
            if mm:
                script_vs.append("%s=%s" % (py.name, mm.group(1)))
        got["scripts"] = ",".join(script_vs) or "—"
        same = (got["SKILL.md"] == want and got["manifest.json"] == want
                and all(s.endswith("=" + want) for s in script_vs))
        print("  %-28s VERSIONS=%s  SKILL.md=%s  manifest=%s  scripts: %s  %s" % (
            skill, want, got["SKILL.md"], got["manifest.json"], got["scripts"],
            "✅" if same else "❌ 不一致"))
        if not same:
            bad += 1
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", action="append", default=[], help="skill=版本号（可重复）")
    ap.add_argument("--bump", action="append", default=[], help="skill（自动补丁号 +1，可重复）")
    ap.add_argument("--changelog", default="")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.check:
        return check()

    if not args.map and not args.bump:
        ap.print_help()
        return 1
    if not args.changelog:
        print("✗ 必须给 --changelog（写清楚这次改了什么）", file=sys.stderr)
        return 1

    for spec in args.map:
        if "=" not in spec:
            print("✗ --map 格式应为 skill=版本号", file=sys.stderr)
            return 1
        skill, new_v = spec.split("=", 1)
        old = set_skill_version(skill.strip(), new_v.strip(), args.changelog)
        print("  ✓ %-28s %s → %s" % (skill.strip(), old, new_v.strip()))
    for skill in args.bump:
        vf = ROOT / "VERSIONS.json"
        cur = json.loads(vf.read_text(encoding="utf-8"))["skills"][skill.strip()]
        new_v = bump_patch(cur)
        old = set_skill_version(skill.strip(), new_v, args.changelog)
        print("  ✓ %-28s %s → %s" % (skill.strip(), old, new_v))

    print("\n=== 一致性自检 ===")
    return check()


if __name__ == "__main__":
    sys.exit(main())
