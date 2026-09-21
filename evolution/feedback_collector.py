#!/usr/bin/env python3
"""
Feedback Collector — 接收任何形式的审计师反馈

支持的输入形式：
  1. 文字描述（直接说"我觉得 expense-audit 应该能识别某类场景"）
  2. 真实案例（CSV / JSON 文件）
  3. 截图（OCR 提取文字后处理）
  4. finding 评估（"这个 finding 是假阳性"）

工作流：
  用户提供反馈 → 落盘到 feedback/inbox/ → AI/LLM 后续处理

设计原则：
  - 绝不自动 apply（审计工具的特殊性）
  - 接收一切，分类延迟做
  - 元数据完整（时间、来源、状态）
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = ROOT / "feedback" / "inbox"
PROCESSED_DIR = ROOT / "feedback" / "processed"

INBOX_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def collect_text_feedback(text: str, source: str = "manual") -> Path:
    """接收纯文字反馈"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feedback_id = f"fb-{timestamp}"
    feedback_dir = INBOX_DIR / feedback_id
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # 写 feedback.md
    md_path = feedback_dir / "feedback.md"
    md_path.write_text(
        f"# Feedback {feedback_id}\n\n"
        f"**Source**: {source}\n"
        f"**Type**: text\n"
        f"**Created**: {timestamp}\n\n"
        f"## 内容\n\n{text}\n",
        encoding="utf-8"
    )

    # 写 metadata.json
    meta_path = feedback_dir / "metadata.json"
    meta_path.write_text(json.dumps({
        "id": feedback_id,
        "type": "text",
        "source": source,
        "created_at": timestamp,
        "status": "new",  # new / reviewed / applied / rejected
        "tags": [],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return feedback_dir


def collect_file_feedback(file_path: Path, source: str = "manual",
                          description: str = "") -> Path:
    """接收文件反馈（CSV / JSON / 截图等）"""
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feedback_id = f"fb-{timestamp}"
    feedback_dir = INBOX_DIR / feedback_id
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # 复制原文件
    dest = feedback_dir / f"original-{file_path.name}"
    shutil.copy2(file_path, dest)

    # metadata
    meta_path = feedback_dir / "metadata.json"
    meta_path.write_text(json.dumps({
        "id": feedback_id,
        "type": "file",
        "source": source,
        "created_at": timestamp,
        "status": "new",
        "original_filename": file_path.name,
        "original_size": file_path.stat().st_size,
        "description": description,
        "tags": [],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return feedback_dir


def collect_screenshot_feedback(image_path: Path, source: str = "manual") -> Path:
    """接收截图反馈（需要后续 OCR 处理）"""
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    if not image_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp"}:
        raise ValueError(f"不支持的图片格式: {image_path.suffix}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feedback_id = f"fb-{timestamp}"
    feedback_dir = INBOX_DIR / feedback_id
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # 复制截图
    dest = feedback_dir / f"screenshot-{image_path.name}"
    shutil.copy2(image_path, dest)

    # metadata（标记需 OCR）
    meta_path = feedback_dir / "metadata.json"
    meta_path.write_text(json.dumps({
        "id": feedback_id,
        "type": "screenshot",
        "source": source,
        "created_at": timestamp,
        "status": "new",
        "needs_ocr": True,
        "original_filename": image_path.name,
        "tags": [],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 写 README 提示需要 OCR
    readme = feedback_dir / "README.md"
    readme.write_text(
        f"# Screenshot Feedback {feedback_id}\n\n"
        f"图片: {dest.name}\n"
        f"状态: 等待 OCR 处理\n\n"
        f"## 待办\n\n"
        f"- [ ] 跑 OCR 提取文字\n"
        f"- [ ] 人工 review 内容\n"
        f"- [ ] 决定是否转化为 fixture / proposal\n",
        encoding="utf-8"
    )

    return feedback_dir


def collect_finding_evaluation(fixture: str, finding_type: str,
                                verdict: str, notes: str = "") -> Path:
    """
    评估具体 finding（"这个 finding 是真的/是假的"）
    verdict: 'true_positive' | 'false_positive' | 'false_negative'
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feedback_id = f"fb-finding-{timestamp}"
    feedback_dir = INBOX_DIR / feedback_id
    feedback_dir.mkdir(parents=True, exist_ok=True)

    eval_path = feedback_dir / "evaluation.json"
    eval_path.write_text(json.dumps({
        "id": feedback_id,
        "type": "finding_evaluation",
        "created_at": timestamp,
        "fixture": fixture,
        "finding_type": finding_type,
        "verdict": verdict,
        "notes": notes,
        "status": "new",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return feedback_dir


def list_inbox():
    """列出所有未处理的反馈"""
    if not INBOX_DIR.exists():
        return []
    results = []
    for d in sorted(INBOX_DIR.iterdir(), reverse=True):
        if d.is_dir():
            meta_path = d / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                results.append({
                    "id": meta.get("id"),
                    "type": meta.get("type"),
                    "created_at": meta.get("created_at"),
                    "status": meta.get("status"),
                    "path": str(d),
                })
    return results


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    # text 子命令
    p_text = subparsers.add_parser("text", help="提交纯文字反馈")
    p_text.add_argument("content", help="反馈内容（直接写）")
    p_text.add_argument("--source", default="manual", help="来源标识")

    # file 子命令
    p_file = subparsers.add_parser("file", help="提交文件反馈（CSV/JSON）")
    p_file.add_argument("path", help="文件路径")
    p_file.add_argument("--source", default="manual")
    p_file.add_argument("--description", default="", help="文件描述")

    # screenshot 子命令
    p_screen = subparsers.add_parser("screenshot", help="提交截图反馈")
    p_screen.add_argument("path", help="图片路径")

    # finding 子命令
    p_find = subparsers.add_parser("finding", help="评估某个 finding")
    p_find.add_argument("--fixture", required=True)
    p_find.add_argument("--finding-type", required=True)
    p_find.add_argument("--verdict", required=True, choices=["true_positive", "false_positive", "false_negative"])
    p_find.add_argument("--notes", default="")

    # list 子命令
    subparsers.add_parser("list", help="列出 inbox")

    args = parser.parse_args()

    if args.cmd == "text":
        d = collect_text_feedback(args.content, args.source)
        print(f"✓ 文字反馈已存: {d}")

    elif args.cmd == "file":
        d = collect_file_feedback(Path(args.path), args.source, args.description)
        print(f"✓ 文件反馈已存: {d}")

    elif args.cmd == "screenshot":
        d = collect_screenshot_feedback(Path(args.path))
        print(f"✓ 截图反馈已存: {d}")
        print(f"  提示: 后续需要 OCR 处理")

    elif args.cmd == "finding":
        d = collect_finding_evaluation(args.fixture, args.finding_type, args.verdict, args.notes)
        print(f"✓ Finding 评估已存: {d}")

    elif args.cmd == "list":
        items = list_inbox()
        if not items:
            print("(空)")
        else:
            print(f"共 {len(items)} 条反馈:")
            for it in items:
                print(f"  [{it['status']:8s}] {it['id']}  {it['type']:10s}  {it.get('created_at', '')}")
                print(f"             {it['path']}")


if __name__ == "__main__":
    main()
