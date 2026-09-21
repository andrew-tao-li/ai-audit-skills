#!/usr/bin/env python3
"""
修复 fixture 数据：让每个 fixture 尽可能只触发目标 finding，避免多 finding 共现
"""
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLACKBOX = ROOT


# 修复 expense fixtures
EXPENSE_FIXED = {
    "01_duplicate_invoice.csv": [
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-DUP-1","E-EMP-A","meal","2026-06-01","50","CNY","酒店A","INV-DUP-001","A-1"],
        ["E-DUP-2","E-EMP-A","meal","2026-06-02","50","CNY","酒店A","INV-DUP-001","A-1"],
    ],
    "02_employee_date_amount.csv": [
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-EDA-1","E-EMP-B","meal","2026-06-01","50","CNY","餐厅","M-INV-001","A-2"],
        ["E-EDA-2","E-EMP-B","meal","2026-06-01","50","CNY","餐厅","M-INV-002","A-2"],
    ],
    "03_sequential_invoices.csv": [
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-SEQ-1","E-EMP-C","office","2026-06-01","30","CNY","打印店","INV-SEQ-100","A-3"],
        ["E-SEQ-2","E-EMP-C","office","2026-06-02","50","CNY","打印店","INV-SEQ-101","A-3"],
        ["E-SEQ-3","E-EMP-C","office","2026-06-03","40","CNY","打印店","INV-SEQ-102","A-3"],
        ["E-SEQ-4","E-EMP-C","office","2026-06-04","60","CNY","打印店","INV-SEQ-103","A-3"],
    ],
    "05_holiday.csv": [
        # 用低金额避免 policy-threshold，日期用过去日期避免 future-date
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-HOL-1","E-EMP-E","meal","2025-10-01","200","CNY","饭店","M-NAT-2025-1","A-5"],
        ["E-HOL-2","E-EMP-E","hotel","2025-10-02","800","CNY","酒店","H-NAT-2025-1","A-5"],
    ],
    "06_submit_before_expense.csv": [
        ["expense_id","employee_id","expense_type","expense_date","submit_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-SUB-1","E-EMP-F","hotel","2026-06-15","2026-06-10","800","CNY","酒店","H-SUB-001","A-6"],
    ],
    "08_self_approval.csv": [
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-SELF-1","A-APPROVER","hotel","2026-06-01","800","CNY","酒店","H-SELF-001","A-APPROVER"],
    ],
    "09_large_low_level.csv": [
        # 15000 元低于 limits[0] 默认 800，所以不触发 policy-threshold
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-LLL-1","E-EMP-H","meal","2026-06-01","15000","CNY","酒店","H-LLL-001","A-INTERN"],
    ],
    "10_cross_employee_invoice.csv": [
        # 用不同金额避免 exact-duplicate
        ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
        ["E-CROSS-1","E-EMP-X","hotel","2026-06-01","800","CNY","酒店","INV-CROSS-XYZ","A-X"],
        ["E-CROSS-2","E-EMP-Y","hotel","2026-06-01","900","CNY","酒店","INV-CROSS-XYZ","A-Y"],
    ],
}


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def fix_expense():
    base = BLACKBOX / "expense" / "fixtures"
    for filename, data in EXPENSE_FIXED.items():
        write_csv(base / filename, data)
        print(f"Fixed expense fixture: {filename}")


def fix_holiday_policy():
    """修 05_holiday 的 ground truth，删除 future-date 因为数据用了过去日期"""
    gt_file = BLACKBOX / "expense" / "ground_truth" / "05_holiday.json"
    gt = json.loads(gt_file.read_text())
    # 用了过去日期（2025-10-01），未来日期不应该触发
    # 但 hotels 800 是最大超阈值上限 1000（800 < 1000），不应触发 policy-threshold
    gt["policy_overrides"] = {
        "holidays": ["2025-10-01", "2025-10-02", "2025-10-03"],  # 用过去日期
        "limits": [{"rule_id": "HOTEL", "expense_type": "hotel", "currency": "CNY", "max_amount": 1500}],  # 提高 hotel 上限
        "approval_thresholds": [],
    }
    gt_file.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Fixed 05_holiday ground truth")


