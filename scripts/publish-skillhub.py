#!/usr/bin/env python3
"""把 dist-v2/skillhub/<skill>/ 发布到 SkillHub.cn（**带分类**）。

为什么不用官方 CLI：
  官方 `skillhub publish` 的 payload 里**没有** category / subCategories 字段，
  所以 CLI 发出来的 skill 永远是「未分类」——而分类决定它能不能出现在**分类浏览**里。
  本脚本照 CLI 的 multipart 契约自己发，额外带上分类。

分类配置的**单一来源**是 `scripts/build-skillhub.py` 里的 SKILLS（slug / category / sub_categories）。

用法：
  python3 scripts/publish-skillhub.py                 # 发布全部 4 个
  python3 scripts/publish-skillhub.py expense-audit-v2  # 只发一个
  python3 scripts/publish-skillhub.py --dry-run       # 只看 payload，不发

需要 SKILLHUB_TOKEN（读仓库外 ~/.config/ai-audit-skills/env）。
注意：**平台有限频**，连发会 429；本脚本默认每次间隔 70 秒。
"""
import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "dist-v2" / "skillhub"
SKILLHUB_API = "https://api.skillhub.cn"
PUBLISH_URL = SKILLHUB_API + "/api/v1/community/skills/publish"
ENV_FILE = Path.home() / ".config" / "ai-audit-skills" / "env"
INTERVAL_S = 70  # 平台限频，实测连发 4 个会 429


def load_config() -> dict:
    """分类/文案的单一来源：scripts/skillhub_config.py。"""
    spec = importlib.util.spec_from_file_location("skillhub_config", ROOT / "scripts" / "skillhub_config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SKILLS


def load_token() -> str:
    token = os.environ.get("SKILLHUB_TOKEN", "")
    if not token and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip().removeprefix("export ")
            if line.startswith("SKILLHUB_TOKEN="):
                token = line.split("=", 1)[1].strip().strip("'\"")
    return token


def parse_frontmatter(skill_dir: Path) -> dict:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    fm = text.split("---", 2)[1]
    out = {}
    for line in fm.splitlines():
        if line.startswith("  ") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


def build_payload(skill_dir: Path, cfg: dict, changelog: str) -> dict:
    meta = parse_frontmatter(skill_dir)
    tags = []
    if meta.get("tags", "").startswith("["):
        tags = [t.strip() for t in meta["tags"].strip("[]").split(",") if t.strip()]
    return {
        "slug": meta.get("slug", cfg["slug"]),
        "version": meta.get("version", ""),
        "displayName": meta.get("displayName", cfg["display_name"]),
        "summary": meta.get("summary", cfg["summary"]),
        "description": meta.get("description", ""),
        "tags": tags,
        "license": meta.get("license", "MIT-0"),
        "homepage": meta.get("homepage", ""),
        "changelog": changelog,
        # ↓ 官方 CLI 不会传这两个字段——这正是本脚本存在的理由
        "category": cfg.get("category", ""),
        "subCategories": cfg.get("sub_categories", []),
    }


def publish(skill_dir: Path, payload: dict, token: str) -> tuple:
    skill_files = [(str(p.relative_to(skill_dir)), p.read_bytes())
                   for p in sorted(skill_dir.rglob("*")) if p.is_file()]
    boundary = "----aiAuditBoundary" + str(int(time.time() * 1000))
    body = bytearray()

    def add_part(name, data, filename=None, ctype="application/octet-stream"):
        body.extend(("--%s\r\n" % boundary).encode())
        if filename:
            body.extend(('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (name, filename)).encode())
        else:
            body.extend(('Content-Disposition: form-data; name="%s"\r\n' % name).encode())
        body.extend(("Content-Type: %s\r\n\r\n" % ctype).encode())
        body.extend(data)
        body.extend(b"\r\n")

    add_part("payload", json.dumps(payload, ensure_ascii=False).encode("utf-8"), ctype="application/json")
    for rel, data in skill_files:
        add_part("files", data, filename=rel,
                 ctype="text/markdown" if rel.lower().endswith(".md") else "application/octet-stream")
    body.extend(("--%s--\r\n" % boundary).encode())

    req = urllib.request.Request(PUBLISH_URL, data=bytes(body), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "ai-audit-publisher")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw[:300]}
    except urllib.error.URLError as e:
        return 0, {"error": "网络错误: %s" % e.reason}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("skill", nargs="?", help="只发布指定 skill（默认全部）")
    ap.add_argument("--changelog", default="SkillHub 上架元数据：补充分类（行业专业）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--interval", type=int, default=INTERVAL_S)
    args = ap.parse_args()

    config = load_config()
    names = [args.skill] if args.skill else list(config)
    token = load_token()
    if not token and not args.dry_run:
        print("✗ 未找到 SKILLHUB_TOKEN（~/.config/ai-audit-skills/env）", file=sys.stderr)
        return 1

    failed = 0
    for i, name in enumerate(names):
        if name not in config:
            print("✗ 未知 skill: %s" % name, file=sys.stderr)
            failed += 1
            continue
        skill_dir = OUT_ROOT / name
        if not (skill_dir / "SKILL.md").exists():
            print("✗ 未找到 SkillHub 适配版产物：%s（先跑 scripts/build-skillhub.py）" % skill_dir, file=sys.stderr)
            failed += 1
            continue

        payload = build_payload(skill_dir, config[name], args.changelog)
        print("▶ %s  →  v%s  分类=%s %s" % (name, payload["version"], payload["category"], payload["subCategories"]))
        if args.dry_run:
            continue

        if i > 0:
            print("   等 %ds（平台限频）…" % args.interval)
            time.sleep(args.interval)
        code, body = publish(skill_dir, payload, token)
        ok = code in (200, 201) and body.get("ok", True) is not False
        if ok:
            print("   ✓ 已发布（skillId=%s, reviewStatus=%s）" % (body.get("skillId"), body.get("reviewStatus")))
        else:
            failed += 1
            print("   ✗ HTTP %s %s" % (code, json.dumps(body, ensure_ascii=False)[:220]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
