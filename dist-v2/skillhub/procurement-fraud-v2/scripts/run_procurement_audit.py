#!/usr/bin/env python3
"""Offline procurement red-flag scanner with traceable evidence."""

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
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "0.2.4"
SKILL = "procurement-fraud-v2"

# 显示层的中文审计术语（finding_type 英文 key、风险优先级、证据强度 → 中文）
FINDING_TYPE_ZH = {
    "shared-bank-account": "供应商共享账户", "shared-phone": "供应商共享电话", "shared-email": "供应商共享邮箱",
    "shared-address": "供应商共享地址", "shared-legal-representative": "供应商共享法人",
    "employee-vendor-shared-bank-account": "员工供应商共享账户", "employee-vendor-shared-phone": "员工供应商共享电话",
    "employee-vendor-shared-email": "员工供应商共享邮箱", "employee-vendor-shared-address": "员工供应商共享地址",
    "price-outlier": "价格异常偏高", "split-order": "拆单采购",
    "bid-text-similarity": "投标文本雷同", "bid-price-subcluster": "报价异常聚集", "bid-price-pattern": "报价模式异常",
    "new-vendor-large-order": "新供应商接大单", "overpayment": "超额付款", "payment-before-order": "付款早于下单",
    "process-order-before-approval": "下单早于审批", "process-order-stale-approval": "审批严重滞后",
    "process-payment-before-approval": "付款早于审批", "process-receipt-before-approval": "收货早于审批",
    "process-receipt-before-order": "收货早于下单", "buyer-vendor-concentration": "采购员供应商集中",
}
PRIORITY_ZH = {"critical": "严重", "high": "高", "medium": "中", "low": "低"}
STRENGTH_ZH = {"strong": "强", "moderate": "中", "weak": "弱"}

SCHEMAS = {
    "vendors": {
        "required": ["vendor_id", "vendor_name"],
        "fields": {
            "vendor_id": ["vendor_id", "supplier_id", "供应商编码", "供应商编号", "供方编号", "厂商编号", "供货商编号"],
            "vendor_name": ["vendor_name", "supplier_name", "供应商名称", "供应商", "供方名称", "厂商名称", "供货商名称"],
            "legal_name": ["legal_name", "company_name", "企业名称", "法定名称", "公司名称", "法人名称"],
            "tax_id": ["tax_id", "tax_number", "统一社会信用代码", "税号", "纳税人识别号", "信用代码"],
            "bank_account": ["bank_account", "bank_no", "银行账号", "收款账号", "账号", "对公账户", "开户账号"],
            "phone": ["phone", "telephone", "联系电话", "手机号", "电话", "联系方式"],
            "email": ["email", "邮箱", "电子邮箱", "邮件"],
            "address": ["address", "registered_address", "地址", "注册地址", "公司地址", "经营地址"],
            "legal_representative": ["legal_representative", "owner_name", "法人", "法定代表人", "法人代表", "负责人"],
            "created_at": ["created_at", "create_date", "创建日期", "成立日期", "注册日期", "建档日期"],
        },
    },
    "purchase_orders": {
        "required": ["po_id", "vendor_id", "buyer_id", "unit_price", "total_amount", "order_date"],
        "fields": {
            "po_id": ["po_id", "order_id", "采购订单号", "订单号", "采购单号", "单据编号", "PO号"],
            "vendor_id": ["vendor_id", "supplier_id", "供应商编码", "供应商编号", "供方编号"],
            "buyer_id": ["buyer_id", "purchaser_id", "采购员", "采购人员编号", "采购员编号", "采购人"],
            "category": ["category", "采购类别", "品类", "物资类别", "商品类别"],
            "item": ["item", "material", "物料", "商品", "项目", "品名", "物资名称"],
            "unit": ["unit", "计量单位", "单位", "规格"],
            "region": ["region", "地区", "区域", "收货地区"],
            "quantity": ["quantity", "qty", "数量", "采购数量"],
            "unit_price": ["unit_price", "price", "单价", "采购单价", "不含税单价"],
            "total_amount": ["total_amount", "amount", "订单金额", "总金额", "采购金额"],
            "currency": ["currency", "币种", "货币"],
            "order_date": ["order_date", "po_date", "订单日期", "采购日期", "下单日期"],
            "approval_date": ["approval_date", "approved_at", "审批日期", "审批完成日期", "核准日期"],
            "receipt_date": ["receipt_date", "received_at", "收货日期", "验收日期", "到货日期", "入库日期", "goods_recv_date"],
        },
    },
    "employees": {
        "required": ["employee_id"],
        "fields": {
            "employee_id": ["employee_id", "emp_id", "员工编号", "工号", "员工ID", "人员编号"],
            "employee_name": ["employee_name", "name", "员工姓名", "姓名", "人员姓名"],
            "department": ["department", "dept", "部门", "所属部门", "组织"],
            "phone": ["phone", "联系电话", "手机号", "电话", "联系方式"],
            "email": ["email", "邮箱", "电子邮箱"],
            "address": ["address", "地址", "家庭地址", "住址"],
            "bank_account": ["bank_account", "银行账号", "工资卡号", "工资账户"],
        },
    },
    "payments": {
        "required": ["payment_id", "po_id", "vendor_id", "amount", "payment_date"],
        "fields": {
            "payment_id": ["payment_id", "付款编号", "支付编号", "流水号", "付款单号"],
            "po_id": ["po_id", "order_id", "采购订单号", "订单号", "采购单号"],
            "vendor_id": ["vendor_id", "supplier_id", "供应商编码", "供应商编号"],
            "amount": ["amount", "payment_amount", "付款金额", "支付金额", "实际付款"],
            "currency": ["currency", "币种", "货币"],
            "payment_date": ["payment_date", "paid_at", "付款日期", "支付日期", "出账日期"],
            "bank_account": ["bank_account", "银行账号", "收款账号", "对公账户"],
        },
    },
    "bids": {
        "required": ["tender_id", "lot_id", "bidder_id", "bid_price"],
        "fields": {
            "tender_id": ["tender_id", "招标编号", "项目编号", "招标项目编号"],
            "lot_id": ["lot_id", "标段编号", "包件编号", "标包编号"],
            "bidder_id": ["bidder_id", "vendor_id", "投标人编号", "供应商编码", "投标单位编号"],
            "bid_price": ["bid_price", "price", "投标报价", "报价", "投标金额"],
            "currency": ["currency", "币种", "货币"],
            "document_path": ["document_path", "file_path", "投标文件路径", "文本路径", "投标书路径"],
            "submitted_at": ["submitted_at", "submission_time", "提交时间", "投标时间"],
        },
    },
}
FILE_CANDIDATES = {
    "vendors": ["vendors.csv", "vendors.xlsx", "vendor_master.csv", "vendor_master.xlsx"],
    "purchase_orders": ["purchase_orders.csv", "purchase_orders.xlsx", "pos.csv", "pos.xlsx"],
    "employees": ["employees.csv", "employees.xlsx"],
    "payments": ["payments.csv", "payments.xlsx"],
    "bids": ["bids.csv", "bids.xlsx", "tenders.csv", "tenders.xlsx"],
}
NUMBER_FIELDS = {"quantity", "unit_price", "total_amount", "amount", "bid_price"}
DATE_FIELDS = {"created_at", "order_date", "approval_date", "receipt_date", "payment_date"}


def text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value))).strip()


def header_key(value: Any) -> str:
    return re.sub(r"[\s_\-./\\]+", "", text(value).lower())


def match_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff@]+", "", text(value).lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def number(value: Any) -> Optional[float]:
    raw = text(value)
    if not raw:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    cleaned = re.sub(r"[^0-9.+-]", "", raw.replace(",", ""))
    try:
        result = float(cleaned)
        if not math.isfinite(result):
            return None
        return -result if negative else result
    except ValueError:
        return None