def fix_procurement_payment_before_order():
    """修 03_payment_before_order：调整数据避免同时触发 process-payment-before-approval"""
    input_dir = BLACKBOX / "procurement" / "fixtures" / "03_payment_before_order" / "input"

    # 新数据：order=2026-06-01, approval=2026-06-02 (同日之后), payment=2026-05-25 (早于 order 但晚于 approval 之前)
    # 即：付款 05-25 < 订单 06-01，但付款也早于审批 06-02，所以也会触发 process-payment-before-approval
    # 要避免这种情况，必须保证 payment >= approval
    # payment=2026-06-03, order=2026-06-01, approval=2026-06-02
    # payment(06-03) > approval(06-02) ✓ 不触发 process-payment-before-approval
    # payment(06-03) > order(06-06-01) ✓ 不触发 payment-before-order
    # 不！payment 06-03 > order 06-01，所以 payment-after-order，触发了 payment-before-order 应该会触发
    # 但我们希望只触发 payment-before-order（付款早于订单）？等等这就是我们要测的
    # payment=05-25 order=06-01 approval=06-05（很晚）
    # payment(05-25) < approval(06-05)：触发 process-payment-before-approval
    # 要避免这个需要 approval < payment，即 approval=05-24
    # 但是 order_date 必须 < payment_date，即 order=05-26
    # 整体：order=05-26, approval=05-24, payment=05-25
    # payment(05-25) > order(05-26)? 不成立，因为05-25 < 05-26
    # 要触发 payment-before-order：payment < order_date
    # 调整：order=06-05, approval=06-06, payment=06-04（早于 order）
    # payment(06-04) < order(06-05) ✓ 触发 payment-before-order
    # payment(06-04) < approval(06-06) → 也触发 process-payment-before-approval
    # 除非 approval < payment，即 approval=06-03
    # 但 order_date < approval_date 通常成立（先下单后审批）
    # 所以 approval=06-03 < payment=06-04 < order=06-05？order 必须在 approval 之后
    # 简单方案：把 approval 也设为早于 payment
    # order=06-05, approval=06-03, payment=06-04
    # order > approval 不对，违反常理

    # 实际数据：让 approval >= payment（即先付款再补审批，这在某些公司不规范但存在）
    # order=2026-06-05, approval=2026-06-04, payment=2026-06-03
    # payment(06-03) < order(06-05) ✓ 触发 payment-before-order
    # payment(06-03) < approval(06-04) ✓ 触发 process-payment-before-approval
    # 还是不行！

    # 解决：让 order_date 在付款日之后，且 approval 也在付款日之前但同时 approval < order
    # approval(06-03) < payment(06-04) < order(06-05)
    # 但 payment < order 已经触发 payment-before-order
    # approval < payment 触发 process-payment-before-approval
    # 还是冲突

    # 最终方案：去掉 approval_date 字段（不提供）
    # 这样 payment-before-order 触发但 process-payment-before-approval 不触发
    new_orders = [
        ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","receipt_date"],
        # 去掉 approval_date，付款早于订单
        ["PO-C","PV-C","PB","原料","钢板","吨","华南","5","5000","25000","CNY","2026-06-05","2026-06-10"],
    ]
    write_csv(input_dir / "purchase_orders.csv", new_orders)

    new_payments = [
        ["payment_id","po_id","vendor_id","amount","currency","payment_date","bank_account"],
        ["PAY-C","PO-C","PV-C","25000","CNY","2026-06-03","BA-C"],
    ]
    write_csv(input_dir / "payments.csv", new_payments)

    print("Fixed 03_payment_before_order fixture")


if __name__ == "__main__":
    fix_expense()
    fix_holiday_policy()
    fix_procurement_payment_before_order()
    print("\nDone.")
