#!/usr/bin/env python3
"""
结果校验器：这是整个 skill 最值得代码固化的部分。
它防止 LLM 或流程把「待核查」误说成「不关联」、把无证据说成「关联」。

规则：
- status == RELATED：必须 ≥1 条路径，且关键自然人已消歧、实体已锚定。
- status == NOT_RELATED_IN_SCOPE：必须同时满足 7 个前提，否则降级 NEEDS_VERIFICATION。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueryContext:
    """一次关联排查的上下文（决定能否输出「不关联」）。"""
    entities_resolved: bool = False
    person_ambiguity: bool = False
    structured_provider_used: bool = False
    scope_complete: bool = False
    provider_error: bool = False
    only_web_search: bool = False
    provider_supports_negative_semantics: bool = False
    max_depth: int = 3
    warnings: List[str] = field(default_factory=list)


def validate_result(status: str, paths: List[Dict], context: QueryContext) -> str:
    """校验并返回最终状态。任何不合规都降级为 NEEDS_VERIFICATION。"""
    # 1. 若存在有效强路径且主体已锚定、自然人已消歧 → 关联
    if paths:
        if not context.entities_resolved:
            return "NEEDS_VERIFICATION"
        if context.person_ambiguity:
            return "NEEDS_VERIFICATION"
        return "RELATED"

    # 2. 无路径时：只有全部前提满足才允许「不关联」
    if status == "NOT_RELATED_IN_SCOPE":
        required = (
            context.entities_resolved
            and context.structured_provider_used
            and context.scope_complete
            and not context.provider_error
            and not context.person_ambiguity
            and context.provider_supports_negative_semantics
        )
        if required:
            return "NOT_RELATED_IN_SCOPE"
        return "NEEDS_VERIFICATION"

    # 3. 其余都是待核查
    return "NEEDS_VERIFICATION"


def deterministic_decision(paths: List[Dict], context: QueryContext) -> str:
    """
    确定性决策（对应规范第 26 节伪代码）：
    只由结构化证据 + 上下文决定状态，LLM 只能读取、不得修改。
    """
    if not context.entities_resolved:
        return "NEEDS_VERIFICATION"
    if context.person_ambiguity:
        return "NEEDS_VERIFICATION"
    if paths:
        return "RELATED"
    if context.provider_error:
        return "NEEDS_VERIFICATION"
    if context.only_web_search:
        return "NEEDS_VERIFICATION"
    if not context.scope_complete:
        return "NEEDS_VERIFICATION"
    if not context.provider_supports_negative_semantics:
        return "NEEDS_VERIFICATION"
    return "NOT_RELATED_IN_SCOPE"
