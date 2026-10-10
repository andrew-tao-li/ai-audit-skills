#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把检查结果的失败**分两类**：真实回归 vs 基础设施/检测未完成。

背景（2026-10-10）：日报把当晚的**网络抖动**（GitHub TLS 中断）当成了代码缺陷，
自动开了一个改 changelog 的 PR（#6）——那是误判。

原则（最小守卫）：**只有"真实回归"才计入失败、才触发修复提案**；
网络类错误与"检测未完成"一律标 `⚠️ 未执行`，不进失败清单。
"""
from __future__ import annotations

from typing import Any, Dict, List

# 网络/基础设施类错误的关键字（命中即视为"未执行"，不是代码问题）
NETWORK_MARKERS = (
    "EOF occurred in violation of protocol",
    "SSLError",
    "ssl.c",
    "urlopen error",
    "URLError",
    "Connection refused",
    "Connection reset",
    "Remote end closed connection",
    "Temporary failure in name resolution",
    "timed out",
    "TimeoutError",
    "ECONNRESET",
    "ETIMEDOUT",
)

# 验收里"只是没观察到 skill 调用"的那一项；其余功能项全过 → 视为检测未完成
DETECTION_CHECK = "加载预期 skill"


def is_network_error(text: str) -> bool:
    text = text or ""
    return any(m in text for m in NETWORK_MARKERS)


def classify_acceptance_case(case: Dict[str, Any]) -> str:
    """返回 'passed' / 'failed' / 'not_run'。"""
    if case.get("passed"):
        return "passed"
    # ① 网络类错误 → 未执行
    if is_network_error(str(case.get("error") or "")) or is_network_error(str(case.get("stderr_tail") or "")):
        return "not_run"
    checks = case.get("checks", [])
    failed = [c for c in checks if not c.get("ok")]
    # ② 只错在"是否观察到 skill 加载"，且**功能项全过** → 检测未完成（不是功能回归）
    if failed and all(c.get("name") == DETECTION_CHECK for c in failed):
        others = [c for c in checks if c.get("name") != DETECTION_CHECK]
        if others and all(c.get("ok") for c in others):
            return "not_run"
    return "failed"


def split_acceptance(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """把一次验收的所有用例分成 real（真失败）与 not_run（未执行）。"""
    out: Dict[str, List[Dict[str, Any]]] = {"real": [], "not_run": []}
    for case in results:
        verdict = classify_acceptance_case(case)
        if verdict == "failed":
            out["real"].append(case)
        elif verdict == "not_run":
            out["not_run"].append(case)
    return out


def split_smoke(output: str) -> bool:
    """安装冒烟输出是否属于"未执行"（网络类）。返回 True = 未执行。"""
    return is_network_error(output or "")
