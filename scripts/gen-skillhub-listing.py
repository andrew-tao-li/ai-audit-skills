#!/usr/bin/env python3
"""从 scripts/skillhub_config.py 生成 docs/skillhub-listing.md。

**不要手改 docs/skillhub-listing.md**——它是生成物，手改会在下次生成时被覆盖。
要改文案/分类，改 scripts/skillhub_config.py，然后跑：
    python3 scripts/gen-skillhub-listing.py
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "skillhub-listing.md"

# 平台分类的中英对照（从平台现网数据读出的 key）
CATEGORY_ZH = {
    "professional": "行业专业",
    "office-efficiency": "办公效率",
    "data-analysis": "数据分析",
    "business-ops": "商业运营",
    "content-creation": "内容创作",
    "knowledge-management": "知识管理",
    "design-media": "设计媒体",
    "dev-programming": "开发编程",
    "ai-agent": "AI Agent",
    "life-service": "生活服务",
    "it-ops-security": "IT运维安全",
}
SUB_ZH = {
    "pro-tax-accounting": "财税处理",
    "pro-legal": "法律合规",
    "pro-risk-control": "风险风控",
}


def load_config():
    spec = importlib.util.spec_from_file_location("skillhub_config", ROOT / "scripts" / "skillhub_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def indent_quote(text: str) -> str:
    return "\n".join(("> " + line) if line.strip() else ">" for line in text.splitlines())


def main() -> int:
    cfg = load_config()
    lines = [
        "# SkillHub 上架文案",
        "",
        "> ⚠️ **本文件是自动生成的**——由 `scripts/skillhub_config.py` + `python3 scripts/gen-skillhub-listing.py` 产出。",
        "> **不要手改这里**；要改文案或分类，改 `scripts/skillhub_config.py` 再重新生成。",
        "",
        "---",
        "",
        "## 通用信息",
        "",
        f"- **homepage**：`{cfg.HOMEPAGE}`",
        f"- **license**：`{cfg.LICENSE}`（使用不需署名）",
        "- **运行环境**：纯本地离线；Python 3.10+；XLSX 需 `openpyxl`（可选）；**不联网、不上传数据、无需任何 API Key**",
        "- **分类**：全部归入 **行业专业（`professional`）** + 对应子类",
        "",
        "**平台分类 key 对照**（从平台现网数据读取，非猜测）：",
        "",
        "| 一级 key | 中文 | 子类 key | 中文 |",
        "|---|---|---|---|",
        "| `professional` | 行业专业 | `pro-tax-accounting` | 财税处理 |",
        "| `office-efficiency` | 办公效率 | `pro-legal` | 法律合规 |",
        "| `data-analysis` | 数据分析 | `pro-risk-control` | 风险风控 |",
        "",
        "> **分类只能在发布时带**：官方 CLI 的 payload 没有 `category` 字段（发出来永远「未分类」），",
        "> 所以用本仓库的 `scripts/publish-skillhub.py` 发布——它照官方契约自己发并带上分类。",
        "> （网页端也能改：个人中心 → 我的 Skill → 编辑；但那会触发内容重审。）",
        "",
        "---",
        "",
        "## 发布",
        "",
        "```bash",
        "python3 scripts/build-skillhub.py         # 生成净化版 + 自检",
        "python3 scripts/publish-skillhub.py --dry-run   # 看 payload（含分类）",
        "python3 scripts/publish-skillhub.py             # 发布全部（自动限频 70s）",
        "```",
        "",
        "---",
        "",
    ]

    for i, (name, s) in enumerate(cfg.SKILLS.items(), 1):
        cat = s.get("category", "professional")
        subs = s.get("sub_categories", [])
        subs_zh = "、".join(SUB_ZH.get(x, x) for x in subs)
        lines += [
            f"## {i}. {s['display_name']}",
            "",
            f"- **slug**：`{s['slug']}`",
            f"- **一级分类**：{CATEGORY_ZH.get(cat, cat)}（`{cat}`）",
            f"- **子类**：{subs_zh}（{'、'.join('`%s`' % x for x in subs)}）",
            f"- **tags**：{'、'.join(s.get('tags', []))}",
            f"- **本地目录**：`skills-v2/{name}/`",
            "",
            "**summary（一句话）**",
            "",
            indent_quote(s["summary"]),
            "",
            "**详细介绍**",
            "",
            indent_quote(s["intro"]),
            "",
            "---",
            "",
        ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("✓ 已生成 %s（%d 个 skill）" % (OUT.relative_to(ROOT), len(cfg.SKILLS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
