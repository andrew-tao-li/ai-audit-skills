#!/usr/bin/env python3
"""一次性完成：① 包内署名（NOTICE / LICENSE / README 署名行 / manifest notice / SKILL.md metadata）
② 5 个 skill 版本号统一升一位（内容变了版本必须跟着变）。

不动许可证条款：canonical 一直是 MIT-0（有意选择，见 README License 段），
本次只补**非约束性**署名与 NOTICE，并让包内自带的 LICENSE 文件与声明一致。
"""
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills-v2"

# 新版本号：expense 平台已是 0.2.47 → 必须 > 它，故跳到 0.2.48
NEW_VERSIONS = {
    "expense-audit-v2": "0.2.48",
    "procurement-fraud-v2": "0.2.9",
    "investigation-assistant-v2": "0.2.8",
    "cn-entity-relation-check": "0.1.10",
    "audit-sql-builder": "0.1.1",
}

AUTHOR = "Andrew Tao Li (andrew-tao-li)"
REPO_URL = "https://github.com/andrew-tao-li/ai-audit-skills"
CONTACT = "微信公众号「美会侠」（回复「费用审计」）· 邮箱 andrew.tao.li@foxmail.com"

MIT0_TEXT = """MIT No Attribution (MIT-0)

Copyright (c) 2026 {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

NOTICE_TEMPLATE = """Copyright (c) 2026 {author}

本 skill（{name}）由 {author} 开发，全部源码、版本与发布记录位于：
  {repo}

许可证
  本 skill 采用 MIT-0（MIT No Attribution）授权 —— 使用、修改、再分发均**无需署名**，
  也无需附带本文件。完整条款见同目录的 `LICENSE`。
  （仓库内其余部分——README / evals / evolution / scripts / docs——为 Apache-2.0。）

非约束性的出处声明（非许可条件）
  以上条款不要求你署名。若你把本 skill 或其衍生作品用于商业产品、
  对外服务、或再分发到第三方平台，**欢迎注明出处**（如「基于 andrew-tao-li 的
  {repo} 」），这对作者是实际的支持。

问题 / 建议
  {contact}
"""

README_SIGN = """
---

## 版权与署名

本 skill 由 **{author}** 开发（源码与全部版本：{repo}）。

许可证为 **MIT-0**（MIT No Attribution）：使用、修改、再分发**均无需署名**，条款见
同目录 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。

若用于商业产品、对外服务或再分发到第三方平台，欢迎注明出处 —— 这不是许可条件，
只是对作者的实际支持。

