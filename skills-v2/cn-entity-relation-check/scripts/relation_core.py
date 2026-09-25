#!/usr/bin/env python3
"""
关联排查核心编排：normalize → resolve → graph → paths → decision → result。
只做确定性判定，不联网、不内置 Key。宿主 Agent 负责采集证据后调用本模块。
"""
import json
from typing import Any, Dict, List, Optional

from entity_normalizer import Entity, normalize_entity
from evidence_normalizer import Edge, Node, normalize_edge, STRONG_RELATION_TYPES
from path_finder import find_paths
from result_validator import QueryContext, deterministic_decision, validate_result

VERSION = "0.1.3"
SKILL = "cn-entity-relation-check"

STATUS_DISPLAY = {
    "RELATED": "关联",
    "NOT_RELATED_IN_SCOPE": "不关联",
    "NEEDS_VERIFICATION": "待核查",
}


def build_context(
    entities_resolved: bool,
    person_ambiguity: bool = False,
    structured_provider_used: bool = False,
    scope_complete: bool = False,
    provider_error: bool = False,
    only_web_search: bool = False,
    provider_supports_negative_semantics: bool = False,
    max_depth: int = 3,
    warnings: Optional[List[str]] = None,
) -> QueryContext:
    return QueryContext(
        entities_resolved=entities_resolved,
        person_ambiguity=person_ambiguity,
        structured_provider_used=structured_provider_used,
        scope_complete=scope_complete,
        provider_error=provider_error,
        only_web_search=only_web_search,
        provider_supports_negative_semantics=provider_supports_negative_semantics,
        max_depth=max_depth,
        warnings=warnings or [],
    )


def run_relation_check(
    raw_a: str,
    raw_b: str,
    nodes: List[Dict],
    edges: List[Dict],
    entities_resolved: bool = False,
    person_ambiguity: bool = False,
    structured_provider_used: bool = False,
    scope_complete: bool = False,
    provider_error: bool = False,
    only_web_search: bool = False,
    provider_supports_negative_semantics: bool = False,
    max_depth: int = 3,
    sources: Optional[List[Dict]] = None,
    queried_at: Optional[str] = None,
) -> Dict[str, Any]:
    """完整执行一次关联排查，返回标准机器输出。"""
    a: Entity = normalize_entity(raw_a)
    b: Entity = normalize_entity(raw_b)

    # 实体是否已锚定：调用方通过 entities_resolved 显式告知（因为锚定依赖数据源）
    a.resolved = entities_resolved
    b.resolved = entities_resolved

    node_objs = [Node(n["node_id"], n.get("type", "unknown"), n.get("name", n["node_id"]),
                      n.get("canonical_id"), n.get("source")) for n in nodes]
    edge_objs: List[Edge] = []
    for e in edges:
        ne = normalize_edge(e)
        if ne is not None:
            edge_objs.append(ne)

    ctx = build_context(
        entities_resolved=entities_resolved,
        person_ambiguity=person_ambiguity,
        structured_provider_used=structured_provider_used,
        scope_complete=scope_complete,
        provider_error=provider_error,
        only_web_search=only_web_search,
        provider_supports_negative_semantics=provider_supports_negative_semantics,
        max_depth=max_depth,
    )

    # 确定 source/target node_id：优先用 canonical_id 匹配，否则用 normalized_name 匹配
    source_id = _match_node(a, b, node_objs, "a")
    target_id = _match_node(b, a, node_objs, "b")

    paths: List[Dict] = []
    if source_id and target_id and source_id != target_id:
        paths = find_paths(node_objs, edge_objs, source_id, target_id, max_depth=max_depth, strong_only=True)

    status = deterministic_decision(paths, ctx)
    # 结果硬校验（防止越权）
    status = validate_result(status, paths, ctx)

    # 关系时态：任一路径含历史边则为历史关联
    temporality = "historical" if any(p.get("historical") for p in paths) else "current"

    return {
        "skill": SKILL,
        "skill_version": VERSION,
        "status": status,
        "display_status": STATUS_DISPLAY.get(status, status),
        "relationship_temporality": temporality,
        "entity_a": {"type": a.type, "name": a.normalized_name or a.raw_input, "canonical_id": a.canonical_id},
        "entity_b": {"type": b.type, "name": b.normalized_name or b.raw_input, "canonical_id": b.canonical_id},
        "paths": paths,
        "scope": {
            "relation_types": sorted(STRONG_RELATION_TYPES),
            "max_depth": max_depth,
        },
        "sources": sources or [],
        "warnings": ctx.warnings,
        "queried_at": queried_at,
    }


def _match_node(a: Entity, other: Entity, nodes: List[Node], which: str) -> Optional[str]:
    """把 Entity 匹配到图里的 node_id。优先 canonical_id，其次 normalized_name。"""
    # 优先 canonical_id
    if a.canonical_id:
        for n in nodes:
            if n.canonical_id == a.canonical_id:
                return n.node_id
    # 其次名称
    name = a.normalized_name or a.raw_input
    for n in nodes:
        if n.name == name:
            return n.node_id
    # 名称包含匹配（宽松）
    for n in nodes:
        if name and (name in n.name or n.name in name):
            return n.node_id
    return None
