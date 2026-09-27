#!/usr/bin/env python3
"""
关联排查核心的单元测试。

聚焦四个硬指标：
1. False Negative Safety：任何 Provider 失败/身份歧义/Web-only 都不能输出「不关联」。
2. Person Identity Safety：自然人必须有唯一锚点。
3. Evidence Traceability：每个「关联」有路径。
4. Negative Traceability：每个「不关联」有完整前提。

测试数据全部虚构。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from relation_core import run_relation_check  # noqa: E402
from result_validator import deterministic_decision, validate_result, QueryContext  # noqa: E402


def _related(a, b, nodes, edges, **kw):
    """构造一个「两主体已锚定、结构化、范围完整、支持 negative semantics」的上下文。"""
    flags = dict(
        entities_resolved=True,
        person_ambiguity=False,
        structured_provider_used=True,
        scope_complete=True,
        provider_error=False,
        only_web_search=False,
        provider_supports_negative_semantics=True,
    )
    flags.update(kw)
    return run_relation_check(a, b, nodes, edges, **flags)


def _graph_shared_person(a_name="上海甲科技有限公司", b_name="上海乙科技有限公司"):
    nodes = [
        {"node_id": "A", "type": "company", "name": a_name, "canonical_id": "91310000MA1K3A000X"},
        {"node_id": "B", "type": "company", "name": b_name, "canonical_id": "91310000MA1K3B000Y"},
        {"node_id": "P1", "type": "person", "name": "张三", "canonical_id": "person-zhangsan-001"},
    ]
    edges = [
        {"from": "P1", "to": "A", "relation_type": "LEGAL_REP", "current": True, "source": "mock"},
        {"from": "P1", "to": "B", "relation_type": "SHAREHOLDER", "holding_percent": 35.0, "current": True, "source": "mock"},
    ]
    return nodes, edges


class TestCompanyCompany(unittest.TestCase):
    def test_common_legal_rep_is_related(self):
        nodes, edges = _graph_shared_person()
        r = _related("上海甲科技有限公司", "上海乙科技有限公司", nodes, edges)
        self.assertEqual(r["status"], "RELATED")
        self.assertEqual(r["display_status"], "关联")
        self.assertGreaterEqual(len(r["paths"]), 1)

    def test_three_hop_path_is_related(self):
        nodes = [
            {"node_id": "A", "type": "company", "name": "甲公司", "canonical_id": "A"},
            {"node_id": "C", "type": "company", "name": "丙公司", "canonical_id": "C"},
            {"node_id": "B", "type": "company", "name": "乙公司", "canonical_id": "B"},
            {"node_id": "P1", "type": "person", "name": "张三", "canonical_id": "P1"},
        ]
        edges = [
            {"from": "A", "to": "C", "relation_type": "INVESTMENT", "current": True, "source": "mock"},
            {"from": "C", "to": "P1", "relation_type": "DIRECTOR", "current": True, "source": "mock"},
            {"from": "P1", "to": "B", "relation_type": "LEGAL_REP", "current": True, "source": "mock"},
        ]
        r = _related("甲公司", "乙公司", nodes, edges)
        self.assertEqual(r["status"], "RELATED")

    def test_no_path_with_full_scope_is_not_related(self):
        nodes = [
            {"node_id": "A", "type": "company", "name": "甲公司", "canonical_id": "A"},
            {"node_id": "B", "type": "company", "name": "乙公司", "canonical_id": "B"},
        ]
        edges = []
        r = _related("甲公司", "乙公司", nodes, edges)
        self.assertEqual(r["status"], "NOT_RELATED_IN_SCOPE")
        self.assertEqual(r["display_status"], "不关联")

    def test_weak_signal_never_related(self):
        # 只有同地址（弱线索），不能判「关联」
        nodes = [
            {"node_id": "A", "type": "company", "name": "甲公司", "canonical_id": "A"},
            {"node_id": "B", "type": "company", "name": "乙公司", "canonical_id": "B"},
        ]
        edges = [{"from": "A", "to": "B", "relation_type": "SAME_ADDRESS", "current": True, "source": "mock"}]
        r = _related("甲公司", "乙公司", nodes, edges)
        self.assertEqual(r["status"], "NOT_RELATED_IN_SCOPE")  # 弱边不进入强图，故无强路径


class TestCompanyPerson(unittest.TestCase):
    def test_direct_director_is_related(self):
        nodes = [
            {"node_id": "A", "type": "company", "name": "上海甲科技有限公司", "canonical_id": "A"},
            {"node_id": "P1", "type": "person", "name": "张三", "canonical_id": "P1"},
        ]
        edges = [{"from": "P1", "to": "A", "relation_type": "DIRECTOR", "current": True, "source": "mock"}]
        r = _related("上海甲科技有限公司", "张三", nodes, edges)
        self.assertEqual(r["status"], "RELATED")

    def test_bare_person_name_is_verification(self):
        # 人只是裸姓名、无锚点 → 待核查
        nodes = [{"node_id": "A", "type": "company", "name": "甲公司", "canonical_id": "A"}]
        edges = []
        r = _related("甲公司", "张三", nodes, edges, person_ambiguity=True)
        self.assertEqual(r["status"], "NEEDS_VERIFICATION")


class TestPersonPerson(unittest.TestCase):
    def test_shared_company_is_related(self):
        nodes = [
            {"node_id": "P1", "type": "person", "name": "张三", "canonical_id": "P1"},
            {"node_id": "P2", "type": "person", "name": "李四", "canonical_id": "P2"},
            {"node_id": "A", "type": "company", "name": "甲公司", "canonical_id": "A"},
        ]
        edges = [
            {"from": "P1", "to": "A", "relation_type": "DIRECTOR", "current": True, "source": "mock"},
            {"from": "P2", "to": "A", "relation_type": "SHAREHOLDER", "current": True, "source": "mock"},
        ]
        r = _related("张三", "李四", nodes, edges)
        self.assertEqual(r["status"], "RELATED")


class TestNegativeSemantics(unittest.TestCase):
    def test_web_only_never_not_related(self):
        r = run_relation_check("甲", "乙", [], [], entities_resolved=True, only_web_search=True)
        self.assertEqual(r["status"], "NEEDS_VERIFICATION")

    def test_provider_error_never_not_related(self):
        r = run_relation_check("甲", "乙", [], [], entities_resolved=True, provider_error=True)
        self.assertEqual(r["status"], "NEEDS_VERIFICATION")

    def test_not_related_requires_negative_semantics(self):
        r = run_relation_check("甲", "乙", [], [], entities_resolved=True, structured_provider_used=True,
                               scope_complete=True, provider_supports_negative_semantics=False)
        self.assertEqual(r["status"], "NEEDS_VERIFICATION")

    def test_not_related_requires_scope_complete(self):
        r = run_relation_check("甲", "乙", [], [], entities_resolved=True, structured_provider_used=True,
                               scope_complete=False, provider_supports_negative_semantics=True)
        self.assertEqual(r["status"], "NEEDS_VERIFICATION")

    def test_unresolved_entity_is_verification(self):
        r = run_relation_check("甲", "乙", [], [], entities_resolved=False)
        self.assertEqual(r["status"], "NEEDS_VERIFICATION")


class TestHistorical(unittest.TestCase):
    def test_historical_relation_is_related_historical(self):
        nodes = [
            {"node_id": "A", "type": "company", "name": "甲公司", "canonical_id": "A"},
            {"node_id": "B", "type": "company", "name": "乙公司", "canonical_id": "B"},
            {"node_id": "P1", "type": "person", "name": "张三", "canonical_id": "P1"},
        ]
        edges = [
            {"from": "P1", "to": "A", "relation_type": "HISTORICAL_DIRECTOR", "current": False, "source": "mock"},
            {"from": "P1", "to": "B", "relation_type": "LEGAL_REP", "current": True, "source": "mock"},
        ]
        r = _related("甲公司", "乙公司", nodes, edges)
        self.assertEqual(r["status"], "RELATED")
        self.assertEqual(r["relationship_temporality"], "historical")


class TestValidator(unittest.TestCase):
    def test_validator_downgrades_related_without_path(self):
        ctx = QueryContext(entities_resolved=True, structured_provider_used=True, scope_complete=True,
                           provider_supports_negative_semantics=True)
        self.assertEqual(validate_result("RELATED", [], ctx), "NEEDS_VERIFICATION")

    def test_validator_downgrades_not_related_without_negative_semantics(self):
        ctx = QueryContext(entities_resolved=True, structured_provider_used=True, scope_complete=True,
                           provider_supports_negative_semantics=False)
        self.assertEqual(validate_result("NOT_RELATED_IN_SCOPE", [], ctx), "NEEDS_VERIFICATION")

    def test_deterministic_decision_order(self):
        # 有路径但实体未锚定 → 待核查（不因路径而「关联」）
        ctx = QueryContext(entities_resolved=False)
        self.assertEqual(deterministic_decision([{"length": 1}], ctx), "NEEDS_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