问题 / 建议：{contact}
"""


def bump_frontmatter_version(text: str, new_v: str) -> str:
    """只改顶层 version: 那一行（frontmatter 第一个 --- 块内）。

    ⚠️ 末尾必须用 [ \\t]* 而不是 \\s* —— \\s 会连行尾换行一起吃掉，
       换行丢了 frontmatter 结束处就没有「\\n---\\n」，build-skillhub.py 会直接报错。
    """
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise RuntimeError("SKILL.md frontmatter 结构异常")
    fm, body = parts[1], parts[2]
    fm2, n = re.subn(r"(?m)^version:[ \t]*\S+[ \t]*$", f"version: {new_v}", fm, count=1)
    if n != 1:
        raise RuntimeError("frontmatter 里找不到 version 行")
    return "---" + fm2 + "---" + body


def prepend_changelog(fm: str, new_v: str, entry: str) -> str:
    """把新版本条目插到 metadata.changelog 开头（保持既有单行长字符串格式）。

    ⚠️ 同上：缩进用 [ \\t]*、行尾用 [ \\t]*，避免吃掉换行。
    """
    m = re.search(r'(?m)^([ \t]*)changelog:[ \t]*"(.*)"[ \t]*$', fm)
    if not m:
        return fm
    indent, old = m.group(1), m.group(2)
    new = f'v{new_v}: {entry} | ' + old
    return fm[:m.start()] + f'{indent}changelog: "{new}"' + fm[m.end():]


def add_metadata_fields(fm: str, homepage: str) -> str:
    """在 metadata: 块里补 homepage / copyright（author 已有）。

    按行处理：找到内容恰为 `metadata:` 的那一行，在 metadata 块内插入。
    （不能用 `^metadata:\\s*$` —— \\s 会吃掉换行，导致插入错位。）
    """
    lines = fm.split("\n")
    try:
        mi = next(i for i, ln in enumerate(lines) if ln.strip() == "metadata:")
    except StopIteration:
        return fm
    # metadata 块的结束 = 下一个顶层键（缩进为 0）或空行（frontmatter 末尾那行）
    # ⚠️ 末尾那个空行必须保留 —— 它就是 frontmatter 结束前的换行，丢了会导致
    #    build-skillhub.py 的 `^---\n(.*?)\n---\n` 匹配失败。
    end = len(lines)
    for j in range(mi + 1, len(lines)):
        if not lines[j].startswith((" ", "\t", "-")):
            end = j
            break
    block = lines[mi + 1:end]
    extra = [
        f'  homepage: "{homepage}"',
        f'  copyright: "Copyright (c) 2026 {AUTHOR}"',
    ]
    # 插在 author 之后（若没有 author，则插在块首）
    ai = next((i for i, ln in enumerate(block) if ln.strip().startswith("author:")), None)
    if ai is None:
        block = extra + block
    else:
        block = block[:ai + 1] + extra + block[ai + 1:]
    return "\n".join(lines[:mi + 1] + block + lines[end:])


def main() -> int:
    changed = []
    for skill, new_v in NEW_VERSIONS.items():
        d = SKILLS_DIR / skill
        if not d.is_dir():
            print(f"✗ 缺目录 {d}", file=sys.stderr)
            return 1

        # --- 1) SKILL.md：版本 + changelog + metadata ---
        sk = d / "SKILL.md"
        text = sk.read_text(encoding="utf-8")
        old_v = re.search(r"(?m)^version:\s*(\S+)", text).group(1)
        entry = ("包内补 LICENSE(MIT-0 全文) 与 NOTICE；manifest 补 copyright/notice；"
                 "README 加版权与出处说明。"
                 "**许可证条款不变（MIT-0，无需署名），审计规则与输出无任何变化。**")
        text = bump_frontmatter_version(text, new_v)
        parts = text.split("---", 2)
        fm = prepend_changelog(parts[1], new_v, entry)
        # ⚠️ 刻意**不**给 SKILL.md 加 metadata 行：
        #   · validate_pack 对 SKILL.md 有「少于 500 行」硬上限（expense-audit-v2 本就 499 行，零余量）
        #   · 署名的权威载体是 NOTICE / LICENSE / manifest.json（均在 SKILL.md 之外）
        #   · 净化版 frontmatter 的顶层 homepage 来自 skillhub_config.HOMEPAGE → 安装者照样看得到主页
        sk.write_text("---" + fm + "---" + parts[2], encoding="utf-8")

        # 自检：改完必须仍能被 build-skillhub.py 的 frontmatter 正则解析
        #（否则净化版构建会直接抛 "SKILL.md 缺少 frontmatter"）
        if not re.match(r"^---\n(.*?)\n---\n", sk.read_text(encoding="utf-8"), re.S):
            raise RuntimeError(f"{skill}/SKILL.md 的 frontmatter 结构被改坏")

        # --- 2) manifest.json：版本 + notice/copyright ---
        mf = d / "manifest.json"
        m = json.loads(mf.read_text(encoding="utf-8"))
        m["version"] = new_v
        m["copyright"] = f"Copyright (c) 2026 {AUTHOR}"
        m["notice"] = f"See NOTICE in this skill directory. Author: {AUTHOR} — {REPO_URL}"
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # --- 3) 脚本里的 VERSION 常量 ---
        for py in sorted((d / "scripts").glob("*.py")):
            t = py.read_text(encoding="utf-8")
            t2, n = re.subn(r'(?m)^(VERSION\s*=\s*")[^"]+(")', rf'\g<1>{new_v}\g<2>', t, count=1)
            if n:
                py.write_text(t2, encoding="utf-8")

        # --- 4) LICENSE + NOTICE ---
        (d / "LICENSE").write_text(MIT0_TEXT.format(author=AUTHOR), encoding="utf-8")
        name = m.get("name") or skill
        (d / "NOTICE").write_text(
            NOTICE_TEMPLATE.format(author=AUTHOR, name=name, repo=REPO_URL, contact=CONTACT),
            encoding="utf-8")

        # --- 5) README 署名块（幂等：已有就不重复加） ---
        rm = d / "README.md"
        rtxt = rm.read_text(encoding="utf-8")
        if "## 版权与署名" not in rtxt:
            rm.write_text(rtxt.rstrip("\n") + "\n" + README_SIGN.format(
                author=AUTHOR, repo=REPO_URL, contact=CONTACT), encoding="utf-8")

        changed.append((skill, old_v, new_v))
        print(f"  ✓ {skill:<28} {old_v} → {new_v}")

    # --- 6) VERSIONS.json ---
    vf = ROOT / "VERSIONS.json"
    v = json.loads(vf.read_text(encoding="utf-8"))
    for skill, new_v in NEW_VERSIONS.items():
        v["skills"][skill] = new_v
    vf.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  ✓ VERSIONS.json 已更新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