def date_value(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raw = text(value)
    if not raw:
        return None
    raw = raw.split("T")[0].split(" ")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


# v0.2.0: config.json 合法键清单（白名单），未知键会被拒绝并提示
CONFIG_KEYS = frozenset({
    "config_version", "default_currency",
    "price_outlier_min_group_size", "price_outlier_robust_z",
    "split_window_days",
    "approval_thresholds",
    "bid_similarity_threshold", "bid_ngram_min", "bid_ngram_max",
    "bid_price_close_ratio",
    "concentration_share", "concentration_min_orders",
    "common_template_phrases",
    "whitelists",
    "files", "field_maps",
    # v0.2.0 新增配置
    "order_approval_direction", "same_day_approval_grace",
    "new_vendor_days_threshold", "new_vendor_amount_threshold",
    "order_amount_tolerance",
})


def validate_config(config: Dict[str, Any]) -> None:
    """v0.2.0: 拒绝未知配置键，避免静默忽略用户配置"""
    unknown = set(config.keys()) - CONFIG_KEYS
    if unknown:
        suggestions = []
        for key in unknown:
            similar = [k for k in CONFIG_KEYS if key.lower() in k.lower() or k.lower() in key.lower()]
            if similar:
                suggestions.append("%s（是否想写 %s？）" % (key, " 或 ".join(similar)))
        msg = "config.json 包含未知配置键：%s。" % ", ".join(sorted(unknown))
        if suggestions:
            msg += " 提示：" + "; ".join(suggestions) + "。"
        msg += " 合法键清单：%s" % ", ".join(sorted(CONFIG_KEYS))
        raise ValueError(msg)


def load_json(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        raise ValueError("--config 必传；如不需要自定义阈值，使用 config.json 模板即可")
    with path.open("r", encoding="utf-8-sig") as handle:
        result = json.load(handle)
    if not isinstance(result, dict):
        raise ValueError("config 顶层必须是 JSON 对象")
    validate_config(result)
    return result


def read_table(path: Path) -> Tuple[List[str], List[Dict[str, Any]], Optional[str]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = [text(h) for h in (reader.fieldnames or [])]
            rows = []
            for row_number, source in enumerate(reader, start=2):
                row = {text(k): v for k, v in source.items() if k is not None}
                row.update({"_source_file": path.name, "_source_row": row_number, "_source_sheet": None})
                rows.append(row)
            return headers, rows, None
    if path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("读取 XLSX 需要 openpyxl；请离线安装或另存为 UTF-8 CSV") from exc
        workbook = load_workbook(path, read_only=True, data_only=True)
        worksheet = workbook[workbook.sheetnames[0]]
        values = worksheet.iter_rows(values_only=True)
        first = next(values, None)
        if first is None:
            return [], [], worksheet.title
        headers = [text(value) for value in first]
        rows = []
        for row_number, values_row in enumerate(values, start=2):
            row = {headers[i]: value for i, value in enumerate(values_row) if i < len(headers)}
            row.update({"_source_file": path.name, "_source_row": row_number, "_source_sheet": worksheet.title})
            rows.append(row)
        workbook.close()
        return headers, rows, worksheet.title
    raise ValueError("仅支持 CSV/XLSX：%s" % path)


def resolve_file(root: Path, table: str, config: Dict[str, Any], required: bool) -> Optional[Path]:
    configured = config.get("files", {}).get(table)
    candidates = [configured] if configured else FILE_CANDIDATES[table]
    for candidate in candidates:
        if not candidate:
            continue
        path = (root / candidate).resolve()
        if root != path and root not in path.parents:
            raise ValueError("输入文件不得跳出 input-dir：%s" % candidate)
        if path.is_file():
            return path
    if required:
        raise FileNotFoundError("缺少必需输入 %s；候选文件：%s" % (table, ", ".join(FILE_CANDIDATES[table])))
    return None


def resolve_mapping(table: str, headers: Sequence[str], explicit: Dict[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, List[str]] = defaultdict(list)
    for header in headers:
        normalized[header_key(header)].append(header)
    mapping = {}
    for canonical, aliases in SCHEMAS[table]["fields"].items():
        if canonical in explicit:
            source = text(explicit[canonical])
            if source not in headers:
                raise ValueError("%s 映射 %s -> %s 不存在" % (table, canonical, source))
            mapping[canonical] = source
            continue
        matches = []
        for alias in aliases:
            matches.extend(normalized.get(header_key(alias), []))
        matches = list(dict.fromkeys(matches))
        if len(matches) == 1:
            mapping[canonical] = matches[0]
    missing = [field for field in SCHEMAS[table]["required"] if field not in mapping]
    if missing:
        raise ValueError("%s 缺核心字段映射：%s" % (table, ", ".join(missing)))
    return mapping


def normalize_table(
    table: str, source: Sequence[Dict[str, Any]], mapping: Dict[str, str], default_currency: str, source_hash: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows, bad = [], []
    fields = list(SCHEMAS[table]["fields"].keys())
    for item in source:
        row = {field: text(item.get(mapping.get(field, ""), "")) for field in fields}
        row.update({"_source_file": item["_source_file"], "_source_row": item["_source_row"], "_source_sheet": item["_source_sheet"], "_source_hash": source_hash})
        reasons = []
        for required in SCHEMAS[table]["required"]:
            if not row.get(required):
                reasons.append("%s 为空" % required)
        for field in NUMBER_FIELDS.intersection(fields):
            if not row.get(field) and field not in SCHEMAS[table]["required"]:
                row[field] = None
                continue
            parsed = number(row.get(field))
            if parsed is None:
                if field in SCHEMAS[table]["required"]:
                    reasons.append("%s 无法解析" % field)
                row[field] = None
            else:
                row[field] = round(parsed, 6)
        for field in DATE_FIELDS.intersection(fields):
            if not row.get(field):
                row[field] = None
                continue
            parsed = date_value(row[field])
            if parsed is None and field in SCHEMAS[table]["required"]:
                reasons.append("%s 无法解析" % field)
            row[field] = parsed
        if "currency" in row:
            row["currency"] = (row["currency"] or default_currency).upper()
        if reasons:
            bad.append({"table": table, "source_file": item["_source_file"], "source_row": item["_source_row"], "reasons": "；".join(reasons), "raw_record": json.dumps({k: item.get(v) for k, v in mapping.items()}, ensure_ascii=False, default=str)})
        else:
            rows.append(row)
    return rows, bad


def risk_priority(score: int) -> str:
    return "critical" if score >= 6 else "high" if score >= 4 else "medium" if score >= 2 else "low"


class Builder:
    def __init__(self) -> None:
        self.findings: List[Dict[str, Any]] = []
        self.evidence: List[Dict[str, Any]] = []
        self.cache: Dict[Tuple[str, Any, str], str] = {}

    def row_evidence(self, row: Dict[str, Any], field: str) -> str:
        key = (row["_source_file"], row["_source_row"], field)
        if key in self.cache:
            return self.cache[key]
        evidence_id = "EV-%06d" % (len(self.evidence) + 1)
        self.evidence.append({
            "evidence_id": evidence_id, "source_file": row["_source_file"],
            "source_hash": "sha256:" + row["_source_hash"], "sheet": row.get("_source_sheet"),
            "row": row["_source_row"], "field": field, "value": row.get(field, ""),
            "extraction_method": "normalized", "confidence": 1.0,
        })
        self.cache[key] = evidence_id
        return evidence_id

    def document_evidence(self, path: Path, snippet: str) -> str:
        key = (path.name, None, "document_text")
        if key in self.cache:
            return self.cache[key]
        evidence_id = "EV-%06d" % (len(self.evidence) + 1)
        self.evidence.append({
            "evidence_id": evidence_id, "source_file": path.name,
            "source_hash": "sha256:" + sha256_file(path), "sheet": None, "row": None,
            "field": "document_text", "value": snippet, "extraction_method": "direct_text",
            "confidence": 1.0,
        })
        self.cache[key] = evidence_id
        return evidence_id

    def add(self, finding_type: str, title: str, score: int, strength: str,
            records: Sequence[Dict[str, Any]], fields: Sequence[str], facts: Sequence[str],
            inferences: Sequence[str], questions: Sequence[str], next_steps: Sequence[str],
            factors: Sequence[Dict[str, Any]], extra_refs: Sequence[str] = ()) -> Dict[str, Any]:
        refs = list(extra_refs)
        for record in records:
            refs.extend(self.row_evidence(record, field) for field in fields if field in record)
        entities, seen = [], set()
        candidates = (("vendor", "vendor_id"), ("vendor", "bidder_id"), ("employee", "employee_id"), ("buyer", "buyer_id"), ("lot", "lot_id"))
        for record in records:
            for entity_type, field in candidates:
                value = record.get(field)
                key = (entity_type, value)
                if value and key not in seen:
                    entities.append({"type": entity_type, "id": value})
                    seen.add(key)
        finding = {
            "finding_id": "PROC-%06d" % (len(self.findings) + 1), "skill": SKILL,
            "finding_type": finding_type, "title": title, "risk_priority": risk_priority(score),
            "evidence_strength": strength, "risk_score": score, "risk_factors": list(factors),
            "entities": entities, "facts": list(facts), "inferences": list(inferences),
            "hypotheses": [], "open_questions": list(questions), "evidence_refs": list(dict.fromkeys(refs)),
            "judgment_layer": "线索层（待复核）",  # v0.2.0: 四层标记
            "recommended_next_steps": list(next_steps), "human_review_required": True,
        }
        self.findings.append(finding)
        return finding


def whitelist_keys(config: Dict[str, Any], attribute: str) -> set:
    return {match_key(value) for value in config.get("whitelists", {}).get(attribute, []) if match_key(value)}


def add_shared_attribute_findings(vendors: List[Dict[str, Any]], employees: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder, edges: List[Dict[str, Any]]) -> None:
    settings = {
        "bank_account": (4, "strong"), "phone": (3, "strong"), "email": (3, "strong"),
        "address": (1, "weak"), "legal_representative": (2, "moderate"),
    }
    for attribute, (score, strength) in settings.items():
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        allowed = whitelist_keys(config, attribute)
        for vendor in vendors:
            key = match_key(vendor.get(attribute))
            if key and key not in allowed:
                groups[key].append(vendor)
        for group in groups.values():
            if len(group) < 2:
                continue
            kind = attribute.replace("_", "-")
            finding = builder.add("shared-" + kind, "多个供应商共享%s" % attribute, score, strength, group,
                                  ("vendor_id", attribute),
                                  ["%d 个供应商的归一化 %s 相同" % (len(group), attribute)],
                                  ["该共享属性需要核对主体独立性和主数据准确性"],
                                  ["是否为集团公共信息、园区地址、平台账户或录入错误？"],
                                  ["核对开户资料、工商资料和供应商准入文件"],
                                  [{"factor": "shared_" + attribute, "points": score}])
            for index, left in enumerate(group):
                for right in group[index + 1 :]:
                    edges.append({"source": "vendor:" + left["vendor_id"], "target": "vendor:" + right["vendor_id"], "type": "shares_" + attribute, "evidence_refs": finding["evidence_refs"]})
    employee_settings = {"bank_account": (4, "strong"), "phone": (3, "strong"), "email": (3, "strong"), "address": (1, "weak")}
    for attribute, (score, strength) in employee_settings.items():
        allowed = whitelist_keys(config, attribute)
        by_value: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for vendor in vendors:
            key = match_key(vendor.get(attribute))
            if key and key not in allowed:
                by_value[key].append(vendor)
        for employee in employees:
            key = match_key(employee.get(attribute))
            if not key or key in allowed:
                continue
            for vendor in by_value.get(key, []):
                finding = builder.add("employee-vendor-shared-" + attribute.replace("_", "-"), "员工与供应商共享%s" % attribute,
                                      score, strength, (employee, vendor), ("employee_id", "vendor_id", attribute),
                                      ["员工 %s 与供应商 %s 的归一化 %s 相同" % (employee["employee_id"], vendor["vendor_id"], attribute)],
                                      ["该属性匹配构成潜在未披露关联的复核线索"],
                                      ["是否为公共信息、数据录入错误或已申报关系？"],
                                      ["核对利益冲突申报、员工资料和供应商准入材料"],
                                      [{"factor": "employee_vendor_shared_" + attribute, "points": score}])
                edges.append({"source": "employee:" + employee["employee_id"], "target": "vendor:" + vendor["vendor_id"], "type": "shares_" + attribute, "evidence_refs": finding["evidence_refs"]})


def add_price_findings(pos: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> None:
    minimum = int(config.get("price_outlier_min_group_size", 5))
    threshold = float(config.get("price_outlier_robust_z", 3.5))
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for po in pos:
        subject = match_key(po.get("item")) or ("category:" + match_key(po.get("category")))
        groups[(subject, match_key(po.get("unit")), match_key(po.get("region")), po.get("currency", ""))].append(po)
    for key, group in groups.items():
        if len(group) < minimum:
            continue
        values = [po["unit_price"] for po in group]
        median = statistics.median(values)
        mad = statistics.median(abs(value - median) for value in values)
        if mad == 0:
            # 退化：大部分单价相同（如马甲供应商串通抬价，把中位数拉高）。
            # 用组内最低价作为市场基准，显著高于最低价者视为价格离群。
            min_price = min(values)
            if min_price > 0:
                for po in group:
                    ratio = po["unit_price"] / min_price
                    if ratio >= 1.3:
                        builder.add("price-outlier", "同类采购单价显著偏高", 2, "moderate", (po,),
                                    ("po_id", "vendor_id", "item", "unit", "region", "unit_price"),
                                    ["本单单价 %.2f，是同类采购最低报价 %.2f 的约 %.1f 倍" % (po["unit_price"], min_price, ratio)],
                                    ["多供应商同价且显著高于市场基准，可能指向串标/抬价"],
                                    ["规格、税、运费、质量、交期和采购时间是否可比？"],
                                    ["补齐规格与报价依据，重新确认同类对比口径后复核"],
                                    [{"factor": "price_outlier", "points": 2}])
            continue
        for po in group:
            robust_z = 0.6745 * (po["unit_price"] - median) / mad
            if robust_z > threshold:
                builder.add("price-outlier", "同类采购单价显著偏高", 2, "moderate", (po,),
                            ("po_id", "vendor_id", "item", "unit", "region", "unit_price"),
                            ["本单单价 %.2f，约为同类采购正常水平（约 %.2f）的 %.1f 倍" % (po["unit_price"], median, po["unit_price"] / median)],
                            ["该单价在同类采购中显著偏高"],
                            ["规格、税、运费、质量、交期和采购时间是否可比？"],
                            ["补齐规格与报价依据，重新确认同类对比口径后复核"],
                            [{"factor": "price_outlier", "points": 2}])


def add_split_findings(pos: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> None:
    window_days = int(config.get("split_window_days", 7))
    for threshold in config.get("approval_thresholds", []):
        limit = number(threshold.get("amount"))
        currency = text(threshold.get("currency")).upper()
        if limit is None:
            continue
        groups: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        for po in pos:
            if currency and po["currency"] != currency:
                continue
            groups[(po["buyer_id"], po["vendor_id"], match_key(po.get("category")), po["currency"])].append(po)
        for group in groups.values():
            group.sort(key=lambda po: po["order_date"])
            # v0.2.0: 按月份去重订阅型重复告警（D3）
            reported_months: set = set()
            for index, first in enumerate(group):
                first_date = date.fromisoformat(first["order_date"])
                window = [po for po in group[index:] if (date.fromisoformat(po["order_date"]) - first_date).days <= window_days]
                if len(window) < 2 or any(po["total_amount"] >= limit for po in window):
                    continue
                total = sum(po["total_amount"] for po in window)
                if total <= limit:
                    continue
                # 用首单月份作为去重键
                month_key = first_date.strftime("%Y-%m")
                if month_key in reported_months:
                    continue
                reported_months.add(month_key)
                builder.add("split-order", "短期多笔采购合计超过审批阈值", 3, "moderate", window,
                            ("po_id", "buyer_id", "vendor_id", "category", "total_amount", "order_date"),
                            ["%d 笔单笔低于 %.2f 的订单合计 %.2f" % (len(window), limit, total)],
                            ["该组合符合配置的疑似拆单条件"],
                            ["是否为框架协议分批交付、独立需求或系统拆行？"],
                            ["核对需求申请、审批层级、合同和交付计划"],
                            [{"factor": "split_order", "points": 3, "rule_id": threshold.get("rule_id"), "window_days": window_days}])


def add_process_findings(pos: List[Dict[str, Any]], payments: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> None:
    # v0.2.0: 流程方向配置
    # strict: 仅"先审批后下单"才算合规，其他都是红旗（强信号）
    # forward: "先审批后下单"合规；"先下单后审批"在同日审批豁免下不报
    # either: 双向都不报（最宽松，仅看极长时差）
    direction = config.get("order_approval_direction", "forward")
    same_day_grace = bool(config.get("same_day_approval_grace", True))

    po_by_id = {po["po_id"]: po for po in pos}
    for po in pos:
        order_date = po.get("order_date")
        approval_date = po.get("approval_date")
        receipt_date = po.get("receipt_date")
        if order_date and approval_date and order_date < approval_date:
            # "先下单后审批"——根据 direction 决定如何处理
            order_dt = date.fromisoformat(order_date)
            appr_dt = date.fromisoformat(approval_date)
            gap_days = (appr_dt - order_dt).days
            if direction == "strict":
                # 仅合规：当前不报任何 finding（因为此模式下不视为异常）
                pass
            elif direction == "either":
                # 双向不报：仅在极长时差（如 >30 天）时报弱信号
                if gap_days > 30:
                    builder.add("process-order-stale-approval", "订单日期与审批日期间隔超过 30 天，存在补录嫌疑", 1, "weak", (po,),
                                ("po_id", "order_date", "approval_date"),
                                ["订单日期 %s 与审批日期 %s 间隔 %d 天" % (order_date, approval_date, gap_days)],
                                ["长时差可能意味着补录"], ["是否系统补录或历史数据？"],
                                ["调取审批日志核实实际审批时间"], [{"factor": "order_approval_stale", "points": 1, "gap_days": gap_days}])
            else:
                # forward（默认）：同日审批豁免；跨日才报但为弱信号
                # 注意：不能用 continue——那会跳过下面同一 PO 的收货时序检查（receipt-before-order/approval）
                if not (same_day_grace and gap_days <= 1):
                    builder.add("process-order-before-approval",
                                "采购订单日期早于审批完成日期（跨日方报）" if same_day_grace else "采购订单日期早于审批完成日期",
                                1, "weak", (po,),
                                ("po_id", "order_date", "approval_date"),
                                ["订单日期 %s 早于审批日期 %s，间隔 %d 天" % (order_date, approval_date, gap_days)],
                                ["若非紧急采购授权，存在流程倒置嫌疑"], ["是否为紧急采购、口径差异或事后补录？"],
                                ["调取审批日志和订单创建时间戳"],
                                [{"factor": "order_before_approval", "points": 1, "gap_days": gap_days, "weak_signal": True}])
        if receipt_date and order_date and receipt_date < order_date:
            builder.add("process-receipt-before-order", "收货日期早于采购订单日期", 2, "strong", (po,),
                        ("po_id", "receipt_date", "order_date"), ["收货日期 %s 早于订单日期 %s" % (receipt_date, order_date)],
                        ["可能存在先执行后补单或日期数据错误"], ["是否为历史补录、退换货或接口口径差异？"],
                        ["核对收货单、系统日志和合同生效时间"], [{"factor": "receipt_before_order", "points": 2}])
        # v0.2.0: 收货早于审批（独立规则，无论收货是否也早于下单都报）
        if receipt_date and approval_date and receipt_date < approval_date:
            builder.add("process-receipt-before-approval", "收货日期早于采购审批完成日期", 3, "strong", (po,),
                        ("po_id", "receipt_date", "approval_date"), ["收货 %s 早于审批 %s" % (receipt_date, approval_date)],
                        ["先收货后审批属于流程倒置"], ["是否为紧急采购、紧急收货后补审批？"],
                        ["核对审批日志、收货签收单和合同"],
                        [{"factor": "receipt_before_approval", "points": 3}])
    for payment in payments:
        po = po_by_id.get(payment["po_id"])
        if po and po.get("approval_date") and payment["payment_date"] < po["approval_date"]:
            builder.add("process-payment-before-approval", "付款日期早于采购审批完成日期", 3, "strong", (payment, po),
                        ("payment_id", "po_id", "payment_date", "approval_date", "amount"),
                        ["付款日期 %s 早于关联 PO 审批日期 %s" % (payment["payment_date"], po["approval_date"])],
                        ["付款流程顺序需要复核"], ["是否为预付款、紧急授权、补录或日期口径差异？"],
                        ["核对付款审批、银行流水和合同预付款条款"], [{"factor": "payment_before_approval", "points": 3}])


def add_concentration_findings(pos: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> None:
    share_limit = float(config.get("concentration_share", 0.7))
    minimum_orders = int(config.get("concentration_min_orders", 3))
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for po in pos:
        groups[po["buyer_id"]].append(po)
    for buyer, group in groups.items():
        total = sum(po["total_amount"] for po in group)
        by_vendor: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for po in group:
            by_vendor[po["vendor_id"]].append(po)
        for vendor, subset in by_vendor.items():
            share = sum(po["total_amount"] for po in subset) / total if total else 0
            if len(subset) >= minimum_orders and share >= share_limit:
                builder.add("buyer-vendor-concentration", "采购员对单一供应商的金额集中度较高", 1, "moderate", subset,
                            ("po_id", "buyer_id", "vendor_id", "total_amount"),
                            ["采购员 %s 的 %d 笔订单中，供应商 %s 金额占比 %.2f%%" % (buyer, len(group), vendor, share * 100)],
                            ["该集中度达到配置的复核阈值"], ["是否存在独家技术、框架协议或地区供给限制？"],
                            ["查看供应商选择依据、市场询价和合同覆盖范围"],
                            [{"factor": "buyer_vendor_concentration", "points": 1, "share": round(share, 6)}])


def ngrams(value: str, minimum: int, maximum: int) -> Counter:
    compact = re.sub(r"\s+", "", value)
    result: Counter = Counter()
    for size in range(minimum, maximum + 1):
        result.update(compact[index:index + size] for index in range(max(len(compact) - size + 1, 0)))
    return result


def tfidf_vectors(documents: Sequence[str], minimum: int, maximum: int) -> List[Dict[str, float]]:
    counts = [ngrams(document, minimum, maximum) for document in documents]
    document_frequency = Counter()
    for count in counts:
        document_frequency.update(count.keys())
    total = len(documents)
    vectors = []
    for count in counts:
        length = sum(count.values()) or 1
        vectors.append({term: (frequency / length) * (math.log((1 + total) / (1 + document_frequency[term])) + 1) for term, frequency in count.items()})
    return vectors


def cosine(left: Dict[str, float], right: Dict[str, float]) -> float:
    dot = sum(value * right.get(term, 0.0) for term, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def safe_document(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root != path and root not in path.parents:
        raise ValueError("document_path 不得跳出 input-dir：%s" % relative)
    if path.suffix.lower() not in (".txt", ".md"):
        raise ValueError("核心文本比较仅支持 .txt/.md：%s" % relative)
    return path


def add_bid_findings(root: Path, bids: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> List[str]:
    warnings = []
    minimum, maximum = int(config.get("bid_ngram_min", 2)), int(config.get("bid_ngram_max", 5))
    threshold = float(config.get("bid_similarity_threshold", 0.78))
    templates = [text(value) for value in config.get("common_template_phrases", []) if text(value)]
    docs, doc_bids, paths = [], [], []
    for bid in bids:
        if not bid.get("document_path"):
            continue
        try:
            path = safe_document(root, bid["document_path"])
            raw = path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            warnings.append("投标文本跳过 %s：%s" % (bid.get("document_path"), exc))
            continue
        normalized = unicodedata.normalize("NFKC", raw).lower()
        for phrase in templates:
            normalized = normalized.replace(phrase.lower(), "")
        if len(re.sub(r"\s+", "", normalized)) < 20:
            warnings.append("投标文本过短：%s" % bid["document_path"])
            continue
        docs.append(normalized)
        doc_bids.append(bid)
        paths.append(path)
    if docs:
        vectors = tfidf_vectors(docs, minimum, maximum)
        for left_index, left in enumerate(doc_bids):
            for right_index in range(left_index + 1, len(doc_bids)):
                right = doc_bids[right_index]
                if left["lot_id"] != right["lot_id"]:
                    continue
                score = cosine(vectors[left_index], vectors[right_index])
                if score >= threshold:
                    refs = [builder.document_evidence(paths[left_index], docs[left_index][:180]), builder.document_evidence(paths[right_index], docs[right_index][:180])]
                    builder.add("bid-text-similarity", "同一标段投标文本高度相似，需回到原文复核", 2, "moderate", (left, right),
                                ("tender_id", "lot_id", "bidder_id", "document_path"),
                                ["字符级 TF-IDF 余弦相似度 %.6f，高于本次配置阈值 %.6f" % (score, threshold)],
                                ["该文件对构成高相似复核线索，不等于串标认定"],
                                ["相同内容是招标公共模板还是投标人自行撰写？"],
                                ["定位相似片段，并核对文件元数据、报价、联系人和保证金来源"],
                                [{"factor": "bid_text_similarity", "points": 2, "similarity": round(score, 6), "threshold": threshold, "ngram_range": [minimum, maximum]}], refs)
    close_ratio = float(config.get("bid_price_close_ratio", 0.01))
    lots: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for bid in bids:
        lots[bid["lot_id"]].append(bid)
    for lot, group in lots.items():
        prices = [bid["bid_price"] for bid in group]
        if len(prices) >= 3:
            median = statistics.median(prices)
            spread = (max(prices) - min(prices)) / median if median else 0
            if spread <= close_ratio:
                builder.add("bid-price-pattern", "同一标段多家报价异常接近", 1, "moderate", group,
                            ("tender_id", "lot_id", "bidder_id", "bid_price"),
                            ["标段 %s 的 %d 个报价极差/中位数为 %.6f" % (lot, len(group), spread)],
                            ["报价接近是弱红旗，需要结合计价规则解释"],
                            ["是否存在统一预算、限价、税率或标准计价公式？"],
                            ["核对报价明细、编制痕迹和提交信息"],
                            [{"factor": "bid_price_close", "points": 1, "spread_ratio": round(spread, 6)}])
            # v0.2.0: 子簇检测——全标段极差被拉大时，检查子簇
            # 把极差 < close_ratio * 3 的相邻报价组合识别为"疑似子簇"
            sorted_prices = sorted(prices)
            sub_clusters = []
            current_cluster = [sorted_prices[0]]
            for p in sorted_prices[1:]:
                if (p - min(current_cluster)) / max(min(current_cluster), 0.01) <= close_ratio * 3:
                    current_cluster.append(p)
                else:
                    if len(current_cluster) >= 3:
                        sub_clusters.append(current_cluster)
                    current_cluster = [p]
            if len(current_cluster) >= 3:
                sub_clusters.append(current_cluster)
            for cluster in sub_clusters:
                cluster_median = statistics.median(cluster)
                cluster_spread = (max(cluster) - min(cluster)) / cluster_median if cluster_median else 0
                if cluster_spread <= close_ratio * 2:
                    cluster_bids = [bid for bid in group if bid["bid_price"] in cluster]
                    if cluster_bids and not any(
                        f.get("entities", [{}])[0].get("id") == lot and f.get("entities", [{}])[0].get("type") == "lot"
                        for f in builder.findings
                    ):
                        builder.add("bid-price-subcluster", "同一标段内报价存在接近子簇", 2, "moderate", cluster_bids,
                                    ("tender_id", "lot_id", "bidder_id", "bid_price"),
                                    ["标段 %s 内 %d 个报价形成接近子簇，极差/中位数 %.6f" % (lot, len(cluster), cluster_spread)],
                                    ["可能是真实竞争组 vs 围标组的混合报价"],
                                    ["子簇内部是否为关联公司或同一投标代理？"],
                                    ["核对子簇投标人背景、保证金来源和文件元数据"],
                                    [{"factor": "bid_price_subcluster", "points": 2, "cluster_size": len(cluster), "spread_ratio": round(cluster_spread, 6)}])

    return warnings


def add_vendor_age_findings(vendors: List[Dict[str, Any]], pos: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> None:
    """v0.2.0: 新成立供应商接大单"""
    days_threshold = int(config.get("new_vendor_days_threshold", 90))
    amount_threshold = float(config.get("new_vendor_amount_threshold", 20000))  # v0.2.0: 默认 20000（原 50000 偏严）

    po_by_vendor = defaultdict(list)
    for po in pos:
        po_by_vendor[po["vendor_id"]].append(po)

    for vendor in vendors:
        vendor_id = vendor.get("vendor_id")
        created_at = vendor.get("created_at")
        if not (vendor_id and created_at):
            continue
        try:
            created_date = date.fromisoformat(created_at)
        except (ValueError, TypeError):
            continue
        # 找该供应商的首笔订单
        vendor_pos = po_by_vendor.get(vendor_id, [])
        first_po = min(vendor_pos, key=lambda po: po.get("order_date", "9999-12-31"), default=None)
        if first_po is None or not first_po.get("order_date"):
            continue
        try:
            first_order_date = date.fromisoformat(first_po["order_date"])
        except (ValueError, TypeError):
            continue
        # 新供应商 = 从「成立日期」到「首单日期」在阈值内（用数据自身时间轴，不用系统时钟，避免非确定性）
        age_days = (first_order_date - created_date).days
        if age_days < 0 or age_days > days_threshold:
            continue
        first_amount = first_po.get("total_amount", 0) or 0
        if first_amount < amount_threshold:
            continue
        builder.add("new-vendor-large-order", "新成立供应商短期内接大单", 3, "strong", (vendor, first_po),
                    ("vendor_id", "vendor_name", "created_at", "po_id", "total_amount", "order_date"),
                    ["供应商 %s 成立于 %s，%d 天后即接到首单金额 %.2f（超过阈值 %.2f）" % (
                        vendor_id, created_at, age_days, first_amount, amount_threshold)],
                    ["新供应商缺少合作历史，首单金额过大需重点关注"],
                    ["是否为关系户、走账或合规盲区？"],
                    ["调取供应商背景、关联关系、招标过程和资金来源"],
                    [{"factor": "new_vendor_large_order", "points": 3, "age_days": age_days, "amount": first_amount}])


def add_payment_findings(pos: List[Dict[str, Any]], payments: List[Dict[str, Any]], config: Dict[str, Any], builder: Builder) -> None:
    """v0.2.0: 付款额 ≠ 订单额（超额付款）+ 付款早于下单"""
    tolerance = float(config.get("order_amount_tolerance", 0.01))
    po_by_id = {po["po_id"]: po for po in pos}
    for payment in payments:
        po = po_by_id.get(payment["po_id"])
        if not po:
            continue
        po_amount = po.get("total_amount", 0) or 0
        pay_amount = payment.get("amount", 0) or 0
        # 超额付款
        if pay_amount > po_amount * (1 + tolerance):
            over = pay_amount - po_amount
            builder.add("overpayment", "付款金额超过订单金额", 3, "strong", (payment, po),
                        ("payment_id", "po_id", "amount", "po_amount"),
                        ["付款 %.2f 超过订单 %.2f，多付 %.2f" % (pay_amount, po_amount, over)],
                        ["超付可能涉及利益输送"],
                        ["是否为合同变更、运费、税费或事后补款？"],
                        ["核对合同条款、变更审批和银行流水"],
                        [{"factor": "overpayment", "points": 3, "over_amount": round(over, 2)}])
        # 付款早于下单
        po_order_date = po.get("order_date")
        pay_date = payment.get("payment_date")
        if po_order_date and pay_date and pay_date < po_order_date:
            builder.add("payment-before-order", "付款日期早于采购订单日期", 3, "strong", (payment, po),
                        ("payment_id", "po_id", "payment_date", "order_date"),
                        ["付款 %s 早于订单 %s" % (pay_date, po_order_date)],
                        ["付款先于订单通常是重大异常"],
                        ["是否为预付款、紧急授权或日期口径差异？"],
                        ["核对付款审批、银行流水和合同预付款条款"],
                        [{"factor": "payment_before_order", "points": 3}])


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def validate(builder: Builder) -> None:
    evidence_ids = {item["evidence_id"] for item in builder.evidence}
    for finding in builder.findings:
        if not finding["evidence_refs"] or not set(finding["evidence_refs"]).issubset(evidence_ids):
            raise ValueError("finding %s 的 evidence 引用不完整" % finding["finding_id"])
        if not finding["human_review_required"]:
            raise ValueError("finding 必须要求人工复核")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--config", type=Path, required=True, help="必传；含审批阈值、相似度阈值、白名单等参数")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-env", action="store_true")
    args = parser.parse_args(argv)
    if args.check_env:
        try:
            import openpyxl
            xlsx = "available (%s)" % openpyxl.__version__
        except ImportError:
            xlsx = "unavailable; CSV/TXT mode still works"
        print(json.dumps({"python": sys.version.split()[0], "recommended": ">=3.10", "xlsx_support": xlsx, "network_required": False}, ensure_ascii=False))
        return 0
    if not args.input_dir or not args.output:
        parser.error("正式运行需要 --input-dir 和 --output")
    root = args.input_dir.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("输出目录非空；请使用新目录：%s" % output)
    output.mkdir(parents=True, exist_ok=True)
    config = load_json(args.config.resolve() if args.config else None)
    default_currency = text(config.get("default_currency", "CNY")).upper()
    started = datetime.now(timezone.utc)
    tables: Dict[str, List[Dict[str, Any]]] = {}
    mappings, input_files, quality, bad_rows = {}, [], {}, []
    for table in SCHEMAS:
        path = resolve_file(root, table, config, table in ("vendors", "purchase_orders"))
        if path is None:
            tables[table] = []
            quality[table] = {"status": "not_provided", "rows": 0, "valid_rows": 0, "bad_rows": 0}
            continue
        digest = sha256_file(path)
        headers, source_rows, sheet = read_table(path)
        mapping = resolve_mapping(table, headers, config.get("field_maps", {}).get(table, {}))
        rows, bad = normalize_table(table, source_rows, mapping, default_currency, digest)
        tables[table] = rows
        mappings[table] = mapping
        bad_rows.extend(bad)
        input_files.append({"path": path.name, "sha256": digest, "sheet": sheet, "table": table})
        quality[table] = {"status": "loaded", "rows": len(source_rows), "valid_rows": len(rows), "bad_rows": len(bad), "mapping": mapping}

    builder, edges = Builder(), []
    add_shared_attribute_findings(tables["vendors"], tables["employees"], config, builder, edges)
    add_price_findings(tables["purchase_orders"], config, builder)
    add_split_findings(tables["purchase_orders"], config, builder)
    add_process_findings(tables["purchase_orders"], tables["payments"], config, builder)
    add_concentration_findings(tables["purchase_orders"], config, builder)
    add_vendor_age_findings(tables["vendors"], tables["purchase_orders"], config, builder)
    add_payment_findings(tables["purchase_orders"], tables["payments"], config, builder)
    warnings = add_bid_findings(root, tables["bids"], config, builder)

    for po in tables["purchase_orders"]:
        refs = [builder.row_evidence(po, "po_id"), builder.row_evidence(po, "total_amount")]
        edges.append({"source": "buyer:" + po["buyer_id"], "target": "vendor:" + po["vendor_id"], "type": "purchased_from", "amount": po["total_amount"], "currency": po["currency"], "evidence_refs": refs})
    nodes, node_seen = [], set()
    for node_type, table, field in (("vendor", "vendors", "vendor_id"), ("employee", "employees", "employee_id"), ("buyer", "purchase_orders", "buyer_id")):
        for row in tables[table]:
            node_id = node_type + ":" + row[field]
            if node_id not in node_seen:
                nodes.append({"id": node_id, "type": node_type, "label": row[field]})
                node_seen.add(node_id)
    validate(builder)

    for table, rows in tables.items():
        if rows:
            fields = list(SCHEMAS[table]["fields"].keys()) + ["_source_file", "_source_row", "_source_sheet"]
            write_csv(output / ("normalized_%s.csv" % table), rows, fields)
    write_csv(output / "bad_rows.csv", bad_rows, ("table", "source_file", "source_row", "reasons", "raw_record"))
    flat = [{
        "finding_id": f["finding_id"], "finding_type": f["finding_type"], "title": f["title"],
        "risk_priority": PRIORITY_ZH.get(f["risk_priority"], f["risk_priority"]),
        "evidence_strength": STRENGTH_ZH.get(f["evidence_strength"], f["evidence_strength"]),
        "risk_score": f["risk_score"], "entities": json.dumps(f["entities"], ensure_ascii=False),
        "evidence_refs": "|".join(f["evidence_refs"]),
    } for f in builder.findings]
    write_csv(output / "findings.csv", flat, ("finding_id", "finding_type", "title", "risk_priority", "evidence_strength", "risk_score", "entities", "evidence_refs"))
    write_jsonl(output / "findings.jsonl", builder.findings)
    write_jsonl(output / "evidence.jsonl", builder.evidence)
    (output / "relationship_graph.json").write_text(json.dumps({"schema_version": VERSION, "nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    entity_findings: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for finding in builder.findings:
        for entity in finding["entities"]:
            if entity["type"] == "vendor":
                entity_findings[entity["id"]].append(finding)
    candidates = []
    for vendor, findings in entity_findings.items():
        types = {f["finding_type"] for f in findings}
        if len(types) >= 2 and any(f["risk_priority"] in ("high", "critical") for f in findings):
            candidates.append((vendor, findings))
    if candidates:
        vendor, findings = max(candidates, key=lambda item: (len({f["finding_type"] for f in item[1]}), len(item[1])))
        handoff = {
            "schema_version": VERSION, "status": "recommended", "source_skill": SKILL,
            "finding_ids": [f["finding_id"] for f in findings], "entities": [{"type": "vendor", "id": vendor}],
            "reason_for_handoff": "多个独立采购红旗指向同一供应商，建议由有权人员决定是否进入调查辅助流程",
            "known_facts": list(dict.fromkeys(fact for f in findings for fact in f["facts"]))[:20],
            "hypotheses": ["这些红旗可能有共同原因，也可能由多个独立且合理的业务情形造成"],
            "recommended_scope": ["仅围绕列示 finding 和关联期间核验主数据、审批、报价、付款与利益冲突申报"],
            "human_approval_required": True,
        }
    else:
        handoff = {"schema_version": VERSION, "status": "not_recommended", "source_skill": SKILL, "finding_ids": [], "entities": [], "reason_for_handoff": "未达到多类独立红旗的建议条件", "known_facts": [], "hypotheses": [], "recommended_scope": [], "human_approval_required": True}
    (output / "investigation_handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    skipped = [table + " 模块：未提供输入" for table in ("employees", "payments", "bids") if not tables[table]]
    if not config.get("approval_thresholds"):
        skipped.append("split-order：未提供 approval_thresholds")
    quality_lines = ["# 采购数据质量报告", "", "> 技术附录：本文件是数据体检的机器记录（字段映射、空值率等），供复核追溯，不是审计结论。", "", "- Bad rows 合计：%d" % len(bad_rows), "", "## 各表", ""]
    quality_lines.extend("- `%s`: `%s`" % (table, json.dumps(value, ensure_ascii=False)) for table, value in quality.items())
    if warnings or skipped:
        quality_lines.extend(["", "## 警告与跳过", ""] + ["- " + item for item in warnings + skipped])
    (output / "data_quality.md").write_text("\n".join(quality_lines) + "\n", encoding="utf-8")

    # 类型/优先级显示层中文化（英文 key 保留在 findings.jsonl 供机器比对）
    counts = Counter(FINDING_TYPE_ZH.get(f["finding_type"], f["finding_type"]) for f in builder.findings)
    priorities = Counter(PRIORITY_ZH.get(f["risk_priority"], f["risk_priority"]) for f in builder.findings)
    summary = [
        "# 采购红旗确定性摘要", "", "- Findings：%d；Evidence：%d。" % (len(builder.findings), len(builder.evidence)),
        "- 风险优先级：`%s`" % json.dumps(dict(priorities), ensure_ascii=False, sort_keys=True),
        "- 类型：`%s`" % json.dumps(dict(counts), ensure_ascii=False, sort_keys=True),
        "- 调查移交建议：`%s`。" % handoff["status"], "",
        "> 共享属性、价格离群、流程异常和文本相似均为复核线索。它们不能单独或自动证明串标、利益输送或舞弊。", "",
        "## 建议复核顺序", "", "1. 先核验共享银行账号和员工—供应商强属性是否准确及已申报。",
        "2. 再回到 PO、审批、付款和投标原文检查同一主体上的多模块组合。",
        "3. 主动核对公共地址、模板、独家供应、紧急采购和系统补录等替代解释。", "",
        "## 输出文件", "", "**审计结论（给人看）**：summary.md、findings.csv、findings.jsonl、investigation_handoff.json", "",
        "**技术审计轨迹（复核追溯用，非审计结论）**：data_quality.md、run_manifest.json、各标准化数据表、bad_rows.csv、evidence.jsonl、relationship_graph.json", "",
        "## 这个工具好用吗？（可选反馈）", "",
        "如果它对你有帮助，可以对 AI 说一句「**做匿名反馈**」，它会把这次运行的匿名统计（筛查出几类问题、耗时）发给作者，帮作者改进工具。", "",
        "**不含供应商名称、员工、银行账号、金额**；核心分析全程在你本地、不联网。你不说，它就不会发。", "",
        "想反馈时，把这句发给 AI 即可（可附意见，如「速度偏慢」）：", "",
        "> 做匿名反馈",
    ]
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("提示：如果本工具有帮助，可以对我说「做匿名反馈」——只发送匿名统计（不含供应商名称/员工/银行账号/金额），核心分析始终在本地、不联网。", file=sys.stderr)

    script = Path(__file__).resolve()
    if args.config:
        input_files.append({"path": args.config.name, "sha256": sha256_file(args.config.resolve()), "table": "config"})
    manifest = {
        "run_id": "PROC-%s-%s" % (started.strftime("%Y%m%dT%H%M%SZ"), hashlib.sha256(json.dumps(input_files, sort_keys=True).encode()).hexdigest()[:8]),
        "skill": SKILL, "skill_version": VERSION, "started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
        "input_files": input_files, "field_mappings": mappings,
        "parameters": {key: config.get(key) for key in ("config_version", "default_currency", "price_outlier_min_group_size", "price_outlier_robust_z", "split_window_days", "approval_thresholds", "bid_similarity_threshold", "bid_ngram_min", "bid_ngram_max", "bid_price_close_ratio", "concentration_share", "concentration_min_orders", "common_template_phrases", "whitelists")},
        "scripts": {script.name: "sha256:" + sha256_file(script)}, "warnings": warnings, "skipped_modules": skipped,
        "network_access": False,
        "outputs": sorted(path.name for path in output.iterdir()) + ["run_manifest.json", "dashboard.html"],
        "note": "技术审计轨迹：记录本次运行的机器可追溯信息（哈希、字段映射、参数等），供复核追溯，不是审计结论。",
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        build_dashboard_html(manifest, builder.findings, len(bad_rows), handoff, {"nodes": nodes, "edges": edges}, output)
    except Exception as _e:
        print("WARNING: dashboard.html generation failed: %s" % _e, file=sys.stderr)
    print(json.dumps({"output": str(output), "findings": len(builder.findings), "evidence": len(builder.evidence), "handoff": handoff["status"]}, ensure_ascii=False))
    return 0


DASHBOARD_CSS = """*{box-sizing:border-box;margin:0;padding:0}
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
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
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
.handoff{margin-top:20px;background:var(--brand-soft);border-radius:10px;padding:12px 16px;font-size:14px}
.handoff .hl{font-weight:800;color:var(--brand);margin-right:8px}
.handoff .sub{color:var(--muted);font-size:13px;margin-top:2px}
.nextbox{margin-top:14px;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 16px;font-size:14px}
.nextbox b{color:var(--brand)}
.mini{font-size:12px;font-weight:800;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;margin:22px 0 10px}
.top-row{display:flex;align-items:center;gap:10px;padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);text-decoration:none;color:var(--ink);margin-bottom:8px}
.top-row:hover{border-color:var(--brand)}
.top-title{font-weight:700;font-size:14px}
.top-who{color:var(--muted);font-size:13px;margin-left:auto}
.top-go{color:var(--brand);font-size:13px;font-weight:700;white-space:nowrap}
.links{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.links a{display:block;background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:12px 16px;text-decoration:none;color:var(--ink)}
.links a:hover{border-color:var(--brand)}
.lk-name{display:block;font-weight:700;font-size:14px}
.lk-desc{display:block;font-size:12px;color:var(--muted);margin-top:2px}
.finding{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin-bottom:12px}
.finding.critical,.finding.high{border-left:5px solid var(--red)}
.finding.medium{border-left:5px solid var(--amber)}
.finding.low{border-left:5px solid var(--faint)}
.finding-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.badge{font-size:12px;font-weight:800;padding:3px 10px;border-radius:6px}
.badge.critical,.badge.high{background:var(--red-bg);color:var(--red)}
.badge.medium{background:var(--amber-bg);color:var(--amber)}
.badge.low{background:var(--brand-soft);color:var(--brand)}
.finding-type{font-size:12px;color:var(--faint)}
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
@media print{body{background:#fff;padding:0}.firstpage{break-after:page;border:none;padding:0}.finding,.note,.links a,.disclaimer,.typetable,.handoff{break-inside:avoid}}
@media(max-width:720px){body{padding:20px 12px}.masthead h1{font-size:20px}.kpis{grid-template-columns:1fr 1fr}.links{grid-template-columns:1fr}.finding-title{font-size:15px}.top-who{display:none}.typetable td.crit,.typetable th:nth-child(4){display:none}}"""


def build_dashboard_html(manifest, findings, bad_count, handoff, graph, output_dir):
    """采购舞弊红旗全景报告（面向审计/采购经理，全中文，先说问题）。

    结构对齐审计报告最佳实践：
      第一屏（执行摘要，可独立看懂）：
        论点结论 → 调查移交建议 → 关键指标 → 风险分布 → 最需要先看的 3 条 → 明细入口
      往下：重点红旗逐条（现象/依据/建议/待澄清）→ 按类型汇总 → 关系图 → 数据质量 → 业务定位
    """
    from collections import Counter
    from html import escape

    PRIORITY_ZH = {"critical": "严重", "high": "高风险", "medium": "中风险", "low": "低风险"}
    ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # 制度依据：仅用于展示「本应如何」，不改动任何判定逻辑
    CRITERIA = {
        "shared-bank-account": "不同供应商不应共用同一银行账号（可能指向同一实际控制人或代持）。",
        "shared-phone": "不同供应商不应共用同一联系电话。",
        "shared-email": "不同供应商不应共用同一邮箱。",
        "shared-address": "不同供应商共用地址需确认是否为同一园区、集团或代理注册（白名单除外）。",
        "shared-legal-representative": "不同供应商共用法定代表人，需确认是否存在关联。",
        "employee-vendor-shared-bank-account": "员工不应与供应商共用银行账号（利益冲突红线）。",
        "employee-vendor-shared-phone": "员工不应与供应商共用联系电话。",
        "employee-vendor-shared-email": "员工不应与供应商共用邮箱。",
        "employee-vendor-shared-address": "员工与供应商共用地址需确认是否已申报利益冲突。",
        "price-outlier": "同类采购单价不应显著高于可比较水平。",
        "split-order": "不得为规避审批阈值而拆分订单。",
        "bid-text-similarity": "不同投标人的投标文本不应高度雷同。",
        "bid-price-subcluster": "同一标段的报价不应异常聚集。",
        "bid-price-pattern": "报价模式不应呈现异常规律。",
        "new-vendor-large-order": "新成立供应商承接大额订单需有合理的资质与能力说明。",
        "overpayment": "付款金额不应超过订单/发票金额。",
        "payment-before-order": "付款不应早于下单。",
        "process-order-before-approval": "采购订单应先审批后下单。",
        "process-order-stale-approval": "审批不应严重滞后于下单时间。",
        "process-payment-before-approval": "付款不应早于审批完成。",
        "process-receipt-before-approval": "收货不应早于审批完成。",
        "process-receipt-before-order": "收货不应早于订单日期。",
        "buyer-vendor-concentration": "同一采购员对单一供应商的份额不应过度集中。",
    }

    def tzh(ft):
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
        status_class, status_label, status_zh = "pass", "PASS", "未见明显红旗"

    # ---------- 时间 / 版本 ----------
    duration_str, date_str = "—", "—"
    try:
        s = datetime.fromisoformat(manifest["started_at"])
        e = datetime.fromisoformat(manifest["finished_at"])
        duration_str = "%.1f 秒" % (e - s).total_seconds()
        date_str = s.strftime("%Y-%m-%d %H:%M")
    except (KeyError, ValueError):
        pass
    version = manifest.get("skill_version", "?")

    # ---------- 聚合 ----------
    vens = sorted({e["id"] for f in findings for e in f.get("entities", []) if e.get("type") == "vendor"})
    buyers = sorted({e["id"] for f in findings for e in f.get("entities", []) if e.get("type") == "buyer"})
    type_counts = Counter(f.get("finding_type", "?") for f in findings)
    high_by_type = Counter(f.get("finding_type", "?") for f in findings
                           if f.get("risk_priority") in ("critical", "high"))
    top_type, top_cnt = (type_counts.most_common(1)[0] if type_counts else ("", 0))

    # ---------- 论点句 ----------
    if status_class == "critical":
        thesis_main = "发现 <b>%d</b> 条红旗线索，其中 <b>%d</b> 条高风险，建议优先核对。" % (len(findings), critical + high)
    elif status_class == "review":
        thesis_main = "发现 <b>%d</b> 条红旗线索（%d 条中风险），建议按供应商与采购员归并后逐条确认。" % (len(findings), medium)
    elif status_class == "notice":
        thesis_main = "发现 <b>%d</b> 条提示性红旗，未见高风险线索。" % len(findings)
    else:
        thesis_main = "本次未发现明显红旗，可作为进一步分析的可靠基线。"

    thesis_note = ""
    if top_cnt and len(findings) >= 5 and top_cnt >= max(3, int(len(findings) * 0.3)):
        thesis_note = "其中数量最多的是「%s」共 %d 条，建议优先按此类型归并复核。" % (escape(tzh(top_type)), top_cnt)

    # ---------- 调查移交建议（放在第一屏，属于要人拍板的事）----------
    hs = handoff.get("status") if isinstance(handoff, dict) else None
    if hs == "recommended":
        handoff_html = ('<div class="handoff"><span class="hl">调查移交建议</span>'
                        '建议移交内部调查（%d 条红旗、%d 个关联主体）——需人工批准后方可启动。'
                        '<div class="sub">理由：%s</div></div>') % (
            len(handoff.get("finding_ids", [])), len(handoff.get("entities", [])),
            escape(handoff.get("reason_for_handoff", "")))
    else:
        handoff_html = '<div class="handoff"><span class="hl">调查移交建议</span>暂不建议移交（未达到多类独立红旗的建议条件）。</div>'

    # ---------- 关键指标 ----------
    kpi_items = [
        ("红旗线索", "%d" % len(findings), "等待人工确认", ""),
        ("高风险", "%d" % (critical + high), "建议优先处理" if critical + high else "无", "alert" if critical + high else ""),
        ("涉及供应商", "%d" % len(vens), "去重后家数", ""),
        ("涉及采购员", "%d" % len(buyers), "去重后人数", ""),
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
            if t == "vendor":
                out.append("供应商 %s" % i)
            elif t == "buyer":
                out.append("采购员 %s" % i)
            elif t == "employee":
                out.append("员工 %s" % i)
            else:
                out.append(str(i))
        return "、".join(out[:limit]) if out else "（无明确对象）"

    top_rows = []
    for f in ordered[:3]:
        pr = f.get("risk_priority", "low")
        top_rows.append(
            '<a class="top-row" href="#%s">'
            '<span class="badge badge-%s">%s</span>'
            '<span class="top-title">%s</span>'
            '<span class="top-who">%s</span><span class="top-go">查看 →</span></a>' % (
                escape(str(f.get("finding_id", ""))), pr, PRIORITY_ZH.get(pr, pr),
                escape(f.get("title") or tzh(f.get("finding_type", ""))),
                escape(ent_human(f))))
    top_html = "".join(top_rows) if top_rows else '<p class="empty">未发现重点项。</p>'

    # ---------- 建议下一步 ----------
    if critical + high > 0:
        next_step = "先核对 <b>%d</b> 条高风险红旗的真实性（每条已附证据编号）；再按供应商与采购员归并，回到 PO、审批、付款与投标原文复核。" % (critical + high)
    elif medium > 0:
        next_step = "按供应商与采购员归并后逐条确认；优先核对共享账户、流程倒置与金额异常的替代解释。"
    elif findings:
        next_step = "以抽样确认为主；如需逐一查看，请打开 findings.csv。"
    else:
        next_step = "无需处理；可作为后续比对的基线。"

    # ---------- 明细入口 ----------
    links = [
        ("findings.csv", "全部红旗明细（按风险排序，Excel 可开）"),
        ("summary.md", "完整结论与建议复核顺序"),
        ("investigation_handoff.json", "调查移交建议（如需）"),
        ("relationship_graph.json", "供应商关系图数据"),
    ]
    links_html = "".join(
        '<a href="%s"><span class="lk-name">%s</span><span class="lk-desc">%s</span></a>' % (h, h, d)
        for h, d in links
    )

    # ---------- 重点红旗（细节层）----------
    key = [f for f in ordered if f.get("risk_priority") in ("critical", "high", "medium")]
    shown = key[:12]
    rest_count = len(key) - len(shown)
    cards = []
    for f in shown:
        pr = f.get("risk_priority", "low")
        fid = escape(str(f.get("finding_id", "")))
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
            '<span class="finding-type">%s</span></div>'
            '<h3 class="finding-title">%s</h3>'
            '<div class="finding-who"><span class="k">涉及</span>%s</div>'
            '<div class="finding-body"><span class="k">现象</span>%s</div>'
            '%s'
            '<div class="finding-body"><span class="k">建议</span>%s</div>'
            '%s'
            '</article>' % (
                pr, fid, pr, PRIORITY_ZH.get(pr, pr), escape(tzh(f.get("finding_type", ""))),
                escape(f.get("title") or tzh(f.get("finding_type", ""))),
                escape(ent_human(f)), escape(facts), crit_html, escape(steps), q_html,
            )
        )
    findings_html = "".join(cards) if cards else '<p class="empty">未发现需复核的重点项。</p>'
    if rest_count > 0:
        findings_html += '<p class="more">另有 <b>%d</b> 条中风险线索，见下方「按类型汇总」与 <b>findings.csv</b>。</p>' % rest_count

    # ---------- 按类型汇总 ----------
    rows_html = []
    for ft, cnt in type_counts.most_common():
        rows_html.append(
            '<tr><td>%s</td><td class="num">%d</td><td class="num">%d</td><td class="crit">%s</td></tr>' % (
                escape(tzh(ft)), cnt, high_by_type.get(ft, 0), escape(CRITERIA.get(ft, ""))))
    types_table = (
        '<table class="typetable"><thead><tr><th>红旗类型</th><th>条数</th><th>其中高风险</th>'
        '<th>本应如何（制度依据）</th></tr></thead><tbody>%s</tbody></table>'
        % ("".join(rows_html) or '<tr><td colspan="4">无。</td></tr>')
    )

    # ---------- 供应商关系图 / 数据质量 ----------
    nnodes = len(graph.get("nodes", [])) if isinstance(graph, dict) else 0
    nedges = len(graph.get("edges", [])) if isinstance(graph, dict) else 0
    graph_note = "已生成供应商关系图：<b>%d</b> 个主体、<b>%d</b> 条关系边（详见 relationship_graph.json）。" % (nnodes, nedges)
    dq = "共发现 <b>%d</b> 行数据问题（已隔离，不参与分析）。" % bad_count if bad_count else "无坏行。"

    seal_icon = status_zh[:1] if status_class != "pass" else "✓"
    thesis_note_html = ('<div class="sub">%s</div>' % thesis_note) if thesis_note else ""

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>采购舞弊红旗筛查 · 全景报告</title>
<style>%s</style>
</head>
<body>
<div class="wrap">

  <div class="firstpage">
    <div class="masthead">
      <div class="seal %s">%s</div>
      <div>
        <h1>采购舞弊红旗筛查<span class="tag %s">%s</span></h1>
        <div class="sub">procurement-fraud-v2 v%s · %s · 用时 %s</div>
      </div>
    </div>

    <div class="thesis">
      <div class="main">%s</div>
      %s
    </div>

    %s

    <div class="kpis">%s</div>

    %s
    %s

    <div class="mini">最需要先看的 3 条</div>
    %s

    <div class="nextbox"><b>建议下一步：</b>%s</div>

    <div class="mini">查看明细</div>
    <div class="links">%s</div>
  </div>

  <h2 class="sec">重点红旗<span class="hint">共 %d 条中高风险，以下列出前 %d 条</span></h2>
  %s

  <h2 class="sec">按类型汇总<span class="hint">含全部 %d 条红旗</span></h2>
  %s

  <h2 class="sec">供应商关系图</h2>
  <div class="note">%s</div>

  <h2 class="sec">数据质量</h2>
  <div class="note">%s</div>

  <div class="disclaimer">
    <b>业务定位</b>：本报告为<strong>辅助筛查</strong>，不替代专业审计/合规判断。共享账号、价格离群、流程异常、文本相似均为<strong>复核线索</strong>，不能单独或自动证明串标、利益输送或舞弊。<strong>未发现问题 ≠ 没有问题</strong>；最终结论必须由有资质人员做出。
  </div>

  <div class="foot">由 procurement-fraud-v2 v%s 自动生成 · 离线可看 · 无外部依赖</div>
</div>
</body>
</html>
""" % (
        DASHBOARD_CSS,
        status_class, seal_icon,
        status_class, status_zh,
        version, date_str, duration_str,
        thesis_main, thesis_note_html,
        handoff_html,
        kpis_html,
        riskbar, legend,
        top_html,
        next_step,
        links_html,
        len(key), len(shown),
        findings_html,
        len(findings), types_table,
        graph_note,
        dq,
        version,
    )
    (output_dir / "dashboard.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        raise SystemExit(2)
