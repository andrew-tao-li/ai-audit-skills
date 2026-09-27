#!/usr/bin/env python3
"""
路径查找：在有向（实际按无向遍历强工商边）图上做 BFS，找两实体之间 ≤ max_depth 的强关系路径。
V0.1 用 BFS 足够，不引入图数据库。
"""
from typing import Dict, List, Optional

from evidence_normalizer import Edge, Node, STRONG_RELATION_TYPES


def build_adjacency(nodes: List[Node], edges: List[Edge], strong_only: bool = True) -> Dict[str, Dict[str, Edge]]:
    """建邻接表。strong_only=True 时只保留强工商边。"""
    adj: Dict[str, Dict[str, Edge]] = {}
    for n in nodes:
        adj.setdefault(n.node_id, {})
    for e in edges:
        if strong_only and e.relation_type not in STRONG_RELATION_TYPES:
            continue
        adj.setdefault(e.from_id, {})[e.to_id] = e
        adj.setdefault(e.to_id, {})[e.from_id] = e  # 无向遍历，便于双向发现
    return adj


def find_paths(
    nodes: List[Node],
    edges: List[Edge],
    source: str,
    target: str,
    max_depth: int = 3,
    strong_only: bool = True,
) -> List[Dict]:
    """
    BFS 找 source → target 的最短若干路径（按深度，≤ max_depth）。
    返回按 (深度, 权重) 排序的路径列表，每条含 nodes 与 edges 名称。
    """
    node_map = {n.node_id: n for n in nodes}
    adj = build_adjacency(nodes, edges, strong_only=strong_only)
    if source not in node_map or target not in node_map:
        return []

    results: List[Dict] = []
    # BFS，记录路径
    from collections import deque
    q = deque([(source, [source], [])])  # (cur, node_path, edge_path)
    visited_depth = {source: 0}
    while q:
        cur, node_path, edge_path = q.popleft()
        depth = len(node_path) - 1
        if depth >= max_depth:
            continue
        for nxt, edge in adj.get(cur, {}).items():
            if nxt in node_path:
                continue
            new_nodes = node_path + [nxt]
            new_edges = edge_path + [edge]
            new_depth = depth + 1
            if nxt == target:
                results.append({"nodes": new_nodes, "edges": new_edges})
                # 找到一条后仍继续，但限制同深度的结果数量
                continue
            if new_depth < max_depth and new_depth < visited_depth.get(nxt, max_depth + 1):
                visited_depth[nxt] = new_depth
                q.append((nxt, new_nodes, new_edges))

    # 排序：路径更短优先，其次按边权重和（越大越优先），再次按历史关系靠后
    def sort_key(p):
        total_weight = sum(e.weight for e in p["edges"])
        has_historical = any(e.is_historical for e in p["edges"])
        return (len(p["edges"]), -total_weight, 1 if has_historical else 0)

    results.sort(key=sort_key)

    # 转成可读形式
    out = []
    for p in results[:3]:  # 最多返回 3 条最有解释力的路径
        node_names = [node_map.get(nid, Node(nid, "unknown", nid)).name for nid in p["nodes"]]
        edge_labels = []
        for e in p["edges"]:
            lbl = e.relation_type
            if e.holding_percent is not None:
                lbl += f"{e.holding_percent:g}%"
            edge_labels.append(lbl)
        out.append({
            "length": len(p["edges"]),
            "node_ids": p["nodes"],
            "nodes": node_names,
            "edge_types": [e.relation_type for e in p["edges"]],
            "edges": edge_labels,
            "historical": any(e.is_historical for e in p["edges"]),
        })
    return out
