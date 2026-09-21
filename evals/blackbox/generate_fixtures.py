#!/usr/bin/env python3
"""
生成黄金测试集 fixtures 和 ground truth
"""
import json
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLACKBOX = ROOT


# ============= EXPENSE FIXTURES =============
EXPENSE_FIXTURES = [
    {
        "id": "01_duplicate_invoice",
        "description": "测试 exact-duplicate-invoice：同发票号+同金额+同币种被两人/两次报销",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-DUP-1","E-EMP-A","hotel","2026-06-01","920","CNY","酒店A","INV-DUP-001","A-1"],
            ["E-DUP-2","E-EMP-A","hotel","2026-06-02","920","CNY","酒店A","INV-DUP-001","A-1"],
        ],
        "expected_findings": ["exact-duplicate-invoice"],
    },
    {
        "id": "02_employee_date_amount",
        "description": "测试 exact-duplicate-employee-date-amount：同员工同日同金额",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-EDA-1","E-EMP-B","meal","2026-06-01","55","CNY","餐厅","M-1","A-2"],
            ["E-EDA-2","E-EMP-B","meal","2026-06-01","55","CNY","餐厅","M-2","A-2"],
        ],
        "expected_findings": ["exact-duplicate-employee-date-amount"],
    },
    {
        "id": "03_sequential_invoices",
        "description": "测试 sequential-invoice：同商户≥3 张连号发票",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-SEQ-1","E-EMP-C","office","2026-06-01","100","CNY","打印店","INV-S001","A-3"],
            ["E-SEQ-2","E-EMP-C","office","2026-06-02","100","CNY","打印店","INV-S002","A-3"],
            ["E-SEQ-3","E-EMP-C","office","2026-06-03","100","CNY","打印店","INV-S003","A-3"],
            ["E-SEQ-4","E-EMP-C","office","2026-06-04","100","CNY","打印店","INV-S004","A-3"],
        ],
        "expected_findings": ["sequential-invoice"],
    },
    {
        "id": "04_format_anomaly",
        "description": "测试 invoice-format-anomaly：发票号含非常规字符",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-FMT-1","E-EMP-D","office","2026-06-01","50","CNY","店铺A","INV-@@@@-!!!","A-4"],
            ["E-FMT-2","E-EMP-D","office","2026-06-02","60","CNY","店铺A","#$%^&99","A-4"],
        ],
        "expected_findings": ["invoice-format-anomaly"],
    },
    {
        "id": "05_holiday",
        "description": "测试 holiday-signal：国庆节假日消费（需在 policy 配置 holidays）",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-HOL-1","E-EMP-E","meal","2026-10-01","800","CNY","饭店","M-NAT-001","A-5"],
            ["E-HOL-2","E-EMP-E","hotel","2026-10-02","1500","CNY","酒店","H-NAT-001","A-5"],
        ],
        "policy_overrides": {"holidays": ["2026-10-01","2026-10-02","2026-10-03"]},
        "expected_findings": ["holiday-signal"],
    },
    {
        "id": "06_submit_before_expense",
        "description": "测试 submit-before-expense：提交日期早于消费日期",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","submit_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-SUB-1","E-EMP-F","hotel","2026-06-15","2026-06-10","800","CNY","酒店","H-1","A-6"],
        ],
        "expected_findings": ["submit-before-expense"],
    },
    {
        "id": "07_future_date",
        "description": "测试 future-date：费用日期在未来（默认基准日为系统今天）",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-FUT-1","E-EMP-G","hotel","2026-12-31","1000","CNY","酒店","H-FUT","A-7"],
        ],
        "expected_findings": ["future-date"],
    },
    {
        "id": "08_self_approval",
        "description": "测试 self-approval：审批人 == 报销人",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-SELF-1","A-APPROVER","hotel","2026-06-01","800","CNY","酒店","H-1","A-APPROVER"],
        ],
        "expected_findings": ["self-approval"],
    },
    {
        "id": "09_large_low_level",
        "description": "测试 large-amount-low-level-approval：大额由低层级审批",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-LLL-1","E-EMP-H","hotel","2026-06-01","15000","CNY","酒店","H-LLL","A-INTERN"],
        ],
        "policy_overrides": {
            "large_amount_threshold": 5000,
            "low_level_approver_keywords": ["INTERN", "ASSIST"],
        },
        "expected_findings": ["large-amount-low-level-approval"],
    },
    {
        "id": "10_cross_employee_invoice",
        "description": "测试 cross-employee-invoice：同一发票号被不同员工使用",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-CROSS-1","E-EMP-X","hotel","2026-06-01","800","CNY","酒店","INV-CROSS","A-X"],
            ["E-CROSS-2","E-EMP-Y","hotel","2026-06-01","800","CNY","酒店","INV-CROSS","A-Y"],
        ],
        "expected_findings": ["cross-employee-invoice"],
    },
    {
        "id": "11_missing_expense_type",
        "description": "测试 missing-expense-type：缺费用类型且金额超最严上限",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-MISS-1","E-EMP-Z","","2026-06-01","6000","CNY","酒店","H-MISS","A-Z"],
        ],
        "policy_overrides": {
            "limits": [{"rule_id": "HOTEL", "expense_type": "hotel", "currency": "CNY", "max_amount": 1000}],
        },
        "expected_findings": ["missing-expense-type"],
    },
    {
        "id": "12_no_finding_clean",
        "description": "测试无 finding：完全正常的数据",
        "data": [
            ["expense_id","employee_id","expense_type","expense_date","amount","currency","vendor_name","invoice_number","approver"],
            ["E-CLEAN-1","E-EMP-N","meal","2026-06-08","50","CNY","园区餐厅","M-CLEAN-1","A-N"],
            ["E-CLEAN-2","E-EMP-N","taxi","2026-06-09","80","CNY","出租车","T-CLEAN-1","A-N"],
        ],
        "expected_findings": [],
    },
]


