#!/usr/bin/env python3
"""
调 LLM API 做推理，支持多供应商 + 自动回退：
- MiniMax（Anthropic 兼容协议）：环境变量 MINIMAX_API_KEY，模型 MiniMax-M3
- DeepSeek（OpenAI 兼容协议）：环境变量 DEEPSEEK_API_KEY，模型 deepseek-chat
- 默认 --provider auto：先 MiniMax，失败自动回退 DeepSeek

完全独立于 OpenCode GUI，不持久化任何 key。

用法：
    python3 evals/blackbox/call_llm.py --prompt "..." --out output.md
    python3 evals/blackbox/call_llm.py --prompt-file prompt.txt --out output.md
    python3 evals/blackbox/call_llm.py --prompt "..." --provider deepseek
"""
import argparse
import json
import os
import sys
from pathlib import Path

PROVIDERS = {
    "minimax": {
        "endpoint": "https://api.minimax.io/anthropic/v1/messages",
        "model": "MiniMax-M3",
        "key_env": "MINIMAX_API_KEY",
        "protocol": "anthropic",
    },
    "deepseek": {
        "endpoint": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
        "protocol": "openai",
    },
}


def get_api_key(provider: str) -> str:
    """从环境变量读 API key，不在文件中存储"""
    cfg = PROVIDERS[provider]
    key = os.environ.get(cfg["key_env"], "").strip()
    if not key:
        raise RuntimeError(f"{cfg['key_env']} 环境变量未设置")
    return key


def build_request(provider, prompt, model, max_tokens, temperature):
    """按协议构造 (endpoint, headers, body)"""
    cfg = PROVIDERS[provider]
    if cfg["protocol"] == "anthropic":
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": get_api_key(provider),
            "anthropic-version": "2023-06-01",
        }
    else:  # openai 兼容
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_api_key(provider)}",
        }
    return cfg["endpoint"], headers, body


def parse_response(provider, data):
    """按协议解析回复文本"""
    cfg = PROVIDERS[provider]
    if cfg["protocol"] == "anthropic":
        if data.get("type") == "error":
            raise RuntimeError(f"API error: {data}")
        contents = data.get("content", [])
        return "\n".join(c["text"] for c in contents if c.get("type") == "text")
    # openai 兼容
    if data.get("error"):
        raise RuntimeError(f"API error: {data['error']}")
    choices = data.get("choices", [])
    if not choices:
        return ""
    return choices[0].get("message", {}).get("content", "")


def call_provider(provider, prompt, model, max_tokens, temperature):
    """对单个供应商发起请求，返回回复文本；失败抛 RuntimeError"""
    import urllib.request
    import urllib.error

    endpoint, headers, body = build_request(provider, prompt, model, max_tokens, temperature)
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"network error: {e.reason}")
    return parse_response(provider, data)


def call_llm(prompt, provider="auto", model=None, max_tokens=4000, temperature=0.3):
    """调 LLM，返回 (回复文本, 实际使用的 provider)。
    provider=auto 时按 MiniMax → DeepSeek 顺序回退。"""
    order = [provider] if provider in PROVIDERS else ["minimax", "deepseek"]
    errors = []
    for p in order:
        m = model or PROVIDERS[p]["model"]
        try:
            text = call_provider(p, prompt, m, max_tokens, temperature)
            return text, p
        except Exception as e:
            errors.append(f"{p}: {e}")
            print(f"[call_llm] {p} failed → {e}", file=sys.stderr)
    raise RuntimeError("所有供应商均失败: " + " | ".join(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", help="Prompt 文本（与 --prompt-file 二选一）")
    parser.add_argument("--prompt-file", help="Prompt 文件路径")
    parser.add_argument("--out", help="输出文件路径（默认 stdout）")
    parser.add_argument("--provider", choices=["auto", "minimax", "deepseek"], default="auto",
                        help="LLM 供应商（auto=先 MiniMax 后 DeepSeek）")
    parser.add_argument("--model", default=None, help="覆盖默认模型（不传则用各供应商默认）")
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        sys.exit("ERROR: 必须提供 --prompt 或 --prompt-file")

    response, provider_used = call_llm(
        prompt,
        provider=args.provider,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    print(f"[call_llm] provider={provider_used}, model={args.model or PROVIDERS[provider_used]['model']}, "
          f"chars={len(response)}", file=sys.stderr)

    if args.out:
        Path(args.out).write_text(response, encoding="utf-8")
        print(f"[call_llm] Saved: {args.out} ({len(response)} chars)", file=sys.stderr)
    else:
        print(response)


if __name__ == "__main__":
    main()
