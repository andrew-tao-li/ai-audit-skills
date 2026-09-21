#!/usr/bin/env python3
"""
直接调 MiniMax API（Anthropic 兼容协议）做 LLM 推理
- 完全独立于 OpenCode GUI
- API key 通过环境变量 MINIMAX_API_KEY 传递
- 不持久化任何 key

用法：
    export MINIMAX_API_KEY="sk-..."
    python3 evals/blackbox/call_llm.py --prompt "..." --out output.md

或：
    python3 evals/blackbox/call_llm.py --prompt-file prompt.txt --out output.md
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ENDPOINT = "https://api.minimax.io/anthropic/v1/messages"
MODEL = "MiniMax-M3"
API_VERSION = "2023-06-01"


def get_api_key():
    """从环境变量读 API key，不在文件中存储"""
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        sys.exit("ERROR: MINIMAX_API_KEY 环境变量未设置")
    return key


def call_llm(prompt: str, model: str = MODEL, max_tokens: int = 4000, temperature: float = 0.3) -> str:
    """调 MiniMax API，返回 assistant 回复文本"""
    import urllib.request
    import urllib.error

    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": get_api_key(),
            "anthropic-version": API_VERSION,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body[:500]}")

    if data.get("type") == "error":
        raise RuntimeError(f"API error: {data}")

    # 提取 text content
    contents = data.get("content", [])
    texts = [c["text"] for c in contents if c.get("type") == "text"]
    return "\n".join(texts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", help="Prompt 文本（与 --prompt-file 二选一）")
    parser.add_argument("--prompt-file", help="Prompt 文件路径")
    parser.add_argument("--out", help="输出文件路径（默认 stdout）")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        sys.exit("ERROR: 必须提供 --prompt 或 --prompt-file")

    print(f"[call_llm] Calling {args.model}, max_tokens={args.max_tokens}", file=sys.stderr)
    response = call_llm(prompt, args.model, args.max_tokens, args.temperature)

    if args.out:
        Path(args.out).write_text(response, encoding="utf-8")
        print(f"[call_llm] Saved: {args.out} ({len(response)} chars)", file=sys.stderr)
    else:
        print(response)


if __name__ == "__main__":
    main()
