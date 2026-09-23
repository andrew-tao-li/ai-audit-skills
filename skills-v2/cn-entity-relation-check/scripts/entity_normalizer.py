#!/usr/bin/env python3
"""
实体标准化：识别输入是公司还是自然人，清洗名称，提取统一社会信用代码。

本模块不联网、不内置任何 Key。它是确定性判定链的第一步。
"""
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# 18 位统一社会信用代码：数字+大写字母（排除 I/O/Z/S/V），末位可为数字或大写字母
USCC_RE = re.compile(r"[0-9A-HJ-NPQRTUWXY]{18}")

# 公司名关键词（用于粗判类型）
COMPANY_HINTS = (
    "有限公司", "有限责任公司", "股份有限公司", "合伙企业", "分公司",
    "集团", "企业", "公司", "厂", "中心", "事务所", "合作社",
)

# 中文人名粗判：2-4 个汉字，或「姓+职务」形式，或英文名
PERSON_NAME_RE = re.compile(r"^[\u4e00-\u9fa5]{2,4}$")


@dataclass
class Entity:
    """内部统一实体对象。"""
    raw_input: str
    type: str = "unknown"          # company | person | unknown
    normalized_name: Optional[str] = None
    canonical_id: Optional[str] = None   # 公司=USCC，人=provider person_id
    anchor: Optional[str] = None          # 自然人的企业锚点（如 "上海甲公司"）
    resolved: bool = False
    person_identity_confirmed: bool = False
    note: str = ""


def _clean(text: str) -> str:
    """清洗口语噪音：去首尾空白、统一全角/半角。"""
    t = (text or "").strip()
    t = t.replace("\u3000", " ").strip()
    return t


def extract_uscc(text: str) -> Optional[str]:
    m = USCC_RE.search(text or "")
    return m.group(0) if m else None


def normalize_company_name(text: str) -> str:
    """公司名清洗：去括号附注、去多余空格。"""
    t = _clean(text)
    # 去掉常见括号内附注（如「(存续)」「[已注销]」）
    t = re.sub(r"[（(【\[][^）)】\]]*[）)】\]]", "", t).strip()
    t = re.sub(r"\s+", "", t)
    return t


def normalize_person_name(text: str) -> str:
    return _clean(text)


def detect_type(raw: str) -> str:
    t = _clean(raw)
    if not t:
        return "unknown"
    if extract_uscc(t):
        return "company"
    # 明显公司后缀
    for hint in COMPANY_HINTS:
        if t.endswith(hint) or hint in t:
            return "company"
    # 纯中文 2-4 字视为人名（但含公司关键词的除外，已在上面返回）
    if PERSON_NAME_RE.match(t):
        return "person"
    return "unknown"


def normalize_entity(raw: str) -> Entity:
    """把自由文本转成 Entity。只做类型粗判与名称清洗，不做锚定。"""
    e = Entity(raw_input=_clean(raw))
    e.type = detect_type(raw)
    if e.type == "company":
        e.normalized_name = normalize_company_name(raw)
        e.canonical_id = extract_uscc(raw)
        # 有 USCC 即视为已锚定
        if e.canonical_id:
            e.resolved = True
    elif e.type == "person":
        e.normalized_name = normalize_person_name(raw)
    return e


def attach_anchor(entity: Entity, anchor: str, person_id: Optional[str] = None) -> Entity:
    """给自然人附加企业锚点（姓名 + 已确认任职企业）。"""
    if entity.type != "person":
        return entity
    entity.anchor = normalize_company_name(anchor)
    if person_id:
        entity.canonical_id = person_id
        entity.person_identity_confirmed = True
    entity.resolved = True
    return entity
