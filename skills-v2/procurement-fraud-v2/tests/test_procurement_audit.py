import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "run_procurement_audit.py"
INPUT = SKILL_ROOT / "examples" / "input"
CONFIG = INPUT / "config.json"
EXPECTED = SKILL_ROOT / "examples" / "expected" / "expectations.json"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ProcurementAuditEndToEndTest(unittest.TestCase):
    def run_example(self):
        temp = tempfile.TemporaryDirectory()
        output = Path(temp.name) / "out"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--input-dir", str(INPUT), "--config", str(CONFIG), "--output", str(output)],
            capture_output=True, text=True, encoding="utf-8"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return temp, output

    def test_fixture_detects_each_required_module(self):
        temp, output = self.run_example()
        try:
            findings = read_jsonl(output / "findings.jsonl")
            expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
            types = {finding["finding_type"] for finding in findings}
            self.assertTrue(set(expected["must_include_finding_types"]).issubset(types))
            self.assertTrue(all(finding["human_review_required"] for finding in findings))
            self.assertNotIn("judgment", findings[0])
        finally:
            temp.cleanup()

    def test_evidence_and_graph_references_are_complete(self):
        temp, output = self.run_example()
        try:
            findings = read_jsonl(output / "findings.jsonl")
            evidence = read_jsonl(output / "evidence.jsonl")
            evidence_ids = {item["evidence_id"] for item in evidence}
            for finding in findings:
                self.assertTrue(finding["evidence_refs"])
                self.assertTrue(set(finding["evidence_refs"]).issubset(evidence_ids))
            graph = json.loads((output / "relationship_graph.json").read_text(encoding="utf-8"))
            node_ids = {node["id"] for node in graph["nodes"]}
            for edge in graph["edges"]:
                self.assertIn(edge["source"], node_ids)
                self.assertIn(edge["target"], node_ids)
                self.assertTrue(set(edge["evidence_refs"]).issubset(evidence_ids))
        finally:
            temp.cleanup()

    def test_whitelisted_shared_service_address_is_not_a_finding(self):
        temp, output = self.run_example()
        try:
            findings = read_jsonl(output / "findings.jsonl")
            address_findings = [f for f in findings if "shared-address" in f["finding_type"]]
            self.assertEqual(address_findings, [])
            rendered = json.dumps(findings, ensure_ascii=False)
            self.assertNotIn("舞弊成立", rendered)
            self.assertNotIn("串标成立", rendered)
        finally:
            temp.cleanup()

    def test_bid_similarity_is_scoped_to_same_lot_and_configured_threshold(self):
        temp, output = self.run_example()
        try:
            similarities = [f for f in read_jsonl(output / "findings.jsonl") if f["finding_type"] == "bid-text-similarity"]
            self.assertEqual(len(similarities), 1)
            entity_ids = {entity["id"] for entity in similarities[0]["entities"]}
            self.assertTrue({"V001", "V002", "L-001"}.issubset(entity_ids))
            factor = similarities[0]["risk_factors"][0]
            self.assertGreaterEqual(factor["similarity"], factor["threshold"])
        finally:
            temp.cleanup()

    def test_handoff_requires_human_approval_and_run_is_offline(self):
        temp, output = self.run_example()
        try:
            handoff = json.loads((output / "investigation_handoff.json").read_text(encoding="utf-8"))
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["status"], "recommended")
            self.assertTrue(handoff["human_approval_required"])
            self.assertFalse(manifest["network_access"])
            self.assertEqual(manifest["skill_version"], "0.2.2")
            self.assertEqual(manifest["parameters"]["config_version"], "SYNTHETIC-PROCUREMENT-CONFIG-1.0")
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
