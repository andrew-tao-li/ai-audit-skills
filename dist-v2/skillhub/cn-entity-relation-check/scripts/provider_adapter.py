#!/usr/bin/env python3
"""
Provider Adapter：抽象不同数据商的接口。业务判定层不得直接依赖某一家数据商的原始 JSON。

V0.1 提供一个 MockProvider（从本地 JSON fixture 读数据），用于测试和离线演示；
真实 Provider（企查查/天眼查/启信宝）由宿主 Agent 的 MCP/Connector 承担，或未来在此实现。
本模块不内置任何 Key。
"""
import json
from typing import Any, Dict, List, Optional
from pathlib import Path


class RelationProvider:
    """统一接口。真实实现应覆盖这些方法。"""

    def capabilities(self) -> Dict[str, bool]:
        raise NotImplementedError

    def resolve_company(self, query: str) -> List[Dict]:
        raise NotImplementedError

    def resolve_person(self, name: str, anchor_company: Optional[str] = None) -> List[Dict]:
        raise NotImplementedError

    def shortest_path(self, entity_a: Dict, entity_b: Dict, max_depth: int = 3) -> Dict:
        raise NotImplementedError

    def supports_negative_semantics(self) -> bool:
        return False


class MockProvider(RelationProvider):
    """从本地 JSON 读预置证据，用于离线演示与单元测试。"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @classmethod
    def from_file(cls, path: str) -> "MockProvider":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def capabilities(self) -> Dict[str, bool]:
        return self._data.get("capabilities", {})

    def nodes(self) -> List[Dict]:
        return self._data.get("nodes", [])

    def edges(self) -> List[Dict]:
        return self._data.get("edges", [])

    def supports_negative_semantics(self) -> bool:
        return bool(self._data.get("negative_semantics_supported", False))


# 标准能力字段（对应规范第 10 节）
CAPABILITY_FIELDS = {
    "structured_company_data": False,
    "company_entity_resolution": False,
    "company_shareholders": False,
    "company_key_people": False,
    "company_investments": False,
    "company_controller": False,
    "company_history": False,
    "person_resolution": False,
    "person_related_companies": False,
    "shortest_path": False,
    "web_search": False,
}
