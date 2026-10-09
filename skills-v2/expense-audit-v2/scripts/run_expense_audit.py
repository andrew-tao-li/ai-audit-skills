#!/usr/bin/env python3
"""Offline, deterministic expense red-flag scanner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "0.2.14"
SKILL = "expense-audit-v2"

# 显示层的中文审计术语（finding_type 英文 key、风险优先级、证据强度 → 中文）
FINDING_TYPE_ZH = {
    "exact-duplicate-invoice": "发票号重复", "exact-duplicate-employee-date-amount": "同员工同日同金额",
    "near-duplicate": "金额近似", "policy-threshold": "超制度上限", "split-expense": "拆单报销",
    "weekend-signal": "周末消费", "holiday-signal": "节假日消费", "robust-outlier": "异常高额",
    "self-approval": "自审自批", "cross-employee-invoice": "发票跨人复用", "submit-before-expense": "提交早于消费",
    "future-date": "未来日期", "missing-expense-type": "缺费用类型", "sequential-invoice": "发票连号",
    "invoice-format-anomaly": "发票格式异常", "large-amount-low-level-approval": "大额低层级审批",
    "space-time-conflict": "时空冲突", "cross-period": "跨期入账", "high-frequency-small-amount": "高频小额",
    "resubmit-after-rejection-amount-increase": "撤回/拒绝后重提且金额增加",  # v0.2.8
    # v0.2.13：以下三条均为**可选**（默认关闭）
    "split-expense-cross-merchant": "跨商户拆单",
    "large-amount": "绝对大额",
    "vendor-concentration": "商户集中度",
    # v0.2.9：出差交叉核验（需提供 --travel-requests / --attendance）
    "expense-without-travel-request": "差旅报销无对应出差申请",
    "office-swipe-on-offsite-claim": "报销称外地但当天有公司打卡",
    "attendance-city-mismatch": "打卡地点与出差城市不一致",
}
PRIORITY_ZH = {"critical": "严重", "high": "高", "medium": "中", "low": "低"}
STRENGTH_ZH = {"strong": "强", "moderate": "中", "weak": "弱"}

ALIASES = {
    "expense_id": ["expense_id", "id", "claim_id", "report_id", "单据号", "报销单号", "费用编号"],
    "employee_id": ["employee_id", "emp_id", "employee", "staff_id", "员工编号", "工号", "员工"],
    "employee_name": ["employee_name", "emp_name", "员工姓名", "姓名"],
    "department": ["department", "dept", "部门"],
    "expense_type": ["expense_type", "category", "type", "费用类型", "费用类别", "报销类型"],
    "expense_date": ["expense_date", "date", "transaction_date", "发生日期", "费用日期", "报销日期"],
    "submit_date": ["submit_date", "submission_date", "提交日期"],
    "amount": ["amount", "expense_amount", "claim_amount", "金额", "报销金额", "费用金额"],
    "currency": ["currency", "币种", "货币"],
    "vendor_name": ["vendor_name", "vendor", "merchant", "supplier", "商户", "商家", "供应商"],
    "invoice_number": ["invoice_number", "invoice_no", "invoice", "发票号", "发票号码"],
    "invoice_date": ["invoice_date", "发票日期"],
    "project_code": ["project_code", "project", "项目编号", "项目代码"],
    "approver": ["approver", "approved_by", "审批人"],
    "payment_date": ["payment_date", "付款日期", "支付日期"],
    "business_purpose": ["business_purpose", "purpose", "description", "事由", "用途", "业务目的"],
    "origin_city": ["origin_city", "from_city", "departure_city", "出发城市", "出发地"],
    "dest_city": ["dest_city", "destination_city", "to_city", "arrival_city", "目的城市", "目的地", "到达城市"],
    # v0.2.8：审批/单据状态（真实台账几乎都有；不配置 status_filter 时完全不影响分析）
    "status": ["status", "approval_status", "approval_state", "state", "状态", "审批状态", "单据状态", "报销状态", "流程状态", "审批结果"],
}
CORE_FIELDS = ("expense_id", "employee_id", "amount", "expense_date")
OUTPUT_FIELDS = tuple(ALIASES.keys())
# v0.2.13：白名单可匹配的字段（CSV 列名）；空列 = 通配。另支持 amount_max（金额上限）。
ALLOWLIST_FIELDS = ("expense_id", "employee_id", "employee_name", "vendor_name", "invoice_number", "expense_type")


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def norm_header(value: Any) -> str:
    return re.sub(r"[\s_\-./\\]+", "", norm_text(value).lower())


def match_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", norm_text(value).lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_amount(value: Any) -> Optional[float]:
    text = norm_text(value)
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.+-]", "", text.replace(",", ""))
    try:
        number = float(cleaned)
        return -number if negative else number
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = norm_text(value)
    if not text:
        return None
    text = re.split(r"[T\s]+", text.strip(), maxsplit=1)[0]
    # v0.2.13：中文日期「2026年10月9日」（可跟时间/后缀）——真实台账里很常见，
    # 以前认不出来会被当成坏行，导致这一天相关的规则全部失联。
    m = re.match(r"^(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def read_table(path: Path, sheet: Optional[str]) -> Tuple[List[str], List[Dict[str, Any]], Optional[str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = [norm_text(h) for h in (reader.fieldnames or [])]
            rows = []
            for row_number, raw in enumerate(reader, start=2):
                row = {norm_text(k): v for k, v in raw.items() if k is not None}
                row["_source_row"] = row_number
                row["_source_sheet"] = None
                rows.append(row)
            return headers, rows, None
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("读取 XLSX 需要 openpyxl；请离线安装或另存为 UTF-8 CSV") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        if sheet and sheet not in workbook.sheetnames:
            raise ValueError("找不到工作表：%s；可用工作表：%s" % (sheet, ", ".join(workbook.sheetnames)))
        worksheet = workbook[sheet] if sheet else workbook[workbook.sheetnames[0]]
        values = worksheet.iter_rows(values_only=True)
        first = next(values, None)
        if first is None:
            return [], [], worksheet.title
        headers = [norm_text(v) for v in first]
        rows = []
        for row_number, values_row in enumerate(values, start=2):
            row = {headers[index]: value for index, value in enumerate(values_row) if index < len(headers)}
            row["_source_row"] = row_number
            row["_source_sheet"] = worksheet.title
            rows.append(row)
        workbook.close()
        return headers, rows, worksheet.title
    raise ValueError("仅支持 .csv 和 .xlsx 输入")


# v0.2.0: policy.json 合法键清单（白名单），未知键会被拒绝并提示
POLICY_KEYS = frozenset({
    "policy_version", "default_currency",
    "limits", "approval_thresholds",
    "near_duplicate_window_days", "near_duplicate_amount_tolerance",
    "split_window_days", "weekend_check",
    "outlier_min_group_size", "outlier_robust_z",
    # v0.2.0 新增配置
    "holidays",
    "large_amount_threshold", "low_level_approver_keywords",
    "as_of_date",  # v0.2.0: future-date 基准日
    "cross_period_months",  # v0.2.1: 跨期入账阈值（月）
    "high_frequency_window_days", "high_frequency_min_count", "high_frequency_max_amount",  # v0.2.1: 高频小额
    # v0.2.8 新增（**全部可选**；不配置 = 与旧版行为完全一致）
    "status_filter",          # 只分析/排除指定审批状态：{"include": [...], "exclude": [...]}
    "resubmit_window_days",   # 「撤回/拒绝后重提且金额增加」的关联窗口（天），默认 90
    "amount_columns",         # 多列金额求和（台账没有单一金额列、金额分散在多列时使用）
    "travel_cross_check",     # v0.2.9：出差交叉核验（报销 × 出差申请 × 打卡；不配置=完全不启用）
    # v0.2.13 新增（**全部可选、默认关闭**；不配置 = 与旧版行为完全一致）
    "split_cross_merchant",            # 跨商户拆单（配合 approval_thresholds / split_window_days）
    "large_amount_check",              # 绝对大额（配合 large_amount_threshold）
    "vendor_concentration_check",      # 商户集中度
    "vendor_concentration_min_count",  # 商户集中度：最少笔数，默认 5
    "vendor_concentration_share",      # 商户集中度：占比阈值，默认 0.6
    "vendor_concentration_scope",      # 商户集中度：employee（默认）或 department
})

# v0.2.9：出差申请单字段别名（辅助表，可选）
TRAVEL_REQUEST_ALIASES = {
    "employee_id": ["employee_id", "emp_id", "employee", "staff_id", "工号", "员工编号", "员工", "姓名", "name"],
    "travel_start": ["travel_start", "start_date", "begin_date", "出差开始日期", "开始日期", "出发日期", "出差日期"],
    "travel_end": ["travel_end", "end_date", "finish_date", "出差结束日期", "结束日期", "返回日期"],
    "travel_dest_city": ["travel_dest_city", "dest_city", "destination", "city", "目的城市", "目的地", "出差城市", "到达城市"],
    "transport": ["transport", "vehicle", "交通方式", "交通工具"],
    "estimated_amount": ["estimated_amount", "budget", "预计费用", "预算金额"],
}

# v0.2.9：打卡记录字段别名（辅助表，可选）
ATTENDANCE_ALIASES = {
    "employee_id": ["employee_id", "emp_id", "employee", "staff_id", "工号", "员工编号", "员工", "姓名", "name"],
    "attendance_date": ["attendance_date", "date", "check_date", "打卡日期", "日期", "考勤日期"],
    "attendance_location": ["attendance_location", "location", "address", "place", "打卡地点", "打卡地址", "地点", "地址", "定位地址"],
    "is_office": ["is_office", "in_office", "office_flag", "是否在公司", "在公司", "打卡类型", "考勤类型", "外勤"],
    "lat": ["lat", "latitude", "纬度", "纬度(lat)"],
    "lon": ["lon", "lng", "longitude", "经度", "经度(lon)"],
}


def validate_policy(policy: Dict[str, Any]) -> None:
    """v0.2.0: 拒绝未知 policy 键，避免静默忽略用户配置"""
    unknown = set(policy.keys()) - POLICY_KEYS
    if unknown:
        suggestions = []
        for key in unknown:
            similar = [k for k in POLICY_KEYS if key.lower() in k.lower() or k.lower() in key.lower()]
            if similar:
                suggestions.append("%s（是否想写 %s？）" % (key, " 或 ".join(similar[:2])))
        msg = "policy.json 包含未知配置键：%s。" % ", ".join(sorted(unknown))
        if suggestions:
            msg += " 提示：" + "; ".join(suggestions) + "。"
        msg += " 合法键清单：%s" % ", ".join(sorted(POLICY_KEYS))
        raise ValueError(msg)


def load_json(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("JSON 配置顶层必须是对象")
    return value


def resolve_mapping(headers: Sequence[str], explicit: Dict[str, Any], allow_missing_amount: bool = False) -> Tuple[Dict[str, str], List[str]]:
    by_normalized = defaultdict(list)
    for header in headers:
        by_normalized[norm_header(header)].append(header)
    mapping: Dict[str, str] = {}
    warnings: List[str] = []
    for canonical in OUTPUT_FIELDS:
        if canonical in explicit:
            source = norm_text(explicit[canonical])
            if source not in headers:
                raise ValueError("字段映射 %s -> %s 不存在于输入表" % (canonical, source))
            mapping[canonical] = source
            continue
        matches: List[str] = []
        for alias in ALIASES[canonical]:
            matches.extend(by_normalized.get(norm_header(alias), []))
        matches = list(dict.fromkeys(matches))
        if len(matches) == 1:
            mapping[canonical] = matches[0]
        elif len(matches) > 1:
            warnings.append("字段 %s 存在多个候选：%s" % (canonical, ", ".join(matches)))
    missing = [field for field in CORE_FIELDS if field not in mapping]
    # v0.2.8：若配置了 amount_columns（多列金额求和），则允许没有单一 amount 列
    if allow_missing_amount:
        missing = [field for field in missing if field != "amount"]
    # v0.2.13：报销人身份允许用「姓名」——没有 employee_id 但有 employee_name 时，视为满足
    #（真实台账里小公司常常只有姓名没有工号；见审计师反馈第 4 条）
    if "employee_id" in missing and "employee_name" in mapping:
        missing = [field for field in missing if field != "employee_id"]
    if missing:
        raise ValueError("缺少核心字段映射：%s。请使用 --field-map 提供明确映射" % ", ".join(missing))
    return mapping, warnings


def normalize_rows(
    source_rows: Sequence[Dict[str, Any]], mapping: Dict[str, str], default_currency: str,
    amount_columns: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, int]]:
    clean: List[Dict[str, Any]] = []
    bad: List[Dict[str, Any]] = []
    changes = {"trimmed_or_normalized_text_values": 0, "parsed_amount_values": 0, "parsed_date_values": 0}
    for source in source_rows:
        row: Dict[str, Any] = {"_source_row": source["_source_row"], "_source_sheet": source["_source_sheet"]}
        for canonical in OUTPUT_FIELDS:
            raw = source.get(mapping.get(canonical, ""), "")
            normalized = norm_text(raw)
            row[canonical] = normalized
            if normalized != ("" if raw is None else str(raw).strip()):
                changes["trimmed_or_normalized_text_values"] += 1
        # v0.2.13：只有姓名、没有工号时，用姓名充当 employee_id（保证下游按人分组的规则仍正确）
        if not row.get("employee_id") and row.get("employee_name"):
            row["employee_id"] = row["employee_name"]
        # v0.2.8：多列金额求和——仅当配置了 amount_columns 且该行没有单一金额列时生效
        if amount_columns and not norm_text(row.get("amount")):
            _total, _found = 0.0, False
            for _col in amount_columns:
                _v = parse_amount(source.get(_col))
                if _v is not None and math.isfinite(_v):
                    _total += _v
                    _found = True
            if _found:
                row["amount"] = repr(round(_total, 6))
        amount = parse_amount(row["amount"])
        expense_date = parse_date(row["expense_date"])
        reasons = []
        if not row["expense_id"]:
            reasons.append("expense_id 为空")
        if not row["employee_id"]:
            reasons.append("employee_id 为空")
        if amount is None or not math.isfinite(amount):
            reasons.append("amount 无法解析为有限数值")
        if expense_date is None:
            reasons.append("expense_date 无法解析")
        if reasons:
            bad.append({"source_row": source["_source_row"], "reasons": "；".join(reasons), "raw_record": json.dumps({k: source.get(k) for k in mapping.values()}, ensure_ascii=False, default=str)})
            continue
        row["amount"] = round(float(amount), 6)
        row["expense_date"] = expense_date
        row["currency"] = (row["currency"] or default_currency).upper()
        for date_field in ("submit_date", "invoice_date", "payment_date"):
            if row[date_field]:
                parsed = parse_date(row[date_field])
                row[date_field] = parsed or row[date_field]
        changes["parsed_amount_values"] += 1
        changes["parsed_date_values"] += 1
        clean.append(row)
    return clean, bad, changes


def priority(score: int) -> str:
    if score >= 6:
        return "critical"
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


class Allowlist:
    """v0.2.13：用户自备的白名单——显式、可审计、**绝不静默丢弃**。

    用途：把"已知无风险"的行（小额固定支出、上期已核实单据）从告警里排除。
    被压制的内容会**完整写入** `suppressed_findings.csv`，并在 manifest / 数据质量报告中计数。
    未提供白名单文件时，本类不参与任何逻辑（与旧版完全一致）。
    """

    def __init__(self, entries: List[Dict[str, str]]):
        self.entries = entries

    @classmethod
    def load(cls, path: Optional[Path]) -> Optional["Allowlist"]:
        if path is None:
            return None
        if not path.is_file():
            raise FileNotFoundError("白名单文件不存在：%s" % path)
        entries: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                entry = {norm_text(k): norm_text(v) for k, v in raw.items() if k is not None}
                entry = {k: v for k, v in entry.items() if v}
                if any(entry.get(f) for f in ALLOWLIST_FIELDS) or entry.get("amount_max"):
                    entries.append(entry)
        return cls(entries)

    def match(self, record: Dict[str, Any]) -> Optional[Dict[str, str]]:
        for entry in self.entries:
            ok = True
            for field in ALLOWLIST_FIELDS:
                want = entry.get(field)
                if want and match_key(want) != match_key(record.get(field)):
                    ok = False
                    break
            if not ok:
                continue
            amax = entry.get("amount_max")
            if amax:
                value = parse_amount(record.get("amount"))
                limit = parse_amount(amax)
                if value is None or limit is None or value > limit:
                    continue
            return entry
        return None

    def match_all(self, records: Sequence[Dict[str, Any]]) -> Optional[List[Dict[str, str]]]:
        """只有当一条 finding 的**每一行**都命中白名单时才返回命中条目（否则返回 None）。"""
        reasons: List[Dict[str, str]] = []
        for record in records:
            entry = self.match(record)
            if entry is None:
                return None
            reasons.append(entry)
        return reasons


class ResultBuilder:
    def __init__(self, source_file: str, source_hash: str, policy: Optional[Dict[str, Any]] = None,
                 allowlist: Optional["Allowlist"] = None):
        self.source_file = source_file
        self.source_hash = "sha256:" + source_hash
        self.evidence: List[Dict[str, Any]] = []
        self.findings: List[Dict[str, Any]] = []
        self.suppressed: List[Dict[str, Any]] = []   # v0.2.13：被白名单压制的告警（留痕，不丢弃）
        self._evidence_cache: Dict[Tuple[int, str], str] = {}
        self.policy = policy or {}
        self.allowlist = allowlist

    def evidence_for(self, record: Dict[str, Any], field: str) -> str:
        key = (int(record["_source_row"]), field)
        if key in self._evidence_cache:
            return self._evidence_cache[key]
        evidence_id = "EV-%06d" % (len(self.evidence) + 1)
        item = {
            "evidence_id": evidence_id,
            "source_file": self.source_file,
            "source_hash": self.source_hash,
            "sheet": record.get("_source_sheet"),
            "row": record["_source_row"],
            "field": field,
            "value": record.get(field, ""),
            "extraction_method": "normalized",
            "confidence": 1.0,
        }
        self.evidence.append(item)
        self._evidence_cache[key] = evidence_id
        return evidence_id

    def add(
        self,
        finding_type: str,
        title: str,
        score: int,
        strength: str,
        records: Sequence[Dict[str, Any]],
        evidence_fields: Sequence[str],
        facts: Sequence[str],
        inferences: Sequence[str],
        questions: Sequence[str],
        next_steps: Sequence[str],
        factors: Sequence[Dict[str, Any]],
    ) -> None:
        # v0.2.13：命中用户白名单的 finding 不进入 findings，但**完整留痕**到 suppressed（不静默丢弃）
        if self.allowlist is not None:
            matched = self.allowlist.match_all(records)
            if matched is not None:
                amounts = [a for a in (parse_amount(r.get("amount")) for r in records) if a is not None]
                self.suppressed.append({
                    "finding_type": finding_type,
                    "title": title,
                    "rows": len(records),
                    "expense_ids": "|".join(norm_text(r.get("expense_id")) for r in records),
                    "employees": "|".join(sorted({norm_text(r.get("employee_id")) for r in records if r.get("employee_id")})),
                    "vendors": "|".join(sorted({norm_text(r.get("vendor_name")) for r in records if r.get("vendor_name")})),
                    "max_amount": max(amounts) if amounts else "",
                    "suppressed_reason": "|".join(sorted({str(m.get("reason", "")) for m in matched if m.get("reason")})),
                })
                return
        refs = []
        amounts = []
        for record in records:
            for field in evidence_fields:
                refs.append(self.evidence_for(record, field))
            amount = parse_amount(record.get("amount"))
            if amount is not None:
                amounts.append(amount)
        max_amount = max(amounts) if amounts else None
        entities = []
        seen = set()
        for record in records:
            for entity_type, field in (("employee", "employee_id"), ("vendor", "vendor_name")):
                value = record.get(field)
                key = (entity_type, value)
                if value and key not in seen:
                    entities.append({"type": entity_type, "id": value})
                    seen.add(key)
        # v0.2.0: 按金额×置信度调整 score
        adjusted_score = _adjust_priority_by_amount(score, strength, max_amount, self.policy)
        # v0.2.0: 四层标记——把每条 finding 明确归类
        # - facts: 数据直接命中的事实
        # - inferences: 规则推断（非直接事实）
        # - hypotheses: 待验证的假设
        # - 判定责任属于人工，不在脚本
        finding_entry = {
            "finding_id": "EXP-%06d" % (len(self.findings) + 1),
            "skill": SKILL,
            "skill_version": VERSION,
            "finding_type": finding_type,
            "title": title,
            "risk_priority": priority(adjusted_score),
            "evidence_strength": strength,
            "risk_score": adjusted_score,
            "risk_score_base": score,
            "risk_factors": list(factors),
            "entities": entities,
            "facts": list(facts),
            "inferences": list(inferences),
            "hypotheses": [],  # 审计师/合规填写
            "open_questions": list(questions),
            "evidence_refs": list(dict.fromkeys(refs)),
            "recommended_next_steps": list(next_steps),
            "human_review_required": True,
            "judgment_layer": "线索层（待复核）",  # v0.2.0: 明确不写成"事实"或"判断"
            "max_amount": max_amount,
        }
        self.findings.append(finding_entry)


def group_records(rows: Sequence[Dict[str, Any]], fields: Sequence[str], require_nonempty: Sequence[str] = ()) -> Iterable[List[Dict[str, Any]]]:
    groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if any(not row.get(field) for field in require_nonempty):
            continue
        key = tuple(row.get(field) for field in fields)
        groups[key].append(row)
    return (group for group in groups.values() if len(group) > 1)


def _adjust_priority_by_amount(score: int, strength: str, amount: Optional[float], policy: Dict[str, Any]) -> int:
    """v0.2.0: 按金额×置信度重新调整 risk_score，用于最终 priority 决策
    - 大额强证据 → 升级（即使规则基础分低）
    - 小额弱证据 → 降级
    """
    if amount is None or amount <= 0:
        return score
    large_threshold = float(policy.get("large_amount_threshold", 5000))
    if amount >= large_threshold and strength == "strong":
        return max(score, 4)  # 大额+强证据，至少 medium 偏 high
    if amount < large_threshold / 10 and strength == "weak":
        return min(score, 2)  # 小额+弱证据，至少不升级到 critical
    return score


def apply_status_filter(rows: List[Dict[str, Any]], policy: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """v0.2.8：按审批状态筛选（**可选**）。

    - 不配置 `status_filter` → 原样返回，与旧版行为完全一致。
    - 配置后：不符合条件的行不参与分析，但会单独输出到 `excluded_by_status.csv`，
      **绝不静默丢弃**；状态为空的行一律保留（不猜、不藏）。
    """
    cfg = policy.get("status_filter")
    if not isinstance(cfg, dict):
        return rows, []
    include = {norm_text(x).lower() for x in (cfg.get("include") or []) if norm_text(x)}
    exclude = {norm_text(x).lower() for x in (cfg.get("exclude") or []) if norm_text(x)}
    if not include and not exclude:
        return rows, []
    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for row in rows:
        status = norm_text(row.get("status")).lower()
        if not status:                      # 状态未知 → 保留，不因缺字段而被排除
            kept.append(row)
        elif include:
            (kept if status in include else dropped).append(row)
        elif status in exclude:
            dropped.append(row)
        else:
            kept.append(row)
    return kept, dropped


def _rule_resubmit_after_rejection(rows, excluded, policy, builder) -> None:
    """v0.2.8：同一员工 + 同一费用类型 + 同一商户——先被撤回/拒绝，之后重提且金额增加。

    只在配置了 `status_filter` 且存在被排除行时触发；`resubmit_window_days: 0` 可关闭。
    """
    window = policy.get("resubmit_window_days", 90)
    try:
        window = int(window)
    except (TypeError, ValueError):
        window = 90
    if window <= 0 or not excluded:
        return

    def _day(row):
        value = row.get("expense_date") or row.get("submit_date")
        try:
            from datetime import date as _date
            return _date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            return None

    approved: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        approved[(row.get("employee_id"), row.get("expense_type"), row.get("vendor_name"))].append(row)

    for rejected in excluded:
        key = (rejected.get("employee_id"), rejected.get("expense_type"), rejected.get("vendor_name"))
        r_amount, r_day = rejected.get("amount"), _day(rejected)
        if not isinstance(r_amount, (int, float)) or r_day is None:
            continue
        for later in approved.get(key, []):
            l_amount, l_day = later.get("amount"), _day(later)
            if not isinstance(l_amount, (int, float)) or l_day is None:
                continue
            if l_amount <= r_amount:
                continue
            if abs((l_day - r_day).days) > window:
                continue
            builder.add(
                "resubmit-after-rejection-amount-increase",
                "撤回/拒绝后重提，且金额增加", 3, "moderate",
                [rejected, later],
                ("expense_id", "employee_id", "expense_type", "vendor_name", "amount", "status"),
                ["同一员工、同一费用类型、同一商户：先有 1 条「%s」记录（%.2f），%d 天后又有 1 条「%s」记录（%.2f），金额增加 %.2f"
                 % (rejected.get("status") or "被拒/撤回", r_amount, abs((l_day - r_day).days),
                    later.get("status") or "通过", l_amount, l_amount - r_amount)],
                ["可能是修正后重提（正常），也可能是先试小额、通过后再加码"],
                ["核对两次提交的原始凭证与审批意见，确认金额变化的业务原因"],
                ["调取该申请单的完整审批历史与附件"],
                [{"factor": "resubmit_after_rejection_amount_increase", "points": 3}],
            )


TRAVEL_KEYWORDS_DEFAULT = ["差旅", "出差", "住宿", "机票", "火车", "高铁", "市内交通", "交通费", "打车", "补贴"]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _to_float(value: Any) -> Optional[float]:
    try:
        f = float(str(value).strip())
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _as_day(value: Any):
    from datetime import date as _date
    try:
        return _date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def office_verdict(row: Dict[str, Any], cfg: Dict[str, Any]) -> Optional[bool]:
    """三层判定「是否在公司」：① 显式布尔 ② 经纬度+半径 ③ 地点文本。三层都不成立 → None（不猜）。"""
    raw = norm_text(row.get("is_office")).lower()
    if raw:
        if raw in ("是", "y", "yes", "true", "1", "在公司", "公司", "内勤", "office"):
            return True
        if raw in ("否", "n", "no", "false", "0", "不在公司", "外勤", "外出", "field"):
            return False
    lat, lon = _to_float(row.get("lat")), _to_float(row.get("lon"))
    if lat is not None and lon is not None and (cfg.get("company_locations") or []):
        nearest = None
        for loc in cfg.get("company_locations") or []:
            llat, llon = _to_float(loc.get("lat")), _to_float(loc.get("lon"))
            if llat is None or llon is None:
                continue
            dist = _haversine_m(lat, lon, llat, llon)
            if dist <= (_to_float(loc.get("radius_m")) or 1000.0):
                return True
            nearest = dist if nearest is None else min(nearest, dist)
        if nearest is not None:
            return False
    text = norm_text(row.get("attendance_location"))
    keywords = [norm_text(k) for k in (cfg.get("company_location_keywords") or []) if norm_text(k)]
    if text and keywords:
        return any(k in text for k in keywords)
    return None


def read_aux_table(path: Path, aliases: Dict[str, List[str]], sheet: Optional[str] = None):
    """读辅助表（出差申请 / 打卡记录），按别名解析列。返回 (rows, mapping)。"""
    headers, source_rows, _ = read_table(path, sheet)
    by_norm: Dict[str, List[str]] = defaultdict(list)
    for header in headers:
        by_norm[norm_header(header)].append(header)
    mapping: Dict[str, str] = {}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            matches = by_norm.get(norm_header(alias), [])
            if matches:
                mapping[canonical] = matches[0]
                break
    rows = []
    for source in source_rows:
        rows.append({canonical: norm_text(source.get(col, "")) for canonical, col in mapping.items()})
    return rows, mapping


def run_travel_cross_check(analyzable, travel_rows, attendance_rows, policy, builder,
                           travel_mapping, attendance_mapping) -> List[str]:
    """v0.2.9：报销 × 出差申请 × 打卡 的交叉核验。

    只在提供了对应辅助数据时才启用；不提供则一行也不产生（零回归）。
    所有结论都是**线索**，不是认定——尤其「当天有公司打卡」不等于「人没出差」（可能代报销）。
    """
    cfg = policy.get("travel_cross_check") or {}
    notes: List[str] = []
    if not travel_rows and not attendance_rows:
        return notes

    travel_types = [norm_text(t) for t in (cfg.get("travel_types") or TRAVEL_KEYWORDS_DEFAULT) if norm_text(t)]
    company_cities = [norm_text(c) for c in (cfg.get("company_cities") or []) if norm_text(c)]
    tolerance = int(cfg.get("date_tolerance_days", 1) or 0)

    def travel_like(expense) -> bool:
        et = norm_text(expense.get("expense_type"))
        if et and any(t in et for t in travel_types):
            return True
        dest = norm_text(expense.get("dest_city"))
        return bool(dest and dest not in company_cities)

    # 出差申请索引：员工 → [(start, end, dest, raw)]
    trips: Dict[str, List[Any]] = defaultdict(list)
    for t in travel_rows:
        emp = norm_text(t.get("employee_id"))
        start, end = _as_day(t.get("travel_start")), _as_day(t.get("travel_end"))
        if not emp or not start:
            continue
        trips[emp].append((start, end or start, norm_text(t.get("travel_dest_city"))))

    def covered(emp: str, day) -> Optional[Any]:
        for start, end, dest in trips.get(emp, []):
            lo = start - timedelta(days=tolerance)
            hi = end + timedelta(days=tolerance)
            if lo <= day <= hi:
                return (start, end, dest)
        return None

    # 打卡索引：(员工, 日期) → [rows]
    swipes: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for a in attendance_rows:
        emp = norm_text(a.get("employee_id"))
        day = _as_day(a.get("attendance_date"))
        if emp and day:
            swipes[(emp, day)].append(a)

    # 城市词表（用于「打卡地与出差地不一致」）：公司城市 + 所有出差目的城市
    vocab = list(dict.fromkeys(company_cities + [t[2] for ts in trips.values() for t in ts if t[2]]))

    def city_in(text: str) -> Optional[str]:
        for city in vocab:
            if city and city in text:
                return city
        return None

    # A. 差旅报销未找到对应出差申请
    if travel_rows:
        for e in analyzable:
            if not travel_like(e):
                continue
            emp, day = norm_text(e.get("employee_id")), _as_day(e.get("expense_date"))
            if not emp or day is None:
                continue
            if covered(emp, day) is None:
                builder.add("expense-without-travel-request", "差旅报销未找到对应出差申请", 3, "moderate", [e],
                            ("expense_id", "employee_id", "expense_date", "expense_type", "amount"),
                            ["该笔差旅报销的日期不在该员工的任何出差申请区间内（已按 ±%d 天容差比对）" % tolerance],
                            ["可能是未走 OA 的出差、代他人报销，或出差申请未录入"],
                            ["是否为代报销？实际出差人是谁？是否走了线下审批？"],
                            ["调取出差申请、审批邮件/聊天记录与行程凭证"],
                            [{"factor": "expense_without_travel_request", "points": 3}])

    # B / D. 报销称外地，但当天有公司打卡 / 打卡地与出差地不一致
    if attendance_rows:
        for e in analyzable:
            if not travel_like(e):
                continue
            emp, day = norm_text(e.get("employee_id")), _as_day(e.get("expense_date"))
            dest = norm_text(e.get("dest_city"))
            if not emp or day is None:
                continue
            day_rows = swipes.get((emp, day), [])
            if not day_rows:
                continue
            # B：当天在公司打卡（仅在报销是"外地"时才有意义）
            if dest and dest not in company_cities:
                if any(office_verdict(r, cfg) is True for r in day_rows):
                    builder.add("office-swipe-on-offsite-claim", "报销称外地，但当天有公司打卡", 3, "moderate", [e],
                                ("expense_id", "employee_id", "expense_date", "dest_city"),
                                ["该笔报销目的城市为「%s」，但当天（%s）该员工有**公司打卡**记录" % (dest, day.isoformat())],
                                ["当天有公司打卡 ≠ 本人没出差：可能是同事代交、代报销，或出差前后到岗"],
                                ["请核实**实际出差人**，以及是否为代他人报销"],
                                ["比对出差申请的实际出差人、行程单与同行人员"],
                                [{"factor": "office_swipe_on_offsite_claim", "points": 3}])
            # D：打卡地点与出差目的城市不一致（地点能识别出城市时才判，否则跳过）
            if bool(cfg.get("flag_city_mismatch", True)) and dest:
                for r in day_rows:
                    seen = city_in(norm_text(r.get("attendance_location")))
                    if seen and seen != dest and seen not in company_cities:
                        builder.add("attendance-city-mismatch", "打卡地点与出差目的城市不一致", 2, "weak", [e],
                                    ("expense_id", "employee_id", "expense_date", "dest_city"),
                                    ["报销目的城市为「%s」，但当天打卡地点显示在「%s」" % (dest, seen)],
                                    ["可能行程有变、中转停留，或地点解析偏差"],
                                    ["是否有中转、改道或多地行程？以行程单为准"],
                                    ["核对该日行程单与改签/中转记录"],
                                    [{"factor": "attendance_city_mismatch", "points": 2}])
                        break

    # C. 出差期间应有打卡却无记录（默认关闭；仅当公司政策如此时打开）
    if attendance_rows and travel_rows and bool(cfg.get("require_swipe_during_travel", False)):
        min_swipes = int(cfg.get("min_swipes_per_travel_day", 2) or 2)
        for emp, ts in trips.items():
            for start, end, dest in ts:
                cursor = start
                while cursor <= end:
                    if not swipes.get((emp, cursor)):
                        notes.append("出差期间无打卡：%s %s（政策要求每日≥%d 次）" % (emp, cursor.isoformat(), min_swipes))
                        break
                    cursor += timedelta(days=1)

    return notes


def run_rules(rows: List[Dict[str, Any]], policy: Dict[str, Any], builder: ResultBuilder,
              status_excluded: Optional[List[Dict[str, Any]]] = None) -> Tuple[List[str], Dict[str, Any]]:
    skipped: List[str] = []
    exact_pairs = set()
    for group in group_records(rows, ("employee_id", "invoice_number", "currency", "amount"), ("invoice_number",)):
        ids = [r["expense_id"] for r in group]
        exact_pairs.update(frozenset((a, b)) for i, a in enumerate(ids) for b in ids[i + 1 :])
        builder.add("exact-duplicate-invoice", "发票号与金额重复，需核对是否重复报销", 4, "strong", group,
                    ("expense_id", "invoice_number", "amount"),
                    ["%d 条记录具有相同的非空发票号、币种和金额" % len(group)],
                    ["该组合构成可能重复报销的高优先级复核线索"],
                    ["是否为冲销、退款、作废后重提或发票拆分？"],
                    ["核对发票影像、报销状态和付款流水"],
                    [{"factor": "same_invoice_and_amount", "points": 4}])
    for group in group_records(rows, ("employee_id", "expense_date", "currency", "amount")):
        ids = [r["expense_id"] for r in group]
        exact_pairs.update(frozenset((a, b)) for i, a in enumerate(ids) for b in ids[i + 1 :])
        builder.add("exact-duplicate-employee-date-amount", "同员工同日同金额记录重复", 3, "moderate", group,
                    ("expense_id", "employee_id", "expense_date", "amount", "vendor_name"),
                    ["%d 条记录的员工、日期、币种和金额相同" % len(group)],
                    ["可能是重复提交，也可能是同日不同业务"],
                    ["商户、业务事由和原始凭证是否不同？"],
                    ["逐笔核对事由、商户、发票和审批流"],
                    [{"factor": "same_employee_date_amount", "points": 3}])

    near_days = int(policy.get("near_duplicate_window_days", 7))
    near_tolerance = float(policy.get("near_duplicate_amount_tolerance", 0.15))
    ordered = sorted(rows, key=lambda r: (r["employee_id"], r["expense_date"], r["expense_id"]))
    near_seen = set()
    near_records = {}  # expense_id -> row，收集所有近似重复对涉及的记录
    for index, left in enumerate(ordered):
        left_date = date.fromisoformat(left["expense_date"])
        for right in ordered[index + 1 :]:
            if right["employee_id"] != left["employee_id"]:
                if right["employee_id"] > left["employee_id"]:
                    break
                continue
            delta = abs((date.fromisoformat(right["expense_date"]) - left_date).days)
            if delta > near_days:
                continue
            pair = frozenset((left["expense_id"], right["expense_id"]))
            if pair in exact_pairs or pair in near_seen:
                continue
            if not match_key(left["vendor_name"]) or match_key(left["vendor_name"]) != match_key(right["vendor_name"]):
                continue
            if left["currency"] != right["currency"]:
                continue
            difference = abs(left["amount"] - right["amount"]) / max(abs(left["amount"]), abs(right["amount"]), 0.01)
            if difference <= near_tolerance:
                near_seen.add(pair)
                near_records[left["expense_id"]] = left
                near_records[right["expense_id"]] = right
    # 只有 ≥3 条记录构成近似重复簇才报（避免把"两笔相似"误判为高频拆分）
    if len(near_records) >= 3:
        records = list(near_records.values())
        builder.add("near-duplicate", "同员工同商户短期内多笔近似金额", 2, "moderate", records,
                    ("expense_id", "employee_id", "expense_date", "vendor_name", "amount", "invoice_number"),
                    ["%d 笔金额接近、集中在 %d 天内的报销记录" % (len(records), near_days)],
                    ["多笔金额接近、时间集中的报销，可能指向拆分报销或虚构业务"],
                    ["是否为同一次消费的拆分、月度订阅或正常高频小额采购？"],
                    ["对照发票影像、消费时间和支付流水"],
                    [{"factor": "near_duplicate", "points": 2, "count": len(records)}])

    limits = policy.get("limits", [])
    if not limits:
        skipped.append("policy-threshold：未提供 limits")
    for row in rows:
        for limit in limits:
            if limit.get("expense_type") and match_key(limit["expense_type"]) != match_key(row["expense_type"]):
                continue
            if limit.get("currency") and str(limit["currency"]).upper() != row["currency"]:
                continue
            maximum = parse_amount(limit.get("max_amount"))
            if maximum is not None and row["amount"] > maximum:
                over = row["amount"] - maximum
                builder.add("policy-threshold", "费用金额超过适用制度上限", 3, "strong", (row,),
                            ("expense_id", "expense_type", "amount", "currency"),
                            ["金额 %.2f %s 超过配置上限 %.2f %s" % (row["amount"], row["currency"], maximum, row["currency"])],
                            ["该记录触发用户提供的制度阈值 %s" % limit.get("rule_id", "未命名规则")],
                            ["是否存在例外审批、多人费用或可报销附加项目？"],
                            ["核对制度版本、例外审批和费用明细"],
                            [{"factor": "policy_threshold", "points": 3, "rule_id": limit.get("rule_id"), "over_amount": round(over, 2)}])

    thresholds = policy.get("approval_thresholds", [])
    if not thresholds:
        skipped.append("split-expense：未提供 approval_thresholds")
    split_days = int(policy.get("split_window_days", 0))
    for threshold in thresholds:
        amount_threshold = parse_amount(threshold.get("amount"))
        currency = str(threshold.get("currency", "")).upper()
        if amount_threshold is None:
            continue
        groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            if currency and row["currency"] != currency:
                continue
            groups[(row["employee_id"], match_key(row["vendor_name"]), row["currency"])].append(row)
        split_seen = set()
        for group in groups.values():
            group.sort(key=lambda r: r["expense_date"])
            for start, first in enumerate(group):
                end_date = date.fromisoformat(first["expense_date"])
                window = [r for r in group[start:] if (date.fromisoformat(r["expense_date"]) - end_date).days <= split_days]
                if len(window) < 2 or any(r["amount"] >= amount_threshold for r in window):
                    continue
                total = sum(r["amount"] for r in window)
                key = tuple(sorted(r["expense_id"] for r in window))
                if total > amount_threshold and key not in split_seen:
                    split_seen.add(key)
                    builder.add("split-expense", "短期多笔费用合计超过审批阈值", 3, "moderate", window,
                                ("expense_id", "employee_id", "expense_date", "vendor_name", "amount"),
                                ["%d 笔单笔低于 %.2f %s 的费用合计 %.2f %s" % (len(window), amount_threshold, window[0]["currency"], total, window[0]["currency"])],
                                ["该组合符合疑似拆单的配置条件"],
                                ["是否为独立业务、分期结算或不同费用承担人？"],
                                ["核对采购/服务内容、审批层级和原始支付时间"],
                                [{"factor": "split_expense", "points": 3, "rule_id": threshold.get("rule_id"), "window_days": split_days}])

    # v0.2.13：跨商户拆单（**可选，默认关闭**）——真实项目中存在员工在同一窗口内、在不同商户各刷一笔、
    # 每笔都低于审批阈值的情形。默认不启用 = 与旧版完全一致；只有 split_cross_merchant=true 才生效。
    if thresholds and policy.get("split_cross_merchant", False):
        for threshold in thresholds:
            amount_threshold = parse_amount(threshold.get("amount"))
            currency = str(threshold.get("currency", "")).upper()
            if amount_threshold is None:
                continue
            egroups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
            for row in rows:
                if currency and row["currency"] != currency:
                    continue
                egroups[(row["employee_id"], row["currency"])].append(row)
            cross_seen = set()
            for group in egroups.values():
                group.sort(key=lambda r: r["expense_date"])
                for start, first in enumerate(group):
                    end_date = date.fromisoformat(first["expense_date"])
                    window = [r for r in group[start:] if (date.fromisoformat(r["expense_date"]) - end_date).days <= split_days]
                    vendors = {match_key(r["vendor_name"]) for r in window if match_key(r["vendor_name"])}
                    # 必须「跨商户」（≥2 个不同商户），且每笔都低于阈值、合计超过阈值
                    if len(window) < 2 or len(vendors) < 2 or any(r["amount"] >= amount_threshold for r in window):
                        continue
                    total = sum(r["amount"] for r in window)
                    key = tuple(sorted(r["expense_id"] for r in window))
                    if total > amount_threshold and key not in cross_seen:
                        cross_seen.add(key)
                        builder.add("split-expense-cross-merchant", "同员工短期内跨商户多笔合计超过审批阈值（疑似拆单）", 3, "moderate", window,
                                    ("expense_id", "employee_id", "expense_date", "vendor_name", "amount"),
                                    ["%d 笔单笔低于 %.2f %s 的费用分布在 %d 个商户，合计 %.2f %s" % (len(window), amount_threshold, window[0]["currency"], len(vendors), total, window[0]["currency"])],
                                    ["该组合符合疑似拆单的配置条件（跨商户）"],
                                    ["是否为独立业务、不同费用承担人、分期结算，或正常的高频小额采购？"],
                                    ["核对采购/服务内容、审批层级和原始支付时间"],
                                    [{"factor": "split_expense_cross_merchant", "points": 3, "rule_id": threshold.get("rule_id"), "window_days": split_days}])

    if policy.get("weekend_check", False):
        # v0.2.0: 节假日列表支持（如 ["2026-10-01", "2026-10-02"]）
        holidays = set()
        for entry in policy.get("holidays", []):
            try:
                holidays.add(date.fromisoformat(entry).isoformat())
            except (ValueError, TypeError):
                pass
        for row in rows:
            exp_date_str = row["expense_date"]
            try:
                exp_date = date.fromisoformat(exp_date_str)
            except ValueError:
                continue
            is_weekend = exp_date.weekday() >= 5
            is_holiday = exp_date_str in holidays
            if is_weekend or is_holiday:
                kind = "法定节假日" if is_holiday else "周末"
                builder.add("weekend-signal" if is_weekend else "holiday-signal",
                            "费用发生在%s，需结合业务安排解释" % kind, 1, "weak", (row,),
                            ("expense_id", "expense_date", "business_purpose"),
                            ["费用日期 %s 为%s" % (exp_date_str, kind)],
                            ["这是弱风险信号，不能单独说明费用不真实"],
                            ["是否有值班、出差、客户现场或跨时区安排？"],
                            ["核对日程、出差审批和业务事由"],
                            [{"factor": "weekend" if is_weekend else "holiday", "points": 1}])
    else:
        skipped.append("weekend-signal/holiday-signal：weekend_check 未启用")

    min_group = int(policy.get("outlier_min_group_size", 5))
    z_threshold = float(policy.get("outlier_robust_z", 3.5))
    large_threshold = float(policy.get("large_amount_threshold", 5000))
    peer_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        peer_groups[(match_key(row["expense_type"]), row["currency"])].append(row)
    valid_groups = 0
    for key, group in peer_groups.items():
        if len(group) < min_group:
            continue
        values = [r["amount"] for r in group]
        median = statistics.median(values)
        mad = statistics.median([abs(value - median) for value in values])
        if mad == 0:
            continue
        valid_groups += 1
        for row in group:
            # 大额（≥ large_amount_threshold）交由 large-amount-low-level-approval / policy-threshold 等
            # 更具体的规则解释，robust-outlier 只负责"正常区间内的相对离群"，避免同一笔重复告警。
            if row["amount"] >= large_threshold:
                continue
            robust_z = 0.6745 * (row["amount"] - median) / mad
            if robust_z > z_threshold:
                builder.add("robust-outlier", "同类费用中的异常高额", 2, "moderate", (row,),
                            ("expense_id", "expense_type", "amount", "currency"),
                            ["该笔金额 %.2f 元，约为同类费用正常水平的约 %.1f 倍" % (row["amount"], row["amount"] / median)],
                            ["该记录在同类费用中显著偏高，仅用于确定复核优先级"],
                            ["是否存在人数、城市、天数或特殊业务场景差异？"],
                            ["补充数量、人数、期间等口径，核对原始单据"],
                            [{"factor": "robust_outlier", "points": 2}])
    if valid_groups == 0:
        skipped.append("robust-outlier：同类样本不足或样本金额高度一致，无法判断离群")

    # ============ v0.2.0 新增规则 ============

    # 规则：发票连号（sequential invoices）
    # 同一商户在短期内开具连续编号发票（3 张以上连号），可能指向"分拆报销"或"虚构业务"
    # 关键约束：连号发票必须在很短时间内（默认 3 天内）开出，否则只是正常的顺序开票（如月度办公采购）。
    sequential_window = int(policy.get("sequential_invoice_window_days", 3))
    invoice_index = {}  # {(vendor_match, currency): [(row, num, inv_raw)]}
    for row in rows:
        inv_raw = norm_text(row.get("invoice_number"))
        if not inv_raw:
            continue
        # 提取连续数字作为序号
        match = re.search(r"(\d{2,})", inv_raw)
        if not match:
            continue
        try:
            num = int(match.group(1))
        except ValueError:
            continue
        key = (match_key(row.get("vendor_name")), row.get("currency", ""))
        invoice_index.setdefault(key, []).append((row, num, inv_raw))
    for key, entries in invoice_index.items():
        entries.sort(key=lambda x: (x[1], x[0].get("expense_date", "")))
        i = 0
        while i <= len(entries) - 3:
            # 从 i 起找连续编号 run
            j = i + 1
            while j < len(entries) and entries[j][1] == entries[j - 1][1] + 1:
                j += 1
            run_len = j - i
            if run_len >= 3:
                run_records = [entries[k][0] for k in range(i, j)]
                run_nums = [entries[k][1] for k in range(i, j)]
                run_dates = [entries[k][0].get("expense_date", "") for k in range(i, j) if entries[k][0].get("expense_date")]
                span = 0
                if run_dates:
                    try:
                        span = (date.fromisoformat(max(run_dates)) - date.fromisoformat(min(run_dates))).days
                    except ValueError:
                        span = sequential_window + 1
                if span <= sequential_window:
                    builder.add("sequential-invoice", "同一商户短期内发票连号（≥3 张连续编号）", 3, "moderate",
                                run_records,
                                ("expense_id", "vendor_name", "invoice_number", "expense_date", "amount"),
                                ["%d 张发票编号连续（跨度 %d 天）：%s" % (run_len, span, ", ".join(str(n) for n in run_nums))],
                                ["连号发票常指向分拆报销或虚构业务"],
                                ["是否为同一次消费的拆分、团建或代订？"],
                                ["核对发票原件、消费现场记录和报销事由"],
                                [{"factor": "sequential_invoice", "points": 3, "run_length": run_len, "span_days": span}])
                    break  # 一组只报一次
            i += 1

    # 规则：发票号格式异常
    # 检测非标准字符（如 @、! 等）、过长、过短
    format_anomaly = []
    for row in rows:
        inv = norm_text(row.get("invoice_number"))
        if not inv:
            continue
        reasons = []
        # 过短（不含数字）
        if len(inv) < 4:
            reasons.append("长度过短")
        # 过长（>40 字符）
        if len(inv) > 40:
            reasons.append("长度超过 40 字符")
        # 含非标准字符（除字母数字、连字符、下划线、点、空格外）
        if re.search(r"[^A-Za-z0-9\-_. ]", inv):
            reasons.append("含非常规字符")
        # 仅含乱码（连续 4+ 个非典型字符）
        if re.search(r"[@#$%^&*!]{2,}", inv):
            reasons.append("疑似乱码字符")
        if reasons:
            format_anomaly.append((row, reasons))
    if format_anomaly:
        builder.add("invoice-format-anomaly", "发票号格式异常", 3, "moderate",
                    [r[0] for r in format_anomaly],
                    ("expense_id", "vendor_name", "invoice_number"),
                    ["%d 条发票号存在格式异常：%s" % (
                        len(format_anomaly),
                        "; ".join(["%s(%s)" % (r[0].get("invoice_number", ""), ",".join(r[1])) for r in format_anomaly[:5]]))],
                    ["格式异常可能指向虚假发票或录入错误"],
                    ["是否为手工伪造、系统录入错误或扫描 OCR 异常？"],
                    ["核对发票原件与开票方信息"],
                    [{"factor": "invoice_format_anomaly", "points": 3}])

    # 规则：大额低层级审批
    # 当金额超过 large_amount_threshold 但审批人在 low_level_approver_keywords 列表中
    large_amount_threshold = float(policy.get("large_amount_threshold", 5000))
    low_level_keywords = [k.lower() for k in policy.get("low_level_approver_keywords", [])]
    if low_level_keywords:
        large_low_level = []
        for row in rows:
            amount = row.get("amount", 0) or 0
            approver = norm_text(row.get("approver")).lower()
            if amount >= large_amount_threshold and approver and any(kw in approver for kw in low_level_keywords):
                large_low_level.append(row)
        if large_low_level:
            builder.add("large-amount-low-level-approval", "大额费用由低层级审批人审批", 4, "strong",
                        large_low_level,
                        ("expense_id", "amount", "approver", "currency"),
                        ["%d 条记录金额 ≥ %s 但审批人匹配低层级关键词" % (len(large_low_level), large_amount_threshold)],
                        ["可能存在越权审批或审批流形同虚设"],
                        ["审批人是否对应金额权限？是否存在代审批？"],
                        ["核对组织架构中的审批权限表和审批流"],
                        [{"factor": "large_amount_low_level_approval", "points": 4, "threshold": large_amount_threshold}])

    # v0.2.13：绝对大额（**可选，默认关闭**）——公司没有制度额度/审批阈值时，也能按"绝对金额"给出复核线索。
    # 默认不启用 = 与旧版完全一致；只有 large_amount_check=true 才生效。
    # 与「大额低层级审批」去重：已被后者覆盖的行不再重复报。
    if policy.get("large_amount_check", False):
        low_level_covered = set()
        if low_level_keywords:
            for row in rows:
                _a = norm_text(row.get("approver")).lower()
                if (row.get("amount") or 0) >= large_amount_threshold and _a and any(kw in _a for kw in low_level_keywords):
                    low_level_covered.add(row["expense_id"])
        large_rows = [r for r in rows
                      if (r.get("amount") or 0) >= large_amount_threshold and r["expense_id"] not in low_level_covered]
        if large_rows:
            builder.add("large-amount", "单笔金额达到配置的大额阈值", 3, "moderate", large_rows,
                        ("expense_id", "employee_id", "amount", "currency", "expense_type"),
                        ["%d 条记录金额 ≥ %s %s" % (len(large_rows), large_amount_threshold, large_rows[0]["currency"])],
                        ["大额本身不是问题；仅用于确定复核优先级"],
                        ["是否有业务合理性说明与相应层级的审批？是否附合同/验收/明细？"],
                        ["抽取大额样本核对原始单据、业务实质与审批层级"],
                        [{"factor": "large_amount", "points": 3, "threshold": large_amount_threshold}])

    # ============ v0.2.0 新增规则 ============

    # 规则：自审自批（审批人与报销人是同一人）—— 高信号
    # v0.2.13：报销人可以是 employee_id 或 employee_name；审批人命中其一即算自审自批。
    self_approval_pairs = []
    for row in rows:
        approver = norm_text(row.get("approver"))
        identities = {norm_text(row.get("employee_id")), norm_text(row.get("employee_name"))}
        identities.discard("")
        if approver and approver in identities:
            self_approval_pairs.append(row)
    if self_approval_pairs:
        builder.add("self-approval", "审批人与报销人为同一人（自审自批）", 4, "strong",
                    self_approval_pairs,
                    ("expense_id", "employee_id", "approver", "amount", "expense_type"),
                    ["%d 条记录的审批人与报销人相同" % len(self_approval_pairs)],
                    ["自审自批违反基本内部控制原则，除非制度另有规定"],
                    ["是否存在代审批、紧急事后补批或权限错误？"],
                    ["核对审批日志、组织架构和代审批授权"],
                    [{"factor": "self_approval", "points": 4}])
    else:
        # v0.2.13：口径提示——审批人列像是姓名、报销人列像是工号时，几乎必然漏检。
        # 明确写入 skipped，而不是静默"没发现"。这正是真实审计师反馈的第 4 条。
        approver_vals = [norm_text(r.get("approver")) for r in rows if norm_text(r.get("approver"))]
        emp_vals = [norm_text(r.get("employee_id")) for r in rows if norm_text(r.get("employee_id"))]
        has_name_col = any(norm_text(r.get("employee_name")) for r in rows)
        if approver_vals and emp_vals and not has_name_col:
            def _cjk(val: str) -> bool:
                return any("\u4e00" <= ch <= "\u9fff" for ch in val)

            approver_cjk = sum(1 for v in approver_vals if _cjk(v)) / len(approver_vals)
            employee_cjk = sum(1 for v in emp_vals if _cjk(v)) / len(emp_vals)
            if approver_cjk >= 0.6 and employee_cjk <= 0.2:
                skipped.append(
                    "self-approval：审批人列疑似「姓名」、报销人列疑似「工号」，两者口径可能不一致，"
                    "可能漏检自审自批；建议统一为工号或姓名（或提供 employee_name 列）"
                )

    # 规则：发票跨人复用（同一发票号被不同员工使用）
    invoice_employee = defaultdict(set)
    for row in rows:
        inv = norm_text(row.get("invoice_number"))
        emp = norm_text(row.get("employee_id"))
        if inv and emp:
            invoice_employee[inv].add(emp)
    cross_employee_invoices = [(inv, emps) for inv, emps in invoice_employee.items() if len(emps) > 1]
    if cross_employee_invoices:
        cross_records = []
        for inv, _ in cross_employee_invoices:
            for row in rows:
                if norm_text(row.get("invoice_number")) == inv:
                    cross_records.append(row)
        builder.add("cross-employee-invoice", "同一发票号被多个员工报销（发票跨人复用）", 4, "strong",
                    cross_records,
                    ("expense_id", "invoice_number", "employee_id", "amount"),
                    ["%d 张发票被多名员工重复使用" % len(cross_employee_invoices)],
                    ["极可能是虚假发票或员工互相借用报销"],
                    ["是否为同一笔消费的拼单、团建或代订？"],
                    ["核对发票原件、消费现场记录和报销状态"],
                    [{"factor": "cross_employee_invoice", "points": 4, "count": len(cross_employee_invoices)}])

    # 规则：提交日期早于消费日期（时序倒挂）
    submission_inversion = []
    for row in rows:
        sub = parse_date(row.get("submit_date"))
        exp = parse_date(row.get("expense_date"))
        if sub and exp and sub < exp:
            submission_inversion.append(row)
    if submission_inversion:
        builder.add("submit-before-expense", "提交日期早于费用发生日期（时序倒挂）", 2, "moderate",
                    submission_inversion,
                    ("expense_id", "employee_id", "expense_date", "submit_date"),
                    ["%d 条记录的提交日期早于消费日期" % len(submission_inversion)],
                    ["通常报销在消费之后提交；倒挂可能是补录或数据错"],
                    ["是否为事后补录、系统数据导入或日期口径差异？"],
                    ["核对提交日志、补录审批和系统操作记录"],
                    [{"factor": "submit_before_expense", "points": 2}])

    # 规则：未来日期（v0.2.0：as_of_date 可配置）
    as_of_date_str = policy.get("as_of_date")
    if as_of_date_str:
        try:
            today = date.fromisoformat(as_of_date_str)
        except (ValueError, TypeError):
            today = date.today()
    else:
        today = date.today()
    future_records = []
    for row in rows:
        exp = parse_date(row.get("expense_date"))
        if exp and date.fromisoformat(exp) > today:
            future_records.append(row)
    if future_records:
        builder.add("future-date", "费用日期在未来", 3, "moderate",
                    future_records,
                    ("expense_id", "employee_id", "expense_date", "amount"),
                    ["%d 条记录的费用日期在未来（基准日 %s）" % (len(future_records), today.isoformat())],
                    ["未来日期可能意味着录入错误或预填"],
                    ["是否系统录入错误或预占？"],
                    ["核对系统时间和原始凭证日期"],
                    [{"factor": "future_date", "points": 3}])

    # 规则：缺费用类型按最严格类别处理（policy-threshold 已经在 limit 匹配时通过 continue 跳过，
    # 这里我们改为：缺类型且单笔 > 通用最严上限时报警）
    if policy.get("limits"):
        # 最严格上限 = 各限额里最小的 max_amount（越小越严），此前误用 max() 导致多限额时漏报
        parsed_limits = []
        for limit in policy.get("limits", []):
            a = parse_amount(limit.get("max_amount"))
            if a is not None and a > 0:
                parsed_limits.append(a)
        strictest_max = min(parsed_limits) if parsed_limits else 0
        missing_type_records = [
            row for row in rows
            if not norm_text(row.get("expense_type")) and strictest_max and row["amount"] > strictest_max
        ]
        if missing_type_records:
            builder.add("missing-expense-type", "缺费用类型且金额超过所有类别上限的最严格值", 2, "moderate",
                        missing_type_records,
                        ("expense_id", "amount", "expense_type"),
                        ["%d 条记录缺 expense_type 且金额超过 %s" % (len(missing_type_records), strictest_max)],
                        ["缺类型无法匹配任何制度阈值，按最严格处理"],
                        ["是否为数据导入异常或字段缺失？"],
                        ["补充 expense_type 后重新跑"],
                        [{"factor": "missing_expense_type", "points": 2, "strictest_max": strictest_max}])

    # 规则：时空冲突（同一员工同一天在多个城市产生定位型消费，物理上无法同时在场）
    conflict_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        city = norm_text(row.get("dest_city"))
        etype = match_key(row.get("expense_type"))
        if not city or etype == "travel" or not row.get("expense_date"):
            continue
        conflict_groups[(row["employee_id"], row["expense_date"])].append(row)
    for (emp, day), group in conflict_groups.items():
        cities = sorted({norm_text(r.get("dest_city")) for r in group if norm_text(r.get("dest_city"))})
        if len(cities) >= 2:
            builder.add("space-time-conflict", "同一员工同一天在多个城市产生消费", 3, "strong", group,
                        ("expense_id", "employee_id", "expense_date", "origin_city", "dest_city"),
                        ["%d 条记录在 %s 同一天出现在 %s 等多个城市" % (len(group), day, "、".join(cities))],
                        ["同一人同一天在多个城市产生定位型消费，物理上无法同时在场"],
                        ["是否为差旅分段、城市同名误录或系统定位口径差异？"],
                        ["核对行程单、车票/机票和入住记录"],
                        [{"factor": "space_time_conflict", "points": 3, "cities": cities}])

    # 规则：跨期入账（提交日期距费用发生日期超过 N 个月）
    cross_months = int(policy.get("cross_period_months", 3))
    if cross_months > 0:
        cross_records = []
        for row in rows:
            exp = row.get("expense_date")
            sub = row.get("submit_date")
            if not exp or not sub:
                continue
            try:
                d_exp = date.fromisoformat(exp)
                d_sub = date.fromisoformat(sub)
            except ValueError:
                continue
            month_diff = (d_sub.year - d_exp.year) * 12 + (d_sub.month - d_exp.month)
            if month_diff >= cross_months:
                cross_records.append(row)
        if cross_records:
            builder.add("cross-period", "费用提交距发生跨期过久", 2, "moderate", cross_records,
                        ("expense_id", "employee_id", "expense_date", "submit_date", "amount"),
                        ["%d 条记录的提交日期距费用发生日期超过 %d 个月" % (len(cross_records), cross_months)],
                        ["跨期过久可能指向补录、费用归属期异常或账务处理延迟"],
                        ["是否为历史补录、系统迁移或跨期结账？"],
                        ["核对费用归属期间和入账批次"],
                        [{"factor": "cross_period", "points": 2, "months": cross_months}])
    else:
        skipped.append("cross-period：cross_period_months ≤ 0 已禁用")

    # 规则：高频小额（同一员工短期内多笔小额，疑似套现/拆单模式）
    hf_min = int(policy.get("high_frequency_min_count", 10))
    if hf_min > 1:
        hf_days = int(policy.get("high_frequency_window_days", 30))
        hf_max = float(policy.get("high_frequency_max_amount", 100))
        small = [r for r in rows if r["amount"] is not None and r["amount"] <= hf_max]
        by_emp: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for r in small:
            by_emp[(r["employee_id"], match_key(r.get("expense_type")))].append(r)
        for (emp, etype), grp in by_emp.items():
            grp = sorted(grp, key=lambda r: r["expense_date"])
            dates = [date.fromisoformat(r["expense_date"]) for r in grp]
            flagged: Dict[str, Dict[str, Any]] = {}
            i = 0
            for j in range(len(grp)):
                while i < j and (dates[j] - dates[i]).days > hf_days:
                    i += 1
                if j - i + 1 >= hf_min:
                    for k in range(i, j + 1):
                        flagged[grp[k]["expense_id"]] = grp[k]
            if flagged:
                recs = list(flagged.values())
                builder.add("high-frequency-small-amount", "同一员工短期内高频小额消费", 3, "moderate", recs,
                            ("expense_id", "employee_id", "expense_type", "expense_date", "amount"),
                            ["%d 笔小额（≤%.0f）集中在 %d 天内" % (len(recs), hf_max, hf_days)],
                            ["短期内高频小额消费，可能指向套现、拆分或虚构小额业务"],
                            ["是否为通勤、市内交通等正常高频小额场景？"],
                            ["对照行程、事由和支付流水"],
                            [{"factor": "high_frequency_small_amount", "points": 3, "count": len(recs)}])
    else:
        skipped.append("high-frequency-small-amount：high_frequency_min_count ≤ 1 已禁用")

    # v0.2.13：商户集中度（**可选，默认关闭**）——某员工/部门的支出过度集中在单一商户。
    # 默认不启用 = 与旧版完全一致；只有 vendor_concentration_check=true 才生效。
    if policy.get("vendor_concentration_check", False):
        vc_min = int(policy.get("vendor_concentration_min_count", 5))
        vc_share = float(policy.get("vendor_concentration_share", 0.6))
        vc_scope = str(policy.get("vendor_concentration_scope", "employee"))
        vgroups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = norm_text(row.get("department") if vc_scope == "department" else row.get("employee_id"))
            if key:
                vgroups[key].append(row)
        for scope_key, group in vgroups.items():
            if len(group) < vc_min:
                continue
            by_vendor: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for row in group:
                vendor_key = match_key(row["vendor_name"])
                if vendor_key:
                    by_vendor[vendor_key].append(row)
            if not by_vendor:
                continue
            top_vendor, top_rows = max(by_vendor.items(), key=lambda kv: len(kv[1]))
            share = len(top_rows) / len(group)
            if len(top_rows) >= vc_min and share >= vc_share:
                builder.add("vendor-concentration", "支出过度集中于单一商户", 2, "weak", top_rows,
                            ("expense_id", "employee_id", "vendor_name", "amount", "expense_date"),
                            ["%s 共 %d 笔费用，其中 %d 笔（%.0f%%）集中在同一商户“%s”" % (scope_key, len(group), len(top_rows), share * 100, top_rows[0]["vendor_name"])],
                            ["集中度高本身不是问题；仅作为关系/串通风险的复核线索"],
                            ["该商户是否为长期定点供应商、协议单位或唯一可选渠道？"],
                            ["核对商户资质、比价记录、招采流程与关联关系"],
                            [{"factor": "vendor_concentration", "points": 2, "share": round(share, 2)}])

    # v0.2.8：撤回/拒绝后重提且金额增加（仅在配置了 status_filter 时才有数据可判，默认不影响）
    _rule_resubmit_after_rejection(rows, status_excluded or [], policy, builder)

    return skipped, {
        "near_duplicate_window_days": near_days,
        "near_duplicate_amount_tolerance": near_tolerance,
        "split_window_days": split_days,
        "weekend_check": bool(policy.get("weekend_check", False)),
        "outlier_min_group_size": min_group,
        "outlier_robust_z": z_threshold,
        "policy_version": policy.get("policy_version"),
        "cross_period_months": policy.get("cross_period_months", 3),
        "high_frequency_window_days": policy.get("high_frequency_window_days", 30),
        "high_frequency_min_count": policy.get("high_frequency_min_count", 10),
        "high_frequency_max_amount": policy.get("high_frequency_max_amount", 100),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def validate(findings: Sequence[Dict[str, Any]], evidence: Sequence[Dict[str, Any]]) -> None:
    evidence_ids = {item["evidence_id"] for item in evidence}
    finding_ids = set()
    for finding in findings:
        if finding["finding_id"] in finding_ids:
            raise ValueError("finding_id 重复")
        finding_ids.add(finding["finding_id"])
        if not finding["evidence_refs"] or not set(finding["evidence_refs"]).issubset(evidence_ids):
            raise ValueError("finding %s 存在缺失 evidence 引用" % finding["finding_id"])
        if not finding.get("human_review_required"):
            raise ValueError("finding 必须要求人工复核")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--field-map", type=Path)
    parser.add_argument("--sheet")
    # v0.2.9：可选辅助数据，用于出差交叉核验（不提供则完全不启用）
    parser.add_argument("--travel-requests", type=Path, help="可选：出差申请单（CSV/XLSX）")
    parser.add_argument("--attendance", type=Path, help="可选：打卡/考勤记录（CSV/XLSX）")
    # v0.2.13：可选白名单（显式豁免、可审计、不静默丢弃）
    parser.add_argument("--allowlist", type=Path,
                        help="可选：白名单 CSV（列：expense_id/employee_id/vendor_name/invoice_number/expense_type/amount_max/reason）")
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args(argv)
    if args.check_env:
        try:
            import openpyxl
            xlsx = "available (%s)" % openpyxl.__version__
        except ImportError:
            xlsx = "unavailable; CSV mode still works"
        print(json.dumps({"python": sys.version.split()[0], "recommended": ">=3.10", "xlsx_support": xlsx, "network_required": False}, ensure_ascii=False))
        return 0
    if not args.input or not args.output:
        parser.error("正式运行需要 --input 和 --output")
    input_path = args.input.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("输出目录非空；请指定新的目录：%s" % output)
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    source_hash = sha256_file(input_path)
    policy = load_json(args.policy.resolve() if args.policy else None)
    if policy:
        validate_policy(policy)
    allowlist = Allowlist.load(args.allowlist.resolve() if args.allowlist else None)
    explicit_map = load_json(args.field_map.resolve() if args.field_map else None)
    headers, source_rows, sheet = read_table(input_path, args.sheet)
    mapping, warnings = resolve_mapping(headers, explicit_map, allow_missing_amount=bool(policy.get("amount_columns")))
    if not policy.get("default_currency"):
        warnings.append("未配置 default_currency，缺失币种按 CNY 处理")
    clean, bad, changes = normalize_rows(source_rows, mapping, str(policy.get("default_currency", "CNY")), policy.get("amount_columns"))
    # v0.2.8：按审批状态筛选（可选；不配置 status_filter 时与旧版行为完全一致）
    analyzable, status_excluded = apply_status_filter(clean, policy)
    if status_excluded:
        warnings.append("已按 status_filter 排除 %d 行（见 excluded_by_status.csv），这些行不参与分析" % len(status_excluded))
    builder = ResultBuilder(input_path.name, source_hash, policy, allowlist=allowlist)
    skipped, parameters = run_rules(analyzable, policy, builder, status_excluded=status_excluded)

    # v0.2.9：出差交叉核验（可选）。不提供辅助数据时**一行也不产生**，输出与旧版完全一致。
    travel_rows: List[Dict[str, Any]] = []
    attendance_rows: List[Dict[str, Any]] = []
    if args.travel_requests:
        travel_rows, _tm = read_aux_table(args.travel_requests.resolve(), TRAVEL_REQUEST_ALIASES, args.sheet)
        warnings.append("已载入出差申请 %d 条（%s）" % (len(travel_rows), args.travel_requests.name))
    if args.attendance:
        attendance_rows, _am = read_aux_table(args.attendance.resolve(), ATTENDANCE_ALIASES, args.sheet)
        warnings.append("已载入打卡记录 %d 条（%s）" % (len(attendance_rows), args.attendance.name))
    if travel_rows or attendance_rows:
        skipped.extend(run_travel_cross_check(analyzable, travel_rows, attendance_rows, policy, builder, {}, {}))
        if not args.travel_requests:
            skipped.append("travel_cross_check：未提供 --travel-requests（无法核对「有无出差申请」）")
        if not args.attendance:
            skipped.append("travel_cross_check：未提供 --attendance（无法核对打卡）")
    validate(builder.findings, builder.evidence)

    write_csv(output / "clean_expenses.csv", clean, OUTPUT_FIELDS + ("_source_row", "_source_sheet"))
    write_csv(output / "bad_rows.csv", bad, ("source_row", "reasons", "raw_record"))
    if status_excluded:
        write_csv(output / "excluded_by_status.csv",
                  [{"source_row": r.get("_source_row"), "expense_id": r.get("expense_id"),
                    "employee_id": r.get("employee_id"), "status": r.get("status"),
                    "amount": r.get("amount"), "expense_date": r.get("expense_date")} for r in status_excluded],
                  ("source_row", "expense_id", "employee_id", "status", "amount", "expense_date"))
    flat = []
    for finding in builder.findings:
        flat.append({
            "finding_id": finding["finding_id"], "finding_type": finding["finding_type"],
            "title": finding["title"],
            "risk_priority": PRIORITY_ZH.get(finding["risk_priority"], finding["risk_priority"]),
            "evidence_strength": STRENGTH_ZH.get(finding["evidence_strength"], finding["evidence_strength"]),
            "risk_score": finding["risk_score"],
            "entities": json.dumps(finding["entities"], ensure_ascii=False),
            "evidence_refs": "|".join(finding["evidence_refs"]),
        })
    write_csv(output / "findings.csv", flat, ("finding_id", "finding_type", "title", "risk_priority", "evidence_strength", "risk_score", "entities", "evidence_refs"))
    write_jsonl(output / "findings.jsonl", builder.findings)
    write_jsonl(output / "evidence.jsonl", builder.evidence)
    # v0.2.13：被白名单压制的告警——完整留痕（可复核、可撤销），绝不静默丢弃
    if builder.suppressed:
        write_csv(output / "suppressed_findings.csv", builder.suppressed,
                  ("finding_type", "title", "rows", "expense_ids", "employees", "vendors", "max_amount", "suppressed_reason"))

    null_rates = {}
    for header in headers:
        null_rates[header] = round(sum(1 for row in source_rows if not norm_text(row.get(header))) / max(len(source_rows), 1), 6)
    quality = [
        "# 数据质量报告", "",
        "> 技术附录：本文件是数据体检的机器记录（字段映射、空值率、标准化计数等），供复核追溯，不是审计结论。", "",
        "- 源文件：`%s`" % input_path.name,
        "- 工作表：`%s`" % (sheet or "CSV"), "- 源数据行数：%d" % len(source_rows),
        "- 有效行数：%d" % len(clean), "- Bad rows：%d" % len(bad),
        "- 参与分析行数：%d" % len(analyzable),
    ]
    if status_excluded:
        quality.append("- 按 status_filter 排除：%d 行（见 excluded_by_status.csv，不参与分析）" % len(status_excluded))
    if allowlist is not None:
        quality.append("- 白名单：%d 条条目，压制 %d 条告警（见 suppressed_findings.csv；被压制内容完整留痕，不静默丢弃）"
                       % (len(allowlist.entries), len(builder.suppressed)))
    quality.extend([
        "- 字段映射：`%s`" % json.dumps(mapping, ensure_ascii=False),
        "- 标准化计数：`%s`" % json.dumps(changes, ensure_ascii=False), "", "## 源字段空值率", "",
    ])
    quality.extend("- `%s`: %.2f%%" % (field, rate * 100) for field, rate in null_rates.items())
    if warnings or skipped:
        quality.extend(["", "## 警告与跳过规则", ""] + ["- " + item for item in warnings + skipped])
    (output / "data_quality.md").write_text("\n".join(quality) + "\n", encoding="utf-8")

    # 类型/优先级显示层中文化（英文 key 保留在 findings.jsonl 供机器比对）
    counts = defaultdict(int)
    priorities = defaultdict(int)
    for finding in builder.findings:
        counts[FINDING_TYPE_ZH.get(finding["finding_type"], finding["finding_type"])] += 1
        priorities[PRIORITY_ZH.get(finding["risk_priority"], finding["risk_priority"])] += 1
    # 注意：priorities 是「中文标签」计数；这里按风险优先级统计必须用原始英文 key，否则恒为 0
    feedback_high = sum(1 for f in builder.findings if f["risk_priority"] in ("critical", "high"))
    feedback_medium = sum(1 for f in builder.findings if f["risk_priority"] == "medium")
    feedback_low = sum(1 for f in builder.findings if f["risk_priority"] == "low")
    feedback_stats_line = "本次运行已自动统计：Findings %d（高风险 %d / 中风险 %d / 低风险 %d），各类型、风险分布、耗时等统计见上。" % (
        len(builder.findings), feedback_high, feedback_medium, feedback_low
    )
    summary = [
        "# 费用审计确定性摘要", "", "- 分析有效记录：%d；排除坏行：%d。" % (len(clean), len(bad)),
        "- Findings：%d；Evidence：%d。" % (len(builder.findings), len(builder.evidence)),
        "- 风险优先级：`%s`" % json.dumps(dict(priorities), ensure_ascii=False, sort_keys=True),
        "- 发现类型：`%s`" % json.dumps(dict(counts), ensure_ascii=False, sort_keys=True), "",
        "> 这些结果是复核线索，不是舞弊、虚假报销或拒付结论。请先查看数据质量，再回到 evidence 对应源行核验。", "",
        "## 业务实质性声明（请务必阅读）", "",
        "本报告提供的是**数据匹配层面的合理保证（reasonable assurance）**，不是业务实质的绝对保证。", "",
        "- **已验证**：发票号、金额、日期、限额、审批流等数据之间的一致性。",
        "- **无法验证**：费用背后业务是否真实发生。例：一笔合规的客情费——发票真实、未超限、日期合规、就餐时间正常——但当事人当时是否真的在宴请客户，本工具无从判断。", "",
        "因此请注意两点：", "",
        "1. **未发现问题 ≠ 没有问题**：本报告只覆盖「可被数据匹配到的异常」，未被标记的部分，其业务实质尚未核实。",
        "2. **如需深入核查业务实质**，请补充佐证：客户名单、会议/拜访记录、行程单、签到表、定位记录、业务往来凭证等。", "",
        "审计工作在此只完成了一部分：数据匹配已完成，业务实质仍需更多数据佐证。", "",
        "## 建议复核顺序", "",
        "1. 先查 high/critical 且 evidence_strength 为 strong 的重复或制度命中。",
        "2. 再按员工、商户和期间合并 near duplicate、split 和 outlier 模式。",
        "3. 周末信号单独保持低优先级，主动寻找值班、出差和客户现场等合理解释。", "",
        "## 输出文件", "",
        "**审计结论（给人看）**：dashboard.html（全景图，给经理/管理层快速看）、summary.md（完整结论）、findings.csv、findings.jsonl", "",
        "**技术审计轨迹（复核追溯用，非审计结论）**：data_quality.md、run_manifest.json、clean_expenses.csv、bad_rows.csv、evidence.jsonl", "",
        "## 这个工具好用吗？（可选反馈，工具不会自动外发）", "",
        feedback_stats_line,
        "如果它对你有帮助，可以对 AI 说一句「**生成反馈内容**」——它会生成一段**不含任何敏感信息**的统计（发现了几类问题、耗时）并**展示给你**，由**你自己**决定是否复制走、发到作者的 GitHub Issue。", "",
        "**不含员工、供应商、发票号、金额**；核心分析全程在你本地。**你不发，就没有任何内容离开你的电脑。**", "",
        "想反馈时，把这句发给 AI 即可（可附意见，如「速度偏慢」）：", "",
        "> 生成反馈内容",
    ]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    finished = datetime.now(timezone.utc)
    script_path = Path(__file__).resolve()
    input_files = [{"path": input_path.name, "sha256": source_hash, "sheet": sheet}]
    if args.policy:
        input_files.append({"path": args.policy.name, "sha256": sha256_file(args.policy.resolve())})
    if args.field_map:
        input_files.append({"path": args.field_map.name, "sha256": sha256_file(args.field_map.resolve())})
    # v0.2.9：可选辅助数据也登记哈希，保证可追溯
    if args.travel_requests and args.travel_requests.exists():
        input_files.append({"path": args.travel_requests.name, "sha256": sha256_file(args.travel_requests.resolve()), "role": "travel_requests"})
    if args.attendance and args.attendance.exists():
        input_files.append({"path": args.attendance.name, "sha256": sha256_file(args.attendance.resolve()), "role": "attendance"})
    manifest = {
        "run_id": "EXP-%s-%s" % (started.strftime("%Y%m%dT%H%M%SZ"), source_hash[:8]),
        "skill": SKILL, "skill_version": VERSION, "started_at": started.isoformat(), "finished_at": finished.isoformat(),
        "input_files": input_files, "parameters": parameters, "field_mapping": mapping,
        "scripts": {script_path.name: "sha256:" + sha256_file(script_path)},
        "warnings": warnings, "skipped_rules": skipped, "network_access": False,
        "allowlist": ({"entries": len(allowlist.entries), "suppressed_findings": len(builder.suppressed)} if allowlist is not None else None),
        "outputs": ["clean_expenses.csv", "bad_rows.csv"]
        + (["excluded_by_status.csv"] if status_excluded else [])
        + (["suppressed_findings.csv"] if builder.suppressed else [])
        + ["findings.csv", "findings.jsonl", "evidence.jsonl", "summary.md", "data_quality.md", "run_manifest.json", "dashboard.html"],
        "note": "技术审计轨迹：记录本次运行的机器可追溯信息（哈希、字段映射、参数等），供复核追溯，不是审计结论。",
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    build_dashboard_html(manifest, builder.findings, len(clean), len(bad), output)
    print(json.dumps({"output": str(output), "valid_rows": len(clean), "bad_rows": len(bad), "findings": len(builder.findings), "evidence": len(builder.evidence)}, ensure_ascii=False))
    print("提示：如果本工具有帮助，可以对我说「生成反馈内容」——我会生成一段不含敏感信息的统计（不含员工/供应商/发票号/金额）给你，由你自己决定是否发给作者。核心分析在本地；工具不会自动外发任何内容。", file=sys.stderr)
    return 0


def build_dashboard_html(manifest, findings, clean_count, bad_count, output_dir):
    """生成面向「审计经理」的自包含 HTML 全景报告（离线可看，0 外部依赖）。

    结构对齐审计报告最佳实践：
      第一屏（执行摘要，可独立看懂）：
        论点结论 → 关键指标 → 风险分布 → 最需要先看的 3 条 → 建议下一步 → 明细入口
      往下（按需展开）：
        重点发现逐条（现象/依据/建议/待澄清）→ 按类型汇总 → 数据质量 → 业务定位
    """
    import csv as _csv
    from collections import Counter
    from html import escape

    PRIORITY_ZH = {"critical": "严重", "high": "高风险", "medium": "中风险", "low": "低风险"}
    ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # 制度依据：仅用于展示「本应如何」，不改动任何判定逻辑
    CRITERIA = {
        "exact-duplicate-invoice": "同一发票号不应重复报销。",
        "exact-duplicate-employee-date-amount": "同一员工同一天出现相同金额，通常对应同一笔业务，不应重复报销。",
        "near-duplicate": "金额、日期、商户高度近似的记录，需确认是否为同一笔业务重复入账。",
        "policy-threshold": "单笔费用不应超过费用制度规定的对应上限。",
        "split-expense": "不得为规避审批或限额而把一笔费用拆成多笔。",
        "weekend-signal": "周末发生的消费通常需要值班、出差或客户现场等业务说明。",
        "holiday-signal": "节假日发生的消费通常需要值班、出差或客户现场等业务说明。",
        "robust-outlier": "同类费用中显著偏高的金额需要业务合理性说明。",
        "self-approval": "报销人不应对自己的报销进行审批。",
        "cross-employee-invoice": "同一发票不应在不同员工之间重复报销。",
        "submit-before-expense": "报销提交时间不应早于费用发生时间。",
        "future-date": "费用发生日期不应晚于审计基准日。",
        "missing-expense-type": "报销记录应填写费用类型，以便套用正确的限额。",
        "sequential-invoice": "短时间内连号的发票需要确认业务真实性。",
        "invoice-format-anomaly": "发票号应符合常见编码格式。",
        "large-amount-low-level-approval": "大额费用应由更高层级审批。",
        "space-time-conflict": "同一人在同一时间不应出现在两地；同日多笔行程需能衔接。",
        "cross-period": "费用应计入其发生期间，不应跨期入账。",
        "high-frequency-small-amount": "短期内高频次小额报销需要确认业务真实性。",
        "resubmit-after-rejection-amount-increase": "被撤回/拒绝的申请不应在重提时无理由地提高金额。",
        "expense-without-travel-request": "差旅报销原则上应有对应的出差申请作为依据。",
        "office-swipe-on-offsite-claim": "报销称在外地，但本人当天在公司打卡（需确认是否代报销）。",
        "attendance-city-mismatch": "报销的出差城市应与当天打卡地点所在城市一致。",
    }

    def type_zh(ft):
        return FINDING_TYPE_ZH.get(ft, ft)

    # ---------- 状态 ----------
    counts = Counter(f.get("risk_priority", "?") for f in findings)
    critical, high = counts.get("critical", 0), counts.get("high", 0)
    medium, low = counts.get("medium", 0), counts.get("low", 0)
    if critical + high > 0:
        status_class, status_label, status_zh = "critical", "CRITICAL", "需立即处理"
    elif medium > 0:
        status_class, status_label, status_zh = "review", "REVIEW", "建议逐条复核"
    elif findings:
        status_class, status_label, status_zh = "notice", "NOTICE", "以提示为主"
    else:
        status_class, status_label, status_zh = "pass", "PASS", "未见明显异常"

    # ---------- 时间 / 版本 ----------
    duration_str, date_str = "—", "—"
    try:
        from datetime import datetime
        _s = datetime.fromisoformat(manifest["started_at"])
        _e = datetime.fromisoformat(manifest["finished_at"])
        duration_str = "%.1f 秒" % (_e - _s).total_seconds()
        date_str = _s.strftime("%Y-%m-%d %H:%M")
    except (KeyError, ValueError):
        pass
    version = manifest.get("skill_version", "?")

    # ---------- 聚合 ----------
    emps = sorted({e["id"] for f in findings for e in f.get("entities", []) if e.get("type") == "employee"})
    vens = sorted({e["id"] for f in findings for e in f.get("entities", []) if e.get("type") == "vendor"})
    amount_total = sum(f.get("max_amount") or 0 for f in findings if isinstance(f.get("max_amount"), (int, float)))
    type_counts = Counter(f.get("finding_type", "?") for f in findings)
    high_by_type = Counter(f.get("finding_type", "?") for f in findings
                           if f.get("risk_priority") in ("critical", "high"))
    top_type, top_cnt = (type_counts.most_common(1)[0] if type_counts else ("", 0))

    # ---------- 论点句（第一屏核心）----------
    if status_class == "critical":
        thesis_main = "发现 <b>%d</b> 条线索，其中 <b>%d</b> 条高风险，需优先核对。" % (len(findings), critical + high)
    elif status_class == "review":
        thesis_main = "发现 <b>%d</b> 条线索（%d 条中风险），建议按员工与商户归并后逐条确认。" % (len(findings), medium)
    elif status_class == "notice":
        thesis_main = "发现 <b>%d</b> 条提示性信号，未见高风险线索。" % len(findings)
    else:
        thesis_main = "本次未发现明显异常，可作为进一步分析的可靠基线。"

    thesis_note = ""
    if top_cnt and len(findings) >= 10 and top_cnt >= max(10, int(len(findings) * 0.3)):
        if top_type in ("weekend-signal", "holiday-signal"):
            thesis_note = ("其中数量最多的是「%s」共 %d 条，属提示性信息（值班、出差、客户现场等常有正常解释），"
                           "通常无需逐条处理。" % (escape(type_zh(top_type)), top_cnt))
        else:
            thesis_note = "其中数量最多的是「%s」共 %d 条，建议优先按此类型归并复核。" % (escape(type_zh(top_type)), top_cnt)

    # ---------- 关键指标 ----------
    kpi_items = [
        ("需复核线索", "%d" % len(findings), "等待人工确认", ""),
        ("高风险", "%d" % (critical + high), "建议优先处理" if critical + high else "无", "alert" if critical + high else ""),
        ("涉及员工", "%d" % len(emps), "去重后人数", ""),
        ("涉及商户", "%d" % len(vens), "去重后家数", ""),
        ("线索金额合计", "¥{:,.0f}".format(amount_total), "同一笔可能被多条引用", ""),
    ]
    kpis_html = "".join(
        '<div class="kpi %s"><div class="v">%s</div><div class="l">%s</div><div class="h">%s</div></div>' % (cls, v, lbl, hint)
        for lbl, v, hint, cls in kpi_items
    )

    # ---------- 风险分布 ----------
    n_for_bar = max(1, len(findings))
    segs = []
    for cnt, key in ((critical + high, "crit"), (medium, "med"), (low, "low")):
        if cnt:
            segs.append('<span class="seg %s" style="width:%.4f%%"></span>' % (key, cnt / n_for_bar * 100))
    riskbar = '<div class="riskbar">%s</div>' % ("".join(segs) or '<span class="seg low" style="width:100%"></span>')
    legend = ('<div class="risklegend">'
              '<span><i class="dot crit"></i>高风险 %d</span>'
              '<span><i class="dot med"></i>中风险 %d</span>'
              '<span><i class="dot low"></i>低风险 %d</span></div>') % (critical + high, medium, low)

    # ---------- 最需要先看的 3 条 ----------
    ordered = sorted(findings, key=lambda f: (ORDER.get(f.get("risk_priority"), 9), -(f.get("risk_score") or 0)))

    def ent_human(f, limit=3):
        out = []
        for ent in f.get("entities", []):
            t, i = ent.get("type"), ent.get("id")
            if t == "employee":
                out.append("员工 %s" % i)
            elif t == "vendor":
                out.append("商户 %s" % i)
            else:
                out.append(str(i))
        return "、".join(out[:limit]) if out else "（无明确对象）"

    top_rows = []
    for f in ordered[:3]:
        pr = f.get("risk_priority", "low")
        amt = f.get("max_amount")
        amt_html = '<span class="top-amt">¥%.0f</span>' % amt if isinstance(amt, (int, float)) else ""
        top_rows.append(
            '<a class="top-row" href="#%s">'
            '<span class="badge badge-%s">%s</span>'
            '<span class="top-title">%s</span>'
            '<span class="top-who">%s</span>%s<span class="top-go">查看 →</span></a>' % (
                escape(str(f.get("finding_id", ""))), pr, PRIORITY_ZH.get(pr, pr),
                escape(f.get("title") or type_zh(f.get("finding_type", ""))),
                escape(ent_human(f)), amt_html))
    top_html = "".join(top_rows) if top_rows else '<p class="empty">未发现重点项。</p>'

    # ---------- 建议下一步 ----------
    if critical + high > 0:
        next_step = "先核对 <b>%d</b> 条高风险线索的真实性（每条已附证据编号）；再把其余线索按员工与商户归并，避免同一件事被反复问询。" % (critical + high)
    elif medium > 0:
        next_step = "按员工与商户归并后逐条确认；优先处理金额较大的中风险线索。"
    elif findings:
        next_step = "以抽样确认为主；如需逐一查看，请打开 findings.csv。"
    else:
        next_step = "无需处理；可作为后续比对的基线。"

    # ---------- 明细入口（放在第一屏）----------
    links = [
        ("findings.csv", "全部线索明细（按风险排序，Excel 可开）"),
        ("summary.md", "完整审计结论与建议复核顺序"),
        ("data_quality.md", "数据体检报告"),
        ("bad_rows.csv", "被隔离的问题行"),
    ]
    links_html = "".join(
        '<a href="%s"><span class="lk-name">%s</span><span class="lk-desc">%s</span></a>' % (h, h, d)
        for h, d in links
    )

    # ---------- 重点发现（细节层）----------
    key = [f for f in ordered if f.get("risk_priority") in ("critical", "high", "medium")]
    shown = key[:12]
    rest_count = len(key) - len(shown)
    cards = []
    for f in shown:
        pr = f.get("risk_priority", "low")
        fid = escape(str(f.get("finding_id", "")))
        amt = f.get("max_amount")
        amt_html = '<span class="fa-amount">涉及金额 ¥%.0f</span>' % amt if isinstance(amt, (int, float)) else ""
        facts = "；".join(f.get("facts", [])[:2]) or "—"
        crit = CRITERIA.get(f.get("finding_type", ""), "")
        steps = "；".join(f.get("recommended_next_steps", [])[:2]) or "—"
        questions = "；".join(f.get("open_questions", [])[:2])
        crit_html = ('<div class="finding-body"><span class="k">依据</span>%s</div>' % escape(crit)) if crit else ""
        q_html = ('<div class="finding-body"><span class="k">待澄清</span>%s</div>' % escape(questions)) if questions else ""
        cards.append(
            '<article class="finding %s" id="%s">'
            '<div class="finding-head">'
            '<span class="badge badge-%s">%s</span>'
            '<span class="finding-type">%s</span>%s</div>'
            '<h3 class="finding-title">%s</h3>'
            '<div class="finding-who"><span class="k">涉及</span>%s</div>'
            '<div class="finding-body"><span class="k">现象</span>%s</div>'
            '%s'
            '<div class="finding-body"><span class="k">建议</span>%s</div>'
            '%s'
            '</article>' % (
                pr, fid, pr, PRIORITY_ZH.get(pr, pr), escape(type_zh(f.get("finding_type", ""))), amt_html,
                escape(f.get("title") or type_zh(f.get("finding_type", ""))),
                escape(ent_human(f)), escape(facts), crit_html, escape(steps), q_html,
            )
        )
    findings_section = "".join(cards) if cards else '<p class="empty">未发现需复核的重点项。</p>'
    if rest_count > 0:
        findings_section += '<p class="more">另有 <b>%d</b> 条中风险线索，见下方「按类型汇总」与 <b>findings.csv</b>。</p>' % rest_count

    # ---------- 按类型汇总（含全部线索，避免长尾被忽略）----------
    rows_html = []
    for ft, cnt in type_counts.most_common():
        rows_html.append(
            '<tr><td>%s</td><td class="num">%d</td><td class="num">%d</td><td class="crit">%s</td></tr>' % (
                escape(type_zh(ft)), cnt, high_by_type.get(ft, 0), escape(CRITERIA.get(ft, ""))))
    types_table = (
        '<table class="typetable"><thead><tr><th>线索类型</th><th>条数</th><th>其中高风险</th>'
        '<th>本应如何（制度依据）</th></tr></thead><tbody>%s</tbody></table>'
        % ("".join(rows_html) or '<tr><td colspan="4">无。</td></tr>')
    )

    # ---------- 数据质量 ----------
    dq_parts = ["共 <b>%d</b> 行通过体检" % clean_count]
    if bad_count > 0:
        reasons = []
        bf = output_dir / "bad_rows.csv"
        if bf.exists():
            with bf.open(encoding="utf-8-sig", newline="") as fh:
                for row in _csv.DictReader(fh):
                    for r in row.get("reasons", "").split("；"):
                        r = r.strip()
                        if r:
                            reasons.append(r)
        uniq = list(dict.fromkeys(reasons))[:3]
        dq_parts.append("有 <b>%d</b> 行因数据问题被隔离（%s）" % (bad_count, "、".join(escape(r) for r in uniq) if uniq else "字段异常"))
    else:
        dq_parts.append("无坏行")
    dq_section = "；".join(dq_parts) + "。"

    # ---------- 样式 ----------
    css = """*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f5f3ef;--card:#fff;--ink:#1a1a1a;--muted:#6b6b6b;--faint:#9a9a9a;--line:#e5e1da;--brand:#8b1f2f;--brand-soft:#f7ecec;--red:#b42318;--red-bg:#fdecea;--amber:#b54708;--amber-bg:#fdf3e7;--green:#067647;--green-bg:#eaf7ef;--greyseg:#c9c4ba}
