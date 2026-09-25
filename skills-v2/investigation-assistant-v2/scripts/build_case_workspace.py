#!/usr/bin/env python3
"""Build an offline, scope-controlled investigation workspace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import shutil
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

VERSION = "0.2.3"
SKILL = "investigation-assistant-v2"

MESSAGE_FIELDS = {
    "message_id": ["message_id", "id", "消息编号", "邮件编号"],
    "timestamp": ["timestamp", "time", "sent_at", "时间", "发送时间"],
    "sender": ["sender", "from", "发件人", "发送人"],
    "recipient": ["recipient", "to", "收件人", "接收人"],
    "channel": ["channel", "type", "渠道", "消息类型"],
    "content": ["content", "body", "text", "内容", "聊天内容", "正文"],
}
LOG_FIELDS = {
    "event_id": ["event_id", "id", "事件编号", "日志编号"],
    "timestamp": ["timestamp", "time", "event_time", "时间", "发生时间"],
    "actor": ["actor", "user", "employee_id", "用户", "员工编号", "操作人"],
    "event_type": ["event_type", "action", "操作", "事件类型"],
    "object": ["object", "resource", "file", "对象", "资源", "文件"],
    "device": ["device", "device_id", "设备", "设备编号"],
    "ip": ["ip", "ip_address", "IP", "IP地址"],
    "result": ["result", "status", "结果", "状态"],
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def header_key(value: Any) -> str:
    return re.sub(r"[\s_\-./\\]+", "", clean_text(value).lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# v0.2.0: scope.json 合法键清单（白名单），未知键会被拒绝并提示
SCOPE_KEYS = frozenset({
    "case_id", "purpose",
    "authorization_confirmed", "authorization_reference",
    "date_range", "persons_in_scope", "allowed_sources",
    "source_types", "assumed_timezone", "network_access",
    "issues", "interviewees",
    # v0.2.0 新增可选配置
    "holidays", "context_from_other_skill",
})


def validate_scope(scope: Dict[str, Any]) -> None:
    """v0.2.0: 拒绝未知 scope 键，避免静默忽略用户配置"""
    unknown = set(scope.keys()) - SCOPE_KEYS
    if unknown:
        suggestions = []
        for key in unknown:
            similar = [k for k in SCOPE_KEYS if key.lower() in k.lower() or k.lower() in key.lower()]
            if similar:
                suggestions.append("%s（是否想写 %s？）" % (key, " 或 ".join(similar[:2])))
        msg = "scope.json 包含未知键：%s。" % ", ".join(sorted(unknown))
        if suggestions:
            msg += " 提示：" + "; ".join(suggestions) + "。"
        msg += " 合法键清单：%s" % ", ".join(sorted(SCOPE_KEYS))
        raise ValueError(msg)


def load_scope(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        scope = json.load(handle)
    if not isinstance(scope, dict):
        raise ValueError("scope 顶层必须是 JSON 对象")
    validate_scope(scope)
    required = ["case_id", "purpose", "authorization_confirmed", "date_range", "persons_in_scope", "allowed_sources", "network_access"]
    missing = [key for key in required if key not in scope]
    if missing:
        raise ValueError("scope gate 缺失：%s" % ", ".join(missing))
    if scope["authorization_confirmed"] is not True:
        raise PermissionError("authorization_confirmed 必须明确为 true")
    if scope["network_access"] is not False:
        raise ValueError("核心 workflow 必须设置 network_access=false；联网需另行授权和工具")
    if not isinstance(scope["allowed_sources"], list) or not scope["allowed_sources"]:
        raise ValueError("allowed_sources 必须是非空列表")
    if not isinstance(scope["persons_in_scope"], list):
        raise ValueError("persons_in_scope 必须是列表")
    date_range = scope["date_range"]
    try:
        date.fromisoformat(date_range["start"])
        date.fromisoformat(date_range["end"])
    except Exception as exc:
        raise ValueError("date_range 必须包含 YYYY-MM-DD 的 start/end") from exc
    return scope


def safe_source(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise ValueError("allowed_sources 必须使用相对路径：%s" % relative)
    path = (root / relative).resolve()
    if root != path and root not in path.parents:
        raise ValueError("allowed source 不得跳出 input-dir：%s" % relative)
    if not path.is_file():
        raise FileNotFoundError("allowed source 不存在：%s" % relative)
    return path


def resolve_mapping(headers: Sequence[str], schema: Dict[str, Sequence[str]], required: Sequence[str]) -> Dict[str, str]:
    normalized: Dict[str, List[str]] = defaultdict(list)
    for header in headers:
        normalized[header_key(header)].append(header)
    mapping = {}
    for canonical, aliases in schema.items():
        matches = []
        for alias in aliases:
            matches.extend(normalized.get(header_key(alias), []))
        matches = list(dict.fromkeys(matches))
        if len(matches) == 1:
            mapping[canonical] = matches[0]
    missing = [field for field in required if field not in mapping]
    if missing:
        raise ValueError("结构化文件缺核心字段：%s" % ", ".join(missing))
    return mapping


def parse_timestamp(value: Any, assumed_timezone: str) -> Tuple[Optional[datetime], Optional[str]]:
    raw = clean_text(value)
    if not raw:
        return None, "时间戳为空"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            try:
                tz = ZoneInfo(assumed_timezone)
            except Exception as tz_exc:
                tz = timezone(timedelta(hours=_FALLBACK_TZ_OFFSET_HOURS))
                return parsed.replace(tzinfo=tz), "时区库不可用（%s），已回退固定偏移 +%d:%02d" % (tz_exc.__class__.__name__, _FALLBACK_TZ_OFFSET_HOURS, 0)
            parsed = parsed.replace(tzinfo=tz)
            return parsed, "原时间戳无时区，按 %s 解释" % assumed_timezone
        return parsed, None
    except Exception:
        return None, "无法解析时间戳：%s" % raw


# v0.2.0: 时区库降级常量（仅在 ZoneInfo 不可用时使用，固定偏移 +08:00 = Asia/Shanghai）
# 大多数用户都用东八区；其他时区用户可在 scope.json 显式设置 assumed_timezone
_FALLBACK_TZ_OFFSET_HOURS = 8


def _check_timezone_health(assumed_timezone: str) -> Dict[str, Any]:
    """v0.2.0: 检测 ZoneInfo 库的健康状态，告知用户是否需要安装 tzdata

    Returns dict with:
        - tzdata_installed: bool
        - assumed_timezone: str
        - available: bool
        - fallback_offset_hours: int
        - recommendation: str
    """
    status: Dict[str, Any] = {
        "assumed_timezone": assumed_timezone,
        "tzdata_installed": False,
        "available": False,
        "fallback_offset_hours": _FALLBACK_TZ_OFFSET_HOURS,
    }
    try:
        ZoneInfo(assumed_timezone)
        status["available"] = True
        status["tzdata_installed"] = True
        status["recommendation"] = "IANA 时区数据库可用，timeline 将使用精确时区。"
        return status
    except Exception as exc:
        status["available"] = False
        status["tzdata_installed"] = False
        status["error"] = "%s: %s" % (exc.__class__.__name__, str(exc))
        status["recommendation"] = (
            "IANA 时区库不可用，已回退到固定偏移 +%d:00。"
            "Windows 用户建议执行 `pip install tzdata` 以获得完整时区支持；"
            "其他系统通常已自带。"
        ) % _FALLBACK_TZ_OFFSET_HOURS
        return status


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


class EvidenceRegistry:
    def __init__(self) -> None:
        self.items: List[Dict[str, Any]] = []

    def add_file(self, relative: str, digest: str, size: int, mime: str) -> str:
        evidence_id = "EV-%06d" % (len(self.items) + 1)
        self.items.append({
            "evidence_id": evidence_id, "source_file": relative, "source_hash": "sha256:" + digest,
            "sheet": None, "row": None, "field": "file", "value": relative,
            "extraction_method": "file_inventory", "confidence": 1.0, "size_bytes": size, "mime_type": mime,
        })
        return evidence_id

    def add_row(self, relative: str, digest: str, row: int, field: str, value: Any, method: str = "direct") -> str:
        evidence_id = "EV-%06d" % (len(self.items) + 1)
        self.items.append({
            "evidence_id": evidence_id, "source_file": relative, "source_hash": "sha256:" + digest,
            "sheet": None, "row": row, "field": field, "value": value,
            "extraction_method": method, "confidence": 1.0,
        })
        return evidence_id


def source_type(relative: str, scope: Dict[str, Any]) -> str:
    configured = scope.get("source_types", {}).get(relative)
    if configured:
        return clean_text(configured).lower()
    name = Path(relative).name.lower()
    if any(token in name for token in ("message", "chat", "email", "mail", "消息", "聊天", "邮件")):
        return "messages"
    if any(token in name for token in ("log", "event", "access", "日志", "访问")):
        return "logs"
    if Path(relative).suffix.lower() in (".txt", ".md"):
        return "text"
    return "unrecognized"


def row_in_scope(timestamp: datetime, actors: Sequence[str], scope: Dict[str, Any]) -> Tuple[bool, str]:
    start = date.fromisoformat(scope["date_range"]["start"])
    end = date.fromisoformat(scope["date_range"]["end"])
    if timestamp.date() < start or timestamp.date() > end:
        return False, "时间超出 scope date_range"
    persons = {clean_text(person) for person in scope["persons_in_scope"]}
    if persons and not any(clean_text(actor) in persons for actor in actors if clean_text(actor)):
        return False, "人员超出 persons_in_scope"
    return True, ""


def process_messages(
    path: Path, relative: str, digest: str, scope: Dict[str, Any], registry: EvidenceRegistry
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """v0.2.0: 返回 5 元组，新增 unparseable_rows 列表分离坏时间戳"""
    normalized, excluded, unparseable, warnings, corpus = [], [], [], [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = [clean_text(h) for h in (reader.fieldnames or [])]
        mapping = resolve_mapping(headers, MESSAGE_FIELDS, ("message_id", "timestamp", "sender", "content"))
        for row_number, source in enumerate(reader, start=2):
            source = {clean_text(k): v for k, v in source.items() if k is not None}
            row = {field: clean_text(source.get(mapping.get(field, ""), "")) for field in MESSAGE_FIELDS}
            parsed, warning = parse_timestamp(row["timestamp"], scope.get("assumed_timezone", "UTC"))
            evidence_id = registry.add_row(relative, digest, row_number, "content", row["content"], "normalized_message")
            if warning:
                warnings.append("%s 第 %d 行：%s" % (relative, row_number, warning))
            if parsed is None:
                # v0.2.0: 坏时间戳单独列出
                unparseable.append({"source_file": relative, "source_row": row_number, "reason": warning or "时间戳无效", "evidence_id": evidence_id, "raw_timestamp": row["timestamp"]})
                continue
            allowed, reason = row_in_scope(parsed, (row["sender"], row["recipient"]), scope)
            if not allowed:
                # v0.2.0: 加 scope_status 列，区分"越界"vs"时间无效"
                excluded.append({"source_file": relative, "source_row": row_number, "reason": reason, "evidence_id": evidence_id, "scope_status": "out_of_scope"})
                continue
            item = dict(row)
            item.update({"timestamp": parsed.isoformat(), "source_file": relative, "source_row": row_number, "evidence_id": evidence_id})
            normalized.append(item)
            corpus.append({"text": " ".join((row["sender"], row["recipient"], row["content"])), "summary": "%s 向 %s 发送消息：%s" % (row["sender"], row["recipient"], row["content"][:100]), "evidence_id": evidence_id, "actor": row["sender"]})
    return normalized, excluded, unparseable, warnings, corpus


def process_logs(
    path: Path, relative: str, digest: str, scope: Dict[str, Any], registry: EvidenceRegistry
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """v0.2.0: 返回 5 元组，新增 unparseable_rows 列表分离坏时间戳"""
    normalized, excluded, unparseable, warnings, corpus = [], [], [], [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = [clean_text(h) for h in (reader.fieldnames or [])]
        mapping = resolve_mapping(headers, LOG_FIELDS, ("event_id", "timestamp", "actor", "event_type"))
        for row_number, source in enumerate(reader, start=2):
            source = {clean_text(k): v for k, v in source.items() if k is not None}
            row = {field: clean_text(source.get(mapping.get(field, ""), "")) for field in LOG_FIELDS}
            parsed, warning = parse_timestamp(row["timestamp"], scope.get("assumed_timezone", "UTC"))
            evidence_id = registry.add_row(relative, digest, row_number, "event", " | ".join(row.values()), "normalized_log")
            if warning:
                warnings.append("%s 第 %d 行：%s" % (relative, row_number, warning))
            if parsed is None:
                unparseable.append({"source_file": relative, "source_row": row_number, "reason": warning or "时间戳无效", "evidence_id": evidence_id, "raw_timestamp": row["timestamp"]})
                continue
            allowed, reason = row_in_scope(parsed, (row["actor"],), scope)
            if not allowed:
                excluded.append({"source_file": relative, "source_row": row_number, "reason": reason, "evidence_id": evidence_id, "scope_status": "out_of_scope"})
                continue
            item = dict(row)
            item.update({"timestamp": parsed.isoformat(), "source_file": relative, "source_row": row_number, "evidence_id": evidence_id})
            normalized.append(item)
            summary = "%s 执行 %s，对象 %s，结果 %s" % (row["actor"], row["event_type"], row["object"], row["result"])
            corpus.append({"text": " ".join(row.values()), "summary": summary, "evidence_id": evidence_id, "actor": row["actor"]})
    return normalized, excluded, unparseable, warnings, corpus


def process_text(path: Path, relative: str, digest: str, registry: EvidenceRegistry) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows, corpus = [], []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        value = clean_text(line)
        if not value:
            continue
        evidence_id = registry.add_row(relative, digest, line_number, "line", value, "direct_text")
        rows.append({"source_file": relative, "line": line_number, "content": value, "evidence_id": evidence_id})
        corpus.append({"text": value, "summary": "%s 第 %d 行记载：%s" % (relative, line_number, value[:100]), "evidence_id": evidence_id, "actor": ""})
    return rows, corpus


def contains_any(value: str, keywords: Sequence[Any]) -> bool:
    haystack = unicodedata.normalize("NFKC", value).lower()
    return any(unicodedata.normalize("NFKC", clean_text(keyword)).lower() in haystack for keyword in keywords if clean_text(keyword))


def unique(values: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def build_entities_and_relationships(messages: Sequence[Dict[str, Any]], logs: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    entities, entity_ids, edges = [], set(), []

    def add_entity(kind: str, value: str) -> str:
        entity_id = kind + ":" + value
        if entity_id not in entity_ids:
            entities.append({"entity_id": entity_id, "entity_type": kind, "value": value})
            entity_ids.add(entity_id)
        return entity_id

    for message in messages:
        sender = add_entity("person", message["sender"])
        recipient_type = "email" if "@" in message["recipient"] else "person"
        recipient = add_entity(recipient_type, message["recipient"])
        edges.append({"source": sender, "target": recipient, "type": "messaged", "evidence_refs": [message["evidence_id"]]})
        for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", message["content"]):
            add_entity("email", email.lower())
    for log in logs:
        actor = add_entity("person", log["actor"])
        if log["device"]:
            device = add_entity("device", log["device"])
            edges.append({"source": actor, "target": device, "type": "used_device", "evidence_refs": [log["evidence_id"]]})
        if log["object"]:
            obj = add_entity("document", log["object"])
            edges.append({"source": actor, "target": obj, "type": "acted_on", "action": log["event_type"], "evidence_refs": [log["evidence_id"]]})
    return entities, {"schema_version": VERSION, "nodes": [{"id": e["entity_id"], "type": e["entity_type"], "label": e["value"]} for e in entities], "edges": edges}


def build_issue_outputs(scope: Dict[str, Any], corpus: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    matrix, hypotheses, findings = [], [], []
    priority_points = {"low": 1, "medium": 2, "high": 4, "critical": 6}
    for issue in scope.get("issues", []):
        supporting = [entry for entry in corpus if contains_any(entry["text"], issue.get("keywords", []))]
        contradictory = [entry for entry in corpus if contains_any(entry["text"], issue.get("contradictory_keywords", []))]
        support_refs = unique([entry["evidence_id"] for entry in supporting])
        contradiction_refs = unique([entry["evidence_id"] for entry in contradictory])
        missing = issue.get("missing_evidence", [])
        alternatives = issue.get("alternative_explanations", [])
        matrix.append({
            "issue_id": issue.get("issue_id", "ISSUE-%03d" % (len(matrix) + 1)),
            "allegation_or_issue": issue.get("allegation_or_issue", ""),
            "supporting_evidence_refs": "|".join(support_refs),
            "contradictory_evidence_refs": "|".join(contradiction_refs),
            "missing_evidence": "|".join(clean_text(value) for value in missing),
            "alternative_explanations": "|".join(clean_text(value) for value in alternatives),
            "status": "open",
        })
        hypotheses.append({
            "hypothesis_id": "HYP-%03d" % (len(hypotheses) + 1), "issue_id": matrix[-1]["issue_id"],
            "hypothesis": issue.get("allegation_or_issue", ""), "supporting_evidence_refs": "|".join(support_refs),
            "contradictory_evidence_refs": "|".join(contradiction_refs), "missing_evidence": "|".join(clean_text(value) for value in missing),
            "alternative_explanations": "|".join(clean_text(value) for value in alternatives),
            "next_validation_step": "回到候选记录上下文并补齐列示证据", "status": "open",
        })
        refs = unique(support_refs + contradiction_refs)
        if refs:
            priority = clean_text(issue.get("priority", "medium")).lower()
            if priority not in priority_points:
                priority = "medium"
            facts = unique([entry["summary"] for entry in supporting + contradictory])[:20]
            strength = "moderate" if len(refs) >= 2 else "weak"
            findings.append({
                "finding_id": "INV-%06d" % (len(findings) + 1), "skill": SKILL,
                "finding_type": "investigation-lead", "title": "调查 issue 的候选证据与反证已登记",
                "risk_priority": priority, "evidence_strength": strength, "risk_score": priority_points[priority],
                "risk_factors": [{"factor": "scope_assigned_priority", "points": priority_points[priority]}],
                "entities": [{"type": "person", "id": person} for person in scope.get("persons_in_scope", [])],
                "facts": facts,
                "inferences": ["关键词检索把 %d 条支持候选和 %d 条反证候选连接到该 issue；相关性仍需人工阅读上下文确认" % (len(support_refs), len(contradiction_refs))],
                "hypotheses": [issue.get("allegation_or_issue", "")],
                "open_questions": [clean_text(value) for value in missing], "evidence_refs": refs,
                "recommended_next_steps": ["核验候选记录上下文", "补齐反证与缺失证据", "由有权人员决定访谈顺序"],
                "human_review_required": True,
                "judgment_layer": "线索层（待复核）",  # v0.2.0: 四层标记
            })
    return matrix, hypotheses, findings


def validate_refs(registry: EvidenceRegistry, timeline: Sequence[Dict[str, Any]], relationships: Dict[str, Any], matrix: Sequence[Dict[str, Any]], hypotheses: Sequence[Dict[str, Any]], findings: Sequence[Dict[str, Any]]) -> None:
    evidence_ids = {item["evidence_id"] for item in registry.items}
    refs = []
    refs.extend(row["evidence_id"] for row in timeline)
    refs.extend(ref for edge in relationships["edges"] for ref in edge["evidence_refs"])
    for collection in (matrix, hypotheses):
        for row in collection:
            for field in ("supporting_evidence_refs", "contradictory_evidence_refs"):
                refs.extend(value for value in row.get(field, "").split("|") if value)
    refs.extend(ref for finding in findings for ref in finding["evidence_refs"])
    missing = set(refs) - evidence_ids
    if missing:
        raise ValueError("输出引用不存在的 evidence：%s" % ", ".join(sorted(missing)))
    if any(not finding["human_review_required"] for finding in findings):
        raise ValueError("所有 investigation finding 必须要求人工复核")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args(argv)
    if args.check_env:
        tz_status = _check_timezone_health(scope.get("assumed_timezone", "UTC") if False else "Asia/Shanghai")
        print(json.dumps({"python": sys.version.split()[0], "recommended": ">=3.10", "formats": ["csv", "txt", "md"], "tzdata_status": tz_status, "network_required": False}, ensure_ascii=False))
        return 0
    if not args.input_dir or not args.scope or not args.output:
        parser.error("正式运行需要 --input-dir、--scope 和 --output")
    root = args.input_dir.resolve()
    scope_path = args.scope.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    scope = load_scope(scope_path)

    # v0.2.0: 检查时区库健康，写入 manifest warnings
    timezone_warnings = _check_timezone_health(scope.get("assumed_timezone", "UTC"))

    output = args.output.resolve()
    if root == output or root in output.parents:
        raise ValueError("输出目录不得位于输入目录内部")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("输出目录非空；请使用新目录：%s" % output)

    allowed = []
    for relative_value in scope["allowed_sources"]:
        relative = clean_text(relative_value).replace("\\", "/")
        allowed.append((relative, safe_source(root, relative)))
    output.mkdir(parents=True, exist_ok=True)
    raw_root = output / "evidence" / "raw"
    derived_root = output / "derived"
    raw_root.mkdir(parents=True, exist_ok=True)
    derived_root.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    registry = EvidenceRegistry()
    inventory, custody, file_hashes = [], [], {}
    for relative, source in allowed:
        digest = sha256_file(source)
        file_hashes[relative] = digest
        mime = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        evidence_id = registry.add_file(relative, digest, source.stat().st_size, mime)
        inventory.append({
            "evidence_id": evidence_id, "relative_path": relative, "sha256": digest,
            "size_bytes": source.stat().st_size, "modified_at": datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(),
            "mime_type": mime, "source_type": source_type(relative, scope),
        })
        custody.append({"timestamp": datetime.now(timezone.utc).isoformat(), "event": "registered", "actor": SKILL, "evidence_id": evidence_id, "source": relative, "target": None, "sha256": digest})
        target = raw_root / Path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied_hash = sha256_file(target)
        if copied_hash != digest:
            raise IOError("raw 副本 hash 不一致：%s" % relative)
        target.chmod(target.stat().st_mode & ~0o222)
        if target.stat().st_mode & 0o222:
            raise OSError("无法将 raw 副本设置为只读：%s" % relative)
        custody.append({"timestamp": datetime.now(timezone.utc).isoformat(), "event": "copied_and_verified", "actor": SKILL, "evidence_id": evidence_id, "source": relative, "target": "evidence/raw/" + relative, "sha256": copied_hash, "protection": "read-only"})

    messages, logs, text_lines, excluded, unparseable, warnings, corpus = [], [], [], [], [], [], []
    for relative, source in allowed:
        kind = source_type(relative, scope)
        if kind == "messages":
            rows, out, bad, notes, entries = process_messages(source, relative, file_hashes[relative], scope, registry)
            messages.extend(rows); excluded.extend(out); unparseable.extend(bad); warnings.extend(notes); corpus.extend(entries)
        elif kind == "logs":
            rows, out, bad, notes, entries = process_logs(source, relative, file_hashes[relative], scope, registry)
            logs.extend(rows); excluded.extend(out); unparseable.extend(bad); warnings.extend(notes); corpus.extend(entries)
        elif kind == "text":
            rows, entries = process_text(source, relative, file_hashes[relative], registry)
            text_lines.extend(rows); corpus.extend(entries)
        else:
            warnings.append("已登记但未解析的文件：%s" % relative)

    write_csv(derived_root / "normalized_messages.csv", messages, tuple(MESSAGE_FIELDS) + ("source_file", "source_row", "evidence_id"))
    write_csv(derived_root / "normalized_logs.csv", logs, tuple(LOG_FIELDS) + ("source_file", "source_row", "evidence_id"))
    write_csv(derived_root / "text_lines.csv", text_lines, ("source_file", "line", "content", "evidence_id"))
    write_csv(output / "out_of_scope_rows.csv", excluded, ("source_file", "source_row", "scope_status", "reason", "evidence_id"))
    write_csv(output / "unparseable_rows.csv", unparseable, ("source_file", "source_row", "scope_status", "reason", "raw_timestamp", "evidence_id"))

    timeline = []
    for message in messages:
        timeline.append({"timestamp": message["timestamp"], "actor": message["sender"], "event_type": "message", "object": "%s → %s: %s" % (message["sender"], message["recipient"], message["content"][:120]), "source_file": message["source_file"], "source_row": message["source_row"], "evidence_id": message["evidence_id"], "confidence": 1.0})
    for log in logs:
        timeline.append({"timestamp": log["timestamp"], "actor": log["actor"], "event_type": log["event_type"], "object": log["object"], "source_file": log["source_file"], "source_row": log["source_row"], "evidence_id": log["evidence_id"], "confidence": 1.0})
    timeline.sort(key=lambda row: row["timestamp"])
    write_csv(output / "timeline.csv", timeline, ("timestamp", "actor", "event_type", "object", "source_file", "source_row", "evidence_id", "confidence"))

    entities, relationships = build_entities_and_relationships(messages, logs)
    write_csv(output / "entity_index.csv", entities, ("entity_id", "entity_type", "value"))
    (output / "relationships.json").write_text(json.dumps(relationships, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matrix, hypotheses, findings = build_issue_outputs(scope, corpus)
    write_csv(output / "evidence_matrix.csv", matrix, ("issue_id", "allegation_or_issue", "supporting_evidence_refs", "contradictory_evidence_refs", "missing_evidence", "alternative_explanations", "status"))
    write_csv(output / "hypothesis_register.csv", hypotheses, ("hypothesis_id", "issue_id", "hypothesis", "supporting_evidence_refs", "contradictory_evidence_refs", "missing_evidence", "alternative_explanations", "next_validation_step", "status"))
    write_jsonl(output / "findings.jsonl", findings)

    interview_rows = []
    for interviewee in scope.get("interviewees", []):
        person = clean_text(interviewee.get("id"))
        known = unique([entry["summary"] for entry in corpus if entry.get("actor") == person])[:8]
        interview_rows.append({
            "interviewee": person, "objective": clean_text(interviewee.get("objective")),
            "known_facts": "|".join(known),
            "unknown_facts": "|".join(unique([clean_text(value) for issue in scope.get("issues", []) for value in issue.get("missing_evidence", [])])),
            "questions": "请按时间顺序说明相关活动|当时目的和授权依据是什么|哪些记录可以验证或否定该说明|是否存在其他合理解释",
            "documents_to_show": "由调查负责人从 evidence_matrix 中选择并确认展示顺序",
            "follow_up_triggers": "回答与已登记时间线不一致|提出新的授权文件或证人|指出系统自动行为",
        })
    write_csv(output / "interview_plan.csv", interview_rows, ("interviewee", "objective", "known_facts", "unknown_facts", "questions", "documents_to_show", "follow_up_triggers"))

    validate_refs(registry, timeline, relationships, matrix, hypotheses, findings)
    write_jsonl(output / "evidence_inventory.jsonl", inventory)
    write_jsonl(output / "evidence.jsonl", registry.items)
    for relative in ("derived/normalized_messages.csv", "derived/normalized_logs.csv", "derived/text_lines.csv", "timeline.csv", "entity_index.csv", "relationships.json", "evidence_matrix.csv", "hypothesis_register.csv", "findings.jsonl", "interview_plan.csv"):
        path = output / relative
        custody.append({"timestamp": datetime.now(timezone.utc).isoformat(), "event": "derived", "actor": SKILL, "evidence_id": None, "source": "registered evidence", "target": relative, "sha256": sha256_file(path)})
    write_jsonl(output / "chain_of_custody.jsonl", custody)

    memo = [
        "# 调查备忘录模板", "", "- Case ID：`%s`" % scope["case_id"], "- 调查目的：%s" % scope["purpose"],
        "- 授权依据：`%s`" % scope.get("authorization_reference", "未填写"),
        "- 期间：%s 至 %s" % (scope["date_range"]["start"], scope["date_range"]["end"]),
        "- 人员范围：%s" % "、".join(scope["persons_in_scope"]), "", "## 已核验事实", "", "（由调查人员回到 evidence 后填写）",
        "", "## 推断", "", "（说明推断规则、替代解释和置信边界）", "", "## 待验证假设与反证", "", "（引用 hypothesis_register，不把 allegation 写成事实）",
        "", "## 证据缺口与下一步", "", "（引用 evidence_matrix 和访谈计划）", "", "## 人工判断", "", "（仅由有权人员在完成程序后填写）",
        "", "> 本模板由工具生成，未形成责任、处分、法律或事实认定。",
    ]
    (output / "case_memo_template.md").write_text("\n".join(memo) + "\n", encoding="utf-8")
    quality = [
        "# 调查工作空间数据质量", "",
        "> 技术附录：本文件是数据体检的机器记录（范围、哈希、时区等），供复核追溯，不是调查结论。", "",
        "- 已登记并验证 raw 文件：%d" % len(inventory),
        "- 范围内消息：%d" % len(messages), "- 范围内日志：%d" % len(logs),
        "- 文本证据行：%d" % len(text_lines),
        "- 范围外行（人员或日期越界）：%d" % len(excluded),
        "- 坏时间戳行：%d" % len(unparseable),
        "- 时间线事件：%d" % len(timeline), "- Issues：%d" % len(matrix), "",
        "## 警告", "",
    ]
    quality.extend(["- " + warning for warning in warnings] or ["- 无"])

    # v0.2.0: 时区库健康状况写入 data_quality.md
    quality.extend(["", "## 时区库状态", ""])
    quality.append("- 假定时区：`%s`" % timezone_warnings["assumed_timezone"])
    quality.append("- 时区库可用：%s" % ("是" if timezone_warnings["available"] else "否"))
    if not timezone_warnings["available"]:
        quality.append("- 回退偏移：+%d:00" % timezone_warnings["fallback_offset_hours"])
        quality.append("- 建议：%s" % timezone_warnings["recommendation"])
    else:
        quality.append("- %s" % timezone_warnings["recommendation"])

    quality.extend(["", "> 关键词命中只表示候选关联，必须回到上下文确认。无命中不表示事项未发生。"])
    (output / "data_quality.md").write_text("\n".join(quality) + "\n", encoding="utf-8")

    script = Path(__file__).resolve()
    manifest = {
        "run_id": "INV-%s-%s" % (started.strftime("%Y%m%dT%H%M%SZ"), sha256_file(scope_path)[:8]),
        "skill": SKILL, "skill_version": VERSION, "case_id": scope["case_id"],
        "started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
        "scope_file": {"path": scope_path.name, "sha256": sha256_file(scope_path)},
        "scope": {"purpose": scope["purpose"], "authorization_reference": scope.get("authorization_reference"), "date_range": scope["date_range"], "persons_in_scope": scope["persons_in_scope"], "allowed_sources": scope["allowed_sources"], "assumed_timezone": scope.get("assumed_timezone", "UTC")},
        "input_files": inventory, "scripts": {script.name: "sha256:" + sha256_file(script)},
        "warnings": warnings,
        "timezone_health": timezone_warnings,
        "network_access": False,
        "outputs": ["evidence/raw/", "derived/", "evidence_inventory.jsonl", "evidence.jsonl", "chain_of_custody.jsonl", "out_of_scope_rows.csv", "unparseable_rows.csv", "timeline.csv", "entity_index.csv", "relationships.json", "evidence_matrix.csv", "hypothesis_register.csv", "findings.jsonl", "interview_plan.csv", "case_memo_template.md", "data_quality.md", "run_manifest.json", "dashboard.html"],
        "note": "技术审计轨迹：记录本次运行的机器可追溯信息（哈希、范围、时区等），供复核追溯，不是调查结论。",
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        build_dashboard_html(manifest, scope, inventory, timeline, excluded, matrix, custody, warnings, output)
    except Exception as _e:
        print("WARNING: dashboard.html generation failed: %s" % _e, file=sys.stderr)
    print(json.dumps({"output": str(output), "raw_files": len(inventory), "timeline_rows": len(timeline), "out_of_scope_rows": len(excluded), "issues": len(matrix), "findings": len(findings), "timezone_available": timezone_warnings["available"]}, ensure_ascii=False))
    return 0


DASHBOARD_CSS = """*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f5f3ef;--card:#fff;--ink:#1a1a1a;--muted:#6b6b6b;--faint:#9a9a9a;--line:#e5e1da;--brand:#2c4a6e;--brand-soft:#eef2f7;--red:#b42318;--red-bg:#fdecea;--amber:#b54708;--amber-bg:#fdf3e7;--green:#067647;--green-bg:#eaf7ef}
@media(prefers-color-scheme:dark){:root{--bg:#171614;--card:#211f1d;--ink:#f2efea;--muted:#b3ada4;--faint:#7d776e;--line:#33302c;--brand:#8fb4dc;--brand-soft:#1b2733;--red:#f97066;--red-bg:#3a1e1c;--amber:#fdb022;--amber-bg:#33260f;--green:#4ade80;--green-bg:#13291c}}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;padding:40px 20px;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto}
.masthead{display:flex;align-items:center;gap:18px;margin-bottom:28px}
.seal{width:64px;height:64px;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:800;flex:none;background:var(--green-bg);color:var(--green)}
.masthead h1{font-size:26px;font-weight:800;letter-spacing:-.01em}
.masthead .sub{font-size:13px;color:var(--muted);margin-top:3px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px;margin-left:8px;vertical-align:middle;background:var(--green-bg);color:var(--green)}
.verdict{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--brand);border-radius:12px;padding:22px 26px;margin-bottom:14px}
.verdict .lbl{font-size:12px;font-weight:700;letter-spacing:.12em;color:var(--brand);text-transform:uppercase;margin-bottom:8px}
.verdict p{font-size:17px;line-height:1.75}
.verdict b{color:var(--brand);font-weight:800}
.scope{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 22px;margin-bottom:26px;font-size:14px}
.scope .row{display:flex;gap:10px;padding:4px 0;border-bottom:1px dashed var(--line)}
.scope .row:last-child{border-bottom:0}
.scope .sk{color:var(--faint);min-width:90px;font-size:13px}
.scope .sv{flex:1}
h2.sec{font-size:13px;font-weight:800;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:30px 0 14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:10px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;text-align:center}
.kpi .v{font-size:26px;font-weight:800;color:var(--brand);letter-spacing:-.02em}
.kpi .l{font-size:12px;color:var(--muted);margin-top:4px}
.issue{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin-bottom:12px;border-left:5px solid var(--brand)}
.issue h3{font-size:15px;font-weight:700;margin-bottom:8px}
.issue .meta{font-size:13px;color:var(--muted);display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}
.issue .meta b{color:var(--ink)}
.issue .miss{font-size:13px;color:var(--muted);border-top:1px dashed var(--line);padding-top:8px;margin-top:4px}
.issue .status{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px;background:var(--amber-bg);color:var(--amber)}
.note{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 22px;font-size:14px;margin-bottom:10px}
.note b{font-weight:700}
.links{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.links a{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px 16px;text-decoration:none;color:var(--ink)}
.links a:hover{border-color:var(--brand)}
.lk-name{display:block;font-weight:700;font-size:14px}
.lk-desc{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.disclaimer{margin-top:26px;background:var(--brand-soft);border:1px solid var(--line);border-radius:12px;padding:16px 22px;font-size:13px;color:var(--muted)}
.disclaimer b{color:var(--brand)}
.foot{text-align:center;color:var(--faint);font-size:12px;margin-top:22px}
@media print{body{background:#fff;padding:0}.issue,.note,.links a,.verdict,.disclaimer,.scope,.kpi{break-inside:avoid}}
@media(max-width:640px){body{padding:20px 12px}.masthead h1{font-size:20px}.kpis{grid-template-columns:1fr 1fr}.links{grid-template-columns:1fr}}"""


def build_dashboard_html(manifest, scope, inventory, timeline, excluded, matrix, custody, warnings, output_dir):
    """调查工作空间全景（面向调查负责人，全中文，强调授权/证据链/待验证事项）。"""
    from html import escape

    duration_str, date_str = "—", "—"
    try:
        s = datetime.fromisoformat(manifest["started_at"])
        e = datetime.fromisoformat(manifest["finished_at"])
        duration_str = "%.1f 秒" % (e - s).total_seconds()
        date_str = s.strftime("%Y-%m-%d %H:%M")
    except (KeyError, ValueError):
        pass
    version = manifest.get("skill_version", "?")
    case_id = manifest.get("case_id", "—")

    # scope rows
    dr = scope.get("date_range", {})
    date_range = "%s ~ %s" % (dr.get("start", "?"), dr.get("end", "?"))
    persons = "、".join(scope.get("persons_in_scope", [])) or "（无）"
    sources = "、".join(scope.get("allowed_sources", [])) or "（无）"
    auth = scope.get("authorization_reference") or "（未提供文号）"
    tz = scope.get("assumed_timezone", "UTC")
    scope_html = "".join(
        '<div class="row"><span class="sk">%s</span><span class="sv">%s</span></div>' % (k, escape(str(v)))
        for k, v in [
            ("调查目的", scope.get("purpose", "—")),
            ("授权依据", auth),
            ("时间范围", date_range),
            ("涉及人员", persons),
            ("允许来源", sources),
            ("假定时区", tz),
        ]
    )

    statement = "已建立可追溯调查工作空间：登记 <b>%d</b> 个原始文件（含 SHA-256），形成 <b>%d</b> 条时间线事件、<b>%d</b> 个待验证事项。所有证据已按授权范围登记，<b>等待人工复核</b>——本工作空间不做责任认定。" % (
        len(inventory), len(timeline), len(matrix))

    # issue cards
    issue_cards = []
    for it in matrix:
        issue_id = escape(str(it.get("issue_id", "")))
        allegation = escape(it.get("allegation_or_issue", "") or "—")
        sup = it.get("supporting_evidence_refs", "")
        con = it.get("contradictory_evidence_refs", "")
        nsup = len([x for x in sup.split("|") if x]) if sup else 0
        ncon = len([x for x in con.split("|") if x]) if con else 0
        missing = it.get("missing_evidence", "")
        miss_list = [x for x in missing.split("|") if x][:3]
        miss_html = ('<div class="miss"><span class="k">缺失证据</span>%s</div>' % escape("；".join(miss_list))) if miss_list else ""
        issue_cards.append(
            '<article class="issue"><h3>%s · %s <span class="status">待验证</span></h3>'
            '<div class="meta"><span>支持证据 <b>%d</b> 条</span><span>反证 <b>%d</b> 条</span></div>%s</article>' % (
                issue_id, allegation, nsup, ncon, miss_html))
    issues_html = "".join(issue_cards) if issue_cards else '<p class="note">scope 中未定义待验证事项。</p>'

    kpis = (
        '<div class="kpi"><div class="v">%d</div><div class="l">登记原始文件</div></div>'
        '<div class="kpi"><div class="v">%d</div><div class="l">时间线事件</div></div>'
        '<div class="kpi"><div class="v">%d</div><div class="l">待验证事项</div></div>'
        '<div class="kpi"><div class="v">%d</div><div class="l">越界行（已隔离）</div></div>'
    ) % (len(inventory), len(timeline), len(matrix), len(excluded))

    # timeline summary
    tl_note = "时间线共 <b>%d</b> 条事件" % len(timeline)
    if timeline:
        first = min((t.get("timestamp", "") for t in timeline if t.get("timestamp")), default="")
        last = max((t.get("timestamp", "") for t in timeline if t.get("timestamp")), default="")
        if first and last:
            tl_note += "，覆盖 %s ~ %s" % (first[:10], last[:10])
    tl_note += "。"

    # next steps
    next_html = ('<div class="note" style="border-left:4px solid var(--brand)"><b>下一步（必须由有权人员完成）</b><br>'
                 '1. 回到候选记录上下文，逐条核验支持证据与反证；<br>'
                 '2. 补齐缺失证据（访谈、门禁、资金流水等），并寻找替代表述；<br>'
                 '3. 按 <code>interview_plan.csv</code> 安排访谈，<code>case_memo_template.md</code> 由负责人填写。</div>')

    links = [
        ("evidence_inventory.jsonl", "登记的全部原始文件（含哈希）"),
        ("timeline.csv", "时间线事件"),
        ("evidence_matrix.csv", "事项 × 证据矩阵"),
        ("hypothesis_register.csv", "假设与反证登记"),
        ("interview_plan.csv", "访谈计划"),
        ("run_manifest.json", "运行记录（含授权范围与哈希）"),
    ]
    links_html = "".join('<a href="%s"><span class="lk-name">%s</span><span class="lk-desc">%s</span></a>' % (h, h, d) for h, d in links)

    warn_html = ""
    if warnings:
        warn_html = '<div class="note">数据质量提醒：%s</div>' % escape("；".join(str(w) for w in warnings[:4]))

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>调查工作空间全景</title><style>%s</style></head><body>
<div class="wrap">
  <div class="masthead"><div class="seal">✓</div><div>
    <h1>调查工作空间全景<span class="tag">已授权</span></h1>
    <div class="sub">investigation-assistant-v2 v%s · 案件 %s · %s · 用时 %s</div></div></div>
  <div class="verdict"><div class="lbl">工作空间概况</div><p>%s</p></div>
  <h2 class="sec">授权与范围</h2>
  <div class="scope">%s</div>
  <h2 class="sec">证据与覆盖</h2>
  <div class="kpis">%s</div>
  <div class="note">%s</div>
  %s
  <h2 class="sec">待验证事项 · 证据矩阵</h2>
  %s
  %s
  <h2 class="sec">详细报告</h2>
  <div class="links">%s</div>
  <div class="disclaimer"><b>业务定位</b>：本工作空间为<strong>证据整理</strong>，不替代专业调查/法律判断。用户指控与关键词命中均为<strong>待验证线索</strong>，不是事实认定。<strong>未命中不代表事项未发生</strong>；最终责任判断必须由有资质人员做出。</div>
  <div class="foot">由 investigation-assistant-v2 v%s 自动生成 · 离线可看 · 无外部依赖</div>
</div></body></html>
""" % (
        DASHBOARD_CSS, version, case_id, date_str, duration_str,
        statement, scope_html, kpis, tl_note, warn_html, issues_html, next_html, links_html, version,
    )
    (output_dir / "dashboard.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        raise SystemExit(2)
