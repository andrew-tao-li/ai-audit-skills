#!/usr/bin/env python3
"""
添加复合场景 fixture：模拟真实业务中多 finding 共现的复杂情况
让 baseline 不再 100%，给后续改进提供真实的区分度
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLACKBOX = ROOT


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


# ============= EXPENSE 复合场景 =============
# 这些场景故意同时触发 2-3 个 finding，反映真实业务复杂性

EXPENSE_COMPLEX = [
    {
        "id": "complex_01_full_audit",
        "description": "复合场景1：销售经理同一周多次出差广州，存在重复发票 + 自审自批 + 周末信号 + 超标的多 finding 共现",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","submit_date","amount","currency","vendor_name","invoice_number","approver"],
            # 同一发票号出现两次（同员工不同日期，但实际是同一个发票重复报）
            ["E-C1-1","E-SALES-1","hotel","2026-06-12","2026-06-13","980","CNY","广州希尔顿","INV-GZ-2024-001","E-SALES-1"],
            ["E-C1-2","E-SALES-1","hotel","2026-06-13","2026-06-14","980","CNY","广州希尔顿","INV-GZ-2024-001","E-SALES-1"],
            # 同一周末多笔餐饮 + 自审自批 + 周末信号
            ["E-C1-3","E-SALES-1","meal","2026-06-13","2026-06-14","850","CNY","广州海鲜酒家","M-GZ-1","E-SALES-1"],
            ["E-C1-4","E-SALES-1","meal","2026-06-14","2026-06-15","900","CNY","广州海鲜酒家","M-GZ-2","E-SALES-1"],
            # 一笔严重超标
            ["E-C1-5","E-SALES-1","hotel","2026-06-15","2026-06-16","2800","CNY","广州W酒店","INV-W-001","E-SALES-1"],
        ],
        "expected_findings": [
            "exact-duplicate-invoice",
            "self-approval",
            "weekend-signal",
            "policy-threshold",
        ],
    },
    {
        "id": "complex_02_procurement_abuse",
        "description": "复合场景2：仓储员工高频小额办公采购（跨月）+ 单笔大额低层级审批",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","submit_date","amount","currency","vendor_name","invoice_number","approver"],
            # 高频小额办公采购
            ["E-C2-1","E-WH-1","office","2026-06-01","2026-06-02","80","CNY","文具店","WS-001","A-WH-MGR"],
            ["E-C2-2","E-WH-1","office","2026-06-03","2026-06-04","85","CNY","文具店","WS-002","A-WH-MGR"],
            ["E-C2-3","E-WH-1","office","2026-06-05","2026-06-06","92","CNY","文具店","WS-003","A-WH-MGR"],
            ["E-C2-4","E-WH-1","office","2026-06-08","2026-06-09","78","CNY","文具店","WS-004","A-WH-MGR"],
            ["E-C2-5","E-WH-1","office","2026-06-10","2026-06-11","88","CNY","文具店","WS-005","A-WH-MGR"],
            ["E-C2-6","E-WH-1","office","2026-06-12","2026-06-13","95","CNY","文具店","WS-006","A-WH-MGR"],
            # 大额由低层级审批（实习生）
            ["E-C2-7","E-WH-1","office","2026-06-15","2026-06-16","12000","CNY","家具城","FURN-001","A-INTERN"],
        ],
        "expected_findings": [
            "near-duplicate",
            "large-amount-low-level-approval",
        ],
    },
    {
        "id": "complex_03_hr_falsified",
        "description": "复合场景3：HR 伪造差旅报销（跨人复用发票 + 未来日期 + 大额自审）",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","submit_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-C3-1","E-HR-1","hotel","2026-07-01","2026-06-15","1200","CNY","酒店A","INV-HR-FAKE-001","E-HR-1"],
            ["E-C3-2","E-HR-2","hotel","2026-07-02","2026-06-15","1200","CNY","酒店A","INV-HR-FAKE-001","E-HR-1"],
            ["E-C3-3","E-HR-3","hotel","2026-07-03","2026-06-15","1200","CNY","酒店A","INV-HR-FAKE-001","E-HR-1"],
            ["E-C3-4","E-HR-1","meal","2026-12-31","2026-06-15","800","CNY","饭店","M-HR-FUTURE","E-HR-1"],
        ],
        "expected_findings": [
            "cross-employee-invoice",
            "future-date",
            "self-approval",
        ],
    },
]


# ============= PROCUREMENT 复合场景 =============

PROCUREMENT_COMPLEX = [
    {
        "id": "complex_01_ma_carton",
        "description": "复合场景1：3 家马甲供应商共享账户 + 拆分采购 + 价格离群",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["CV-A","甲伪装","BA-CARTON","13800001","A路","2018-01-01"],
            ["CV-B","乙伪装","BA-CARTON","13800002","B路","2018-01-01"],
            ["CV-C","丙伪装","BA-CARTON","13800003","C路","2018-01-01"],
            ["CV-D","正常供应商","BA-D-NORMAL","13800004","D路","2018-01-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            # 3 家马甲供应商同金额同物品
            ["PO-CV-A","CV-A","PB","原料","钢板","吨","华南","5","5000","25000","CNY","2026-06-01","2026-05-31","2026-06-05"],
            ["PO-CV-B","CV-B","PB","原料","钢板","吨","华南","5","5000","25000","CNY","2026-06-02","2026-06-01","2026-06-06"],
            ["PO-CV-C","CV-C","PB","原料","钢板","吨","华南","5","5000","25000","CNY","2026-06-03","2026-06-02","2026-06-07"],
            # 正常供应商提供 peer
            ["PO-CV-D","CV-D","PB","原料","钢板","吨","华南","5","3500","17500","CNY","2026-06-01","2026-05-31","2026-06-05"],
            ["PO-CV-D2","CV-D","PB","原料","钢板","吨","华南","5","3600","18000","CNY","2026-06-08","2026-06-07","2026-06-12"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [],
        "bids": [],
        "bid_docs": {},
        "expected_findings": [
            "shared-bank-account",
            "price-outlier",
        ],
    },
    {
        "id": "complex_02_emergence",
        "description": "复合场景2：新成立供应商紧急采购 + 流程倒置 + 超额付款",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["EV-1","新供应商X","BA-EX","13800011","X路","2026-04-15"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            # 紧急采购：先收货 → 后下单 → 后审批
            ["PO-EV","EV-1","PB","设备","紧急设备","台","华南","1","45000","45000","CNY","2026-06-08","2026-06-10","2026-06-05"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [
            ["payment_id","po_id","vendor_id","amount","currency","payment_date","bank_account"],
            ["PAY-EV","PO-EV","EV-1","50000","CNY","2026-06-09","BA-EX"],
        ],
        "bids": [],
        "bid_docs": {},
        "expected_findings": [
            "new-vendor-large-order",
            "process-receipt-before-order",
            "process-receipt-before-approval",
            "process-payment-before-approval",
            "overpayment",
        ],
    },
]


def add_expense_complex():
    base = BLACKBOX / "expense" / "fixtures"
    gt_base = BLACKBOX / "expense" / "ground_truth"
    for fix in EXPENSE_COMPLEX:
        write_csv(base / f"{fix['id']}.csv", fix["data"])
        gt = {
            "fixture_id": fix["id"],
            "description": fix["description"],
            "expected_findings": fix["expected_findings"],
            "complex": True,
        }
        gt_base.joinpath(f"{fix['id']}.json").write_text(
            json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Added complex expense: {fix['id']}")


def add_procurement_complex():
    base = BLACKBOX / "procurement" / "fixtures"
    for fix in PROCUREMENT_COMPLEX:
        input_dir = base / fix["id"] / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        write_csv(input_dir / "vendors.csv", fix["vendors"])
        write_csv(input_dir / "purchase_orders.csv", fix["purchase_orders"])
        write_csv(input_dir / "employees.csv", fix["employees"])
        if fix["payments"]:
            write_csv(input_dir / "payments.csv", fix["payments"])
        gt = {
            "fixture_id": fix["id"],
            "description": fix["description"],
            "expected_findings": fix["expected_findings"],
            "complex": True,
        }
        (base.parent / "ground_truth" / f"{fix['id']}.json").write_text(
            json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Added complex procurement: {fix['id']}")


if __name__ == "__main__":
    add_expense_complex()
    add_procurement_complex()
    print(f"\nTotal new complex fixtures: {len(EXPENSE_COMPLEX) + len(PROCUREMENT_COMPLEX)}")