@media(prefers-color-scheme:dark){:root{--bg:#171614;--card:#211f1d;--ink:#f2efea;--muted:#b3ada4;--faint:#7d776e;--line:#33302c;--brand:#e8a0a8;--brand-soft:#2a1e20;--red:#f97066;--red-bg:#3a1e1c;--amber:#fdb022;--amber-bg:#33260f;--green:#4ade80;--green-bg:#13291c;--greyseg:#4a463f}}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;padding:40px 20px;-webkit-font-smoothing:antialiased}
.wrap{max-width:960px;margin:0 auto}
.masthead{display:flex;align-items:center;gap:18px;margin-bottom:22px}
.seal{width:60px;height:60px;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:800;flex:none}
.seal.critical{background:var(--red-bg);color:var(--red)}
.seal.review{background:var(--amber-bg);color:var(--amber)}
.seal.notice{background:var(--brand-soft);color:var(--brand)}
.seal.pass{background:var(--green-bg);color:var(--green)}
.masthead h1{font-size:24px;font-weight:800;letter-spacing:-.01em}
.masthead .sub{font-size:13px;color:var(--muted);margin-top:3px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px;margin-left:8px;vertical-align:middle}
.tag.critical{background:var(--red-bg);color:var(--red)}
.tag.review{background:var(--amber-bg);color:var(--amber)}
.tag.notice{background:var(--brand-soft);color:var(--brand)}
.tag.pass{background:var(--green-bg);color:var(--green)}
h2.sec{font-size:13px;font-weight:800;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:30px 0 12px}
h2.sec .hint{font-weight:400;letter-spacing:0;text-transform:none;font-size:12px;color:var(--faint);margin-left:8px}
.firstpage{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 28px;margin-bottom:8px}
.thesis{border-left:5px solid var(--brand);padding-left:18px;margin-bottom:22px}
.thesis .main{font-size:20px;font-weight:800;line-height:1.55}
.thesis .main b{color:var(--brand)}
.thesis .sub{font-size:14px;color:var(--muted);margin-top:8px}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}
.kpi{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi.alert{border-color:var(--red);background:var(--red-bg)}
.kpi .v{font-size:23px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi.alert .v{color:var(--red)}
.kpi .l{font-size:12px;color:var(--muted);margin-top:3px}
.kpi .h{font-size:11px;color:var(--faint);margin-top:1px}
.riskbar{display:flex;height:14px;border-radius:99px;overflow:hidden;background:var(--line);margin-top:20px}
.seg{display:block;height:100%}
.seg.crit{background:var(--red)}
.seg.med{background:var(--amber)}
.seg.low{background:var(--greyseg)}
.risklegend{display:flex;gap:20px;font-size:13px;color:var(--muted);margin-top:8px;flex-wrap:wrap}
.dot{display:inline-block;width:9px;height:9px;border-radius:99px;margin-right:6px}
.dot.crit{background:var(--red)}
.dot.med{background:var(--amber)}
.dot.low{background:var(--greyseg)}
.nextbox{margin-top:20px;background:var(--brand-soft);border-radius:10px;padding:12px 16px;font-size:14px}
.nextbox b{color:var(--brand)}
.mini{font-size:12px;font-weight:800;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;margin:22px 0 10px}
.top-row{display:flex;align-items:center;gap:10px;padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);text-decoration:none;color:var(--ink);margin-bottom:8px}
.top-row:hover{border-color:var(--brand)}
.top-title{font-weight:700;font-size:14px}
.top-who{color:var(--muted);font-size:13px;margin-left:auto}
.top-amt{color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}
.top-go{color:var(--brand);font-size:13px;font-weight:700;white-space:nowrap}
.links{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.links a{display:block;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 16px;text-decoration:none;color:var(--ink)}
.links a:hover{border-color:var(--brand)}
.lk-name{display:block;font-weight:700;font-size:14px}
.lk-desc{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.finding{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin-bottom:12px}
.finding.critical,.finding.high{border-left:5px solid var(--red)}
.finding.medium{border-left:5px solid var(--amber)}
.finding-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.badge{font-size:12px;font-weight:800;padding:3px 10px;border-radius:6px}
.badge.critical,.badge.high{background:var(--red-bg);color:var(--red)}
.badge.medium{background:var(--amber-bg);color:var(--amber)}
.badge.low{background:var(--brand-soft);color:var(--brand)}
.finding-type{font-size:12px;color:var(--faint)}
.fa-amount{margin-left:auto;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.finding-title{font-size:16px;font-weight:700;margin-bottom:10px}
.finding-who{font-size:14px;color:var(--muted);margin-bottom:6px}
.finding-body{font-size:14px;margin-bottom:4px}
.k{display:inline-block;min-width:44px;color:var(--faint);font-size:12px;margin-right:6px}
.more{font-size:13px;color:var(--muted);margin:4px 0 0}
.empty{font-size:14px;color:var(--muted)}
.typetable{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:13px}
.typetable th{text-align:left;font-size:12px;color:var(--muted);font-weight:700;padding:10px 14px;background:var(--bg);border-bottom:1px solid var(--line)}
.typetable th:nth-child(2),.typetable th:nth-child(3){text-align:right}
.typetable td{padding:9px 14px;border-bottom:1px solid var(--line);vertical-align:top}
.typetable tr:last-child td{border-bottom:none}
.typetable td.num{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
.typetable td.crit{color:var(--muted)}
.note{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 22px;font-size:14px}
.note b{font-weight:700}
.disclaimer{margin-top:26px;background:var(--brand-soft);border:1px solid var(--line);border-radius:12px;padding:16px 22px;font-size:13px;color:var(--muted)}
.disclaimer b{color:var(--brand)}
.foot{text-align:center;color:var(--faint);font-size:12px;margin-top:22px}
@media print{body{background:#fff;padding:0}.firstpage{break-after:page;border:none;padding:0}.finding,.note,.links a,.disclaimer,.typetable{break-inside:avoid}}
@media(max-width:720px){body{padding:20px 12px}.masthead h1{font-size:20px}.kpis{grid-template-columns:1fr 1fr}.links{grid-template-columns:1fr}.finding-title{font-size:15px}.top-who{display:none}.typetable td.crit,.typetable th:nth-child(4){display:none}}"""

    seal_icon = status_zh[:1] if status_class != "pass" else "✓"
    thesis_note_html = ('<div class="sub">%s</div>' % thesis_note) if thesis_note else ""

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>费用报销审计 · 全景报告</title>
<style>%s</style>
</head>
<body>
<div class="wrap">

  <div class="firstpage">
    <div class="masthead">
      <div class="seal %s">%s</div>
      <div>
        <h1>费用报销审计<span class="tag %s">%s</span></h1>
        <div class="sub">expense-audit-v2 v%s · %s · 用时 %s</div>
      </div>
    </div>

    <div class="thesis">
      <div class="main">%s</div>
      %s
    </div>

    <div class="kpis">%s</div>

    %s
    %s

    <div class="mini">最需要先看的 3 条</div>
    %s

    <div class="nextbox"><b>建议下一步：</b>%s</div>

    <div class="mini">查看明细</div>
    <div class="links">%s</div>
  </div>

  <h2 class="sec">重点发现<span class="hint">共 %d 条中高风险，以下列出前 %d 条</span></h2>
  %s

  <h2 class="sec">按类型汇总<span class="hint">含全部 %d 条线索</span></h2>
  %s

  <h2 class="sec">数据质量</h2>
  <div class="note">%s</div>

  <div class="disclaimer">
    <b>业务定位</b>：本报告为<strong>辅助分析</strong>，不替代专业审计判断。工具只做「数据之间对得上」的核对，不验证业务是否真实发生（例：一张合规的客情费发票，无法判断当时是否真的在宴请客户）。<strong>未发现问题 ≠ 没有问题</strong>；最终结论必须由有资质的审计师做出。
  </div>

  <div class="foot">由 expense-audit-v2 v%s 自动生成 · 离线可看 · 无外部依赖</div>
</div>
</body>
</html>
""" % (
        css,
        status_class, seal_icon,
        status_class, status_zh,
        version, date_str, duration_str,
        thesis_main, thesis_note_html,
        kpis_html,
        riskbar, legend,
        top_html,
        next_step,
        links_html,
        len(key), len(shown),
        findings_section,
        len(findings), types_table,
        dq_section,
        version,
    )

    (output_dir / "dashboard.html").write_text(html, encoding="utf-8")

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        raise SystemExit(2)

