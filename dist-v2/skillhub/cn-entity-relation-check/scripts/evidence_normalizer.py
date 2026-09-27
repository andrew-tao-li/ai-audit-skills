#!/usr/bin/env python3
"""
证据标准化：把不同数据源的输出统一成内部 Node / Edge 模型，并定义 V0.1 的强关系集合。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# V0.1 允许独立产生「关联」的强工商关系
STRONG_RELATION_TYPES = frozenset({
    "LEGAL_REP",
    "SHAREHOLDER",
    "INVESTMENT",
    "DIRECTOR",
    "SUPERVISOR",
    "EXECUTIVE",
    "PARTNER",
    "BRANCH",
    "ACTUAL_CONTROLLER",
    "UBO",
    # 历史强关系
    "HISTORICAL_LEGAL_REP",
    "HISTORICAL_SHAREHOLDER",
    "HISTORICAL_DIRECTOR",
    "HISTORICAL_SUPERVISOR",
    "HISTORICAL_EXECUTIVE",
    "HISTORICAL_INVESTMENT",
})

# 弱线索：只能触发「待核查」，不能独立「关联」
WEAK_RELATION_TYPES = frozenset({
    "SAME_PHONE", "SAME_EMAIL", "SAME_ADDRESS", "SAME_BANK",
    "SAME_DEVICE", "COMMON_LAWSUIT", "COMMON_BID",
    "SUPPLIER", "CUSTOMER", "NEWS_CO_OCCURRENCE",
})

# 关系权重（仅用于路径排序，不用于是否关联的判定）
RELATION_WEIGHT = {
    "ACTUAL_CONTROLLER": 100, "UBO": 95,
    "SHAREHOLDER": 90, "INVESTMENT": 90,
    "LEGAL_REP": 85, "PARTNER": 85, "BRANCH": 80,
    "DIRECTOR": 70, "EXECUTIVE": 70, "SUPERVISOR": 65,
}
HISTORICAL_WEIGHT_FACTOR = 0.7

# 中文关系标签
RELATION_LABEL = {
    "LEGAL_REP": "法定代表人", "SHAREHOLDER": "股东", "INVESTMENT": "对外投资",
    "DIRECTOR": "董事", "SUPERVISOR": "监事", "EXECUTIVE": "高管",
    "PARTNER": "合伙人", "BRANCH": "分支机构", "ACTUAL_CONTROLLER": "实际控制人", "UBO": "最终受益人",
    "HISTORICAL_LEGAL_REP": "历史法定代表人", "HISTORICAL_SHAREHOLDER": "历史股东",
    "HISTORICAL_DIRECTOR": "历史董事", "HISTORICAL_SUPERVISOR": "历史监事",
    "HISTORICAL_EXECUTIVE": "历史高管", "HISTORICAL_INVESTMENT": "历史投资",
}


@dataclass
class Node:
    node_id: str
    type: str                    # company | person
    name: str
    canonical_id: Optional[str] = None
    source: Optional[str] = None


@dataclass
class Edge:
    from_id: str
    to_id: str
    relation_type: str
    current: bool = True
    holding_percent: Optional[float] = None
    source: Optional[str] = None
    source_record_id: Optional[str] = None

    @property
    def is_strong(self) -> bool:
        return self.relation_type in STRONG_RELATION_TYPES

    @property
    def is_historical(self) -> bool:
        return self.relation_type.startswith("HISTORICAL_")

    @property
    def weight(self) -> float:
        base = RELATION_WEIGHT.get(self.relation_type, 50)
        if self.is_historical:
            base *= HISTORICAL_WEIGHT_FACTOR
        return base


def normalize_relation_type(provider_term: str) -> Optional[str]:
    """把数据商自己的术语映射到内部统一关系类型。"""
    term = (provider_term or "").strip().upper()
    mapping = {
        "LEGAL_REP": "LEGAL_REP", "LEGAL_REPRESENTATIVE": "LEGAL_REP", "法人": "LEGAL_REP", "法定代表人": "LEGAL_REP",
        "SHAREHOLDER": "SHAREHOLDER", "股东": "SHAREHOLDER",
        "INVESTMENT": "INVESTMENT", "投资": "INVESTMENT", "对外投资": "INVESTMENT",
        "DIRECTOR": "DIRECTOR", "董事": "DIRECTOR",
        "SUPERVISOR": "SUPERVISOR", "监事": "SUPERVISOR",
        "EXECUTIVE": "EXECUTIVE", "高管": "EXECUTIVE", "高级管理人员": "EXECUTIVE",
        "PARTNER": "PARTNER", "合伙人": "PARTNER",
        "BRANCH": "BRANCH", "分支机构": "BRANCH",
        "ACTUAL_CONTROLLER": "ACTUAL_CONTROLLER", "实控": "ACTUAL_CONTROLLER", "实际控制人": "ACTUAL_CONTROLLER",
        "UBO": "UBO", "最终受益人": "UBO", "最终受益所有人": "UBO",
        "HISTORICAL_LEGAL_REP": "HISTORICAL_LEGAL_REP", "历史法定代表人": "HISTORICAL_LEGAL_REP",
        "HISTORICAL_SHAREHOLDER": "HISTORICAL_SHAREHOLDER", "历史股东": "HISTORICAL_SHAREHOLDER",
        "HISTORICAL_DIRECTOR": "HISTORICAL_DIRECTOR", "历史董事": "HISTORICAL_DIRECTOR",
        "HISTORICAL_SUPERVISOR": "HISTORICAL_SUPERVISOR", "历史监事": "HISTORICAL_SUPERVISOR",
        "HISTORICAL_EXECUTIVE": "HISTORICAL_EXECUTIVE", "历史高管": "HISTORICAL_EXECUTIVE",
        "HISTORICAL_INVESTMENT": "HISTORICAL_INVESTMENT", "历史投资": "HISTORICAL_INVESTMENT",
    }
    return mapping.get(term)


def normalize_edge(raw: Dict[str, Any]) -> Optional[Edge]:
    """把一条数据源原始边转成内部 Edge。"""
    rel = normalize_relation_type(raw.get("relation_type", ""))
    if rel is None:
        return None
    return Edge(
        from_id=raw.get("from", raw.get("from_id", "")),
        to_id=raw.get("to", raw.get("to_id", "")),
        relation_type=rel,
        current=bool(raw.get("current", True)),
        holding_percent=raw.get("holding_percent"),
        source=raw.get("source"),
        source_record_id=raw.get("source_record_id"),
    )