# ============= PROCUREMENT FIXTURES =============
PROCUREMENT_FIXTURES = [
    {
        "id": "01_shared_bank_account",
        "description": "测试 shared-bank-account：两家供应商共享对公账户",
        "vendors": [
            ["vendor_id","vendor_name","legal_name","tax_id","bank_account","phone","email","address","legal_representative","created_at"],
            ["PV-A","甲公司","甲有限公司","TAX-A","BA-SHARED","13800001","a@a.com","A路","张一","2018-01-01"],
            ["PV-B","乙公司","乙有限公司","TAX-B","BA-SHARED","13800002","b@b.com","B路","李二","2018-01-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            ["PO-A-1","PV-A","PB","工具","扳手","件","华南","10","100","1000","CNY","2026-05-01","2026-04-30","2026-05-05"],
            ["PO-B-1","PV-B","PB","工具","扳手","件","华南","10","100","1000","CNY","2026-05-01","2026-04-30","2026-05-05"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [],
        "bids": [],
        "bid_docs": {},
        "expected_findings": ["shared-bank-account"],
    },
    {
        "id": "02_bid_text_similarity",
        "description": "测试 bid-text-similarity：两家供应商投标文本完全相同",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["PV-X","X公司","BA-X","13800011","X路","2018-01-01"],
            ["PV-Y","Y公司","BA-Y","13800012","Y路","2018-01-01"],
            ["PV-Z","Z公司","BA-Z","13800013","Z路","2018-01-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            ["PO-X","PV-X","PB","设备","机床","台","华南","1","100000","100000","CNY","2026-05-01","2026-04-30","2026-05-05"],
            ["PO-Y","PV-Y","PB","设备","机床","台","华南","1","100000","100000","CNY","2026-05-02","2026-05-01","2026-05-06"],
            ["PO-Z","PV-Z","PB","设备","机床","台","华南","1","110000","110000","CNY","2026-05-03","2026-05-02","2026-05-07"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [],
        "bids": [
            ["tender_id","lot_id","bidder_id","bid_price","currency","document_path","submitted_at"],
            ["T-A","L-A","PV-X","100000","CNY","bid-docs/pvx.txt","2026-04-01 09:00"],
            ["T-A","L-A","PV-Y","100500","CNY","bid-docs/pvy.txt","2026-04-01 09:05"],
            ["T-A","L-A","PV-Z","110000","CNY","bid-docs/pvz.txt","2026-04-01 09:10"],
        ],
        "bid_docs": {
            "pvx.txt": "本投标人针对贵单位T-A标段提交报价。我方采用德国西门子840D数控系统，主轴最高转速12000rpm，刀库容量24把，质保两年。本投标人承诺遵守招标文件的全部通用要求。",
            "pvy.txt": "本投标人针对贵单位T-A标段提交报价。我方采用德国西门子840D数控系统，主轴最高转速12000rpm，刀库容量24把，质保两年。本投标人承诺遵守招标文件的全部通用要求。",
            "pvz.txt": "本投标人针对贵单位T-A标段提交报价。我方采用日本发那科系统，主轴转速8000rpm，质保一年。本投标人承诺遵守招标文件的全部通用要求。",
        },
        "expected_findings": ["bid-text-similarity"],
    },
    {
        "id": "03_payment_before_order",
        "description": "测试 payment-before-order：付款日期早于下单日期",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["PV-C","C公司","BA-C","13800021","C路","2018-01-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            ["PO-C","PV-C","PB","原料","钢板","吨","华南","5","5000","25000","CNY","2026-06-01","2026-05-31","2026-06-04"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [
            ["payment_id","po_id","vendor_id","amount","currency","payment_date","bank_account"],
            ["PAY-C","PO-C","PV-C","25000","CNY","2026-05-25","BA-C"],
        ],
        "bids": [],
        "bid_docs": {},
        "expected_findings": ["payment-before-order"],
    },
    {
        "id": "04_overpayment",
        "description": "测试 overpayment：付款额 > 订单额",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["PV-D","D公司","BA-D","13800031","D路","2018-01-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            ["PO-D","PV-D","PB","原料","塑料","吨","华南","10","5000","50000","CNY","2026-06-01","2026-05-31","2026-06-04"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [
            ["payment_id","po_id","vendor_id","amount","currency","payment_date","bank_account"],
            ["PAY-D","PO-D","PV-D","55000","CNY","2026-06-10","BA-D"],
        ],
        "bids": [],
        "bid_docs": {},
        "expected_findings": ["overpayment"],
    },
    {
        "id": "05_new_vendor",
        "description": "测试 new-vendor-large-order：新成立供应商短期内接大单",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["PV-E","E新公司","BA-E","13800041","E路","2026-04-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            ["PO-E","PV-E","PB","设备","新设备","台","华南","1","30000","30000","CNY","2026-05-01","2026-04-30","2026-05-05"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [],
        "bids": [],
        "bid_docs": {},
        "expected_findings": ["new-vendor-large-order"],
    },
    {
        "id": "06_no_finding_clean",
        "description": "测试无 finding：完全正常的采购数据",
        "vendors": [
            ["vendor_id","vendor_name","bank_account","phone","address","created_at"],
            ["PV-F","F公司","BA-F","13800051","F路","2018-01-01"],
        ],
        "purchase_orders": [
            ["po_id","vendor_id","buyer_id","category","item","unit","region","quantity","unit_price","total_amount","currency","order_date","approval_date","receipt_date"],
            ["PO-F","PV-F","PB","工具","扳手","件","华南","10","50","500","CNY","2026-05-01","2026-04-30","2026-05-05"],
        ],
        "employees": [
            ["employee_id","employee_name","department","phone","email","address","bank_account"],
            ["PB","采购","采购","138","p@p.com","部门","BANK"],
        ],
        "payments": [],
        "bids": [],
        "bid_docs": {},
        "expected_findings": [],
    },
]


# ============= INVESTIGATION FIXTURES =============
INVESTIGATION_FIXTURES = [
    {
        "id": "01_basic_authorized",
        "description": "测试基础 scope：授权齐全，材料齐全，应正常生成调查工作空间",
        "complaint": "【模拟举报】E001 在 2026-06-15 23:00 下载了 confidential_plan.pdf 并外发。",
        "messages": [
            ["message_id","timestamp","sender","recipient","channel","content"],
            ["M-1","2026-06-15T20:00:00+08:00","E001","E002","im","资料已获主管 A100 批准。"],
            ["M-2","2026-06-15T23:50:00+08:00","E001","external@x.com","email","请外发机密计划。"],
        ],
        "logs": [
            ["event_id","timestamp","actor","event_type","object","device","ip","result"],
            ["L-1","2026-06-15T23:41:00+08:00","E001","download","confidential_plan.pdf","LAPTOP","10.0.0.8","success"],
        ],
        "scope": {
            "case_id": "CASE-TEST-001",
            "purpose": "测试基础 scope",
            "authorization_confirmed": True,
            "authorization_reference": "TEST-AUTH-001",
            "date_range": {"start": "2026-06-01", "end": "2026-06-30"},
            "persons_in_scope": ["E001", "E002"],
            "allowed_sources": ["complaint.txt", "messages.csv", "logs.csv"],
            "source_types": {"complaint.txt": "text", "messages.csv": "messages", "logs.csv": "logs"},
            "network_access": False,
        },
        "expected_outcome": "workspace_created",
    },
    {
        "id": "02_out_of_scope",
        "description": "测试 scope filter：超期人员/日期会被排除",
        "complaint": "测试 scope 过滤。",
        "messages": [
            ["message_id","timestamp","sender","recipient","channel","content"],
            ["M-1","2026-06-15T20:00:00+08:00","E001","E002","im","范围内"],
            ["M-2","2026-06-15T23:50:00+08:00","E999","E998","im","人员越界"],
            ["M-3","2026-05-01T10:00:00+08:00","E001","E002","im","日期越界"],
        ],
        "logs": [
            ["event_id","timestamp","actor","event_type","object","device","ip","result"],
            ["L-1","2026-06-15T20:30:00+08:00","E001","download","normal.pdf","LAPTOP","10.0.0.8","success"],
        ],
        "scope": {
            "case_id": "CASE-TEST-002",
            "purpose": "测试 scope 过滤",
            "authorization_confirmed": True,
            "authorization_reference": "TEST-AUTH-002",
            "date_range": {"start": "2026-06-01", "end": "2026-06-30"},
            "persons_in_scope": ["E001", "E002"],
            "allowed_sources": ["complaint.txt", "messages.csv", "logs.csv"],
            "source_types": {"complaint.txt": "text", "messages.csv": "messages", "logs.csv": "logs"},
            "network_access": False,
        },
        "expected_outcome": "scope_filter_works",
    },
    {
        "id": "03_no_authorization",
        "description": "测试 scope gate：未授权时必须拒绝",
        "complaint": "测试无授权拒绝。",
        "messages": [
            ["message_id","timestamp","sender","recipient","channel","content"],
            ["M-1","2026-06-15T20:00:00+08:00","E001","E002","im","x"],
        ],
        "logs": [],
        "scope": {
            "case_id": "CASE-TEST-003",
            "purpose": "测试无授权拒绝",
            "authorization_confirmed": False,  # 关键：未授权
            "authorization_reference": "PENDING",
            "date_range": {"start": "2026-06-01", "end": "2026-06-30"},
            "persons_in_scope": ["E001"],
            "allowed_sources": ["complaint.txt", "messages.csv"],
            "source_types": {"complaint.txt": "text", "messages.csv": "messages"},
            "network_access": False,
        },
        "expected_outcome": "rejected_by_scope_gate",
    },
]


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def write_text(path: Path, content):
    path.write_text(content, encoding="utf-8")


def generate_expense():
    base = BLACKBOX / "expense"
    for fix in EXPENSE_FIXTURES:
        # 写 CSV
        csv_path = base / "fixtures" / f"{fix['id']}.csv"
        write_csv(csv_path, fix["data"])
        # 写 ground truth
        gt_path = base / "ground_truth" / f"{fix['id']}.json"
        gt = {
            "fixture_id": fix["id"],
            "description": fix["description"],
            "expected_findings": fix["expected_findings"],
            "policy_overrides": fix.get("policy_overrides", {}),
        }
        gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(EXPENSE_FIXTURES)} expense fixtures")


def generate_procurement():
    base = BLACKBOX / "procurement"
    for fix in PROCUREMENT_FIXTURES:
        # 写 input 目录
        input_dir = base / "fixtures" / fix["id"] / "input"
        bid_docs_dir = input_dir / "bid-docs"
        input_dir.mkdir(parents=True, exist_ok=True)
        bid_docs_dir.mkdir(exist_ok=True)
        write_csv(input_dir / "vendors.csv", fix["vendors"])
        write_csv(input_dir / "purchase_orders.csv", fix["purchase_orders"])
        write_csv(input_dir / "employees.csv", fix["employees"])
        if fix["payments"]:
            write_csv(input_dir / "payments.csv", fix["payments"])
        if fix["bids"]:
            write_csv(input_dir / "bids.csv", fix["bids"])
        for doc_name, content in fix.get("bid_docs", {}).items():
            (bid_docs_dir / doc_name).write_text(content, encoding="utf-8")
        # 写 ground truth
        gt_path = base / "ground_truth" / f"{fix['id']}.json"
        gt = {
            "fixture_id": fix["id"],
            "description": fix["description"],
            "expected_findings": fix["expected_findings"],
        }
        gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(PROCUREMENT_FIXTURES)} procurement fixtures")


def generate_investigation():
    base = BLACKBOX / "investigation"
    for fix in INVESTIGATION_FIXTURES:
        input_dir = base / "fixtures" / fix["id"] / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        write_text(input_dir / "complaint.txt", fix["complaint"])
        write_csv(input_dir / "messages.csv", fix["messages"])
        if fix["logs"]:
            write_csv(input_dir / "logs.csv", fix["logs"])
        # 写 scope
        scope_path = input_dir / "scope.json"
        scope_path.write_text(json.dumps(fix["scope"], indent=2, ensure_ascii=False), encoding="utf-8")
        # 写 ground truth
        gt_path = base / "ground_truth" / f"{fix['id']}.json"
        gt = {
            "fixture_id": fix["id"],
            "description": fix["description"],
            "expected_outcome": fix["expected_outcome"],
        }
        gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(INVESTIGATION_FIXTURES)} investigation fixtures")


if __name__ == "__main__":
    generate_expense()
    generate_procurement()
    generate_investigation()
    print(f"\nTotal fixtures: {len(EXPENSE_FIXTURES) + len(PROCUREMENT_FIXTURES) + len(INVESTIGATION_FIXTURES)}")
