# 采购数据质量报告

- Bad rows 合计：3

## 各表

- `vendors`: `{"status": "loaded", "rows": 2, "valid_rows": 1, "bad_rows": 1, "mapping": {"vendor_id": "vendor_id", "vendor_name": "vendor_name", "legal_name": "legal_name", "tax_id": "tax_id", "bank_account": "bank_account", "phone": "phone", "email": "email", "address": "address", "legal_representative": "legal_representative", "created_at": "created_at"}}`
- `purchase_orders`: `{"status": "loaded", "rows": 3, "valid_rows": 1, "bad_rows": 2, "mapping": {"po_id": "po_id", "vendor_id": "vendor_id", "buyer_id": "buyer_id", "category": "category", "item": "item", "unit": "unit", "region": "region", "quantity": "quantity", "unit_price": "unit_price", "total_amount": "total_amount", "currency": "currency", "order_date": "order_date", "approval_date": "approval_date", "receipt_date": "receipt_date"}}`
- `employees`: `{"status": "not_provided", "rows": 0, "valid_rows": 0, "bad_rows": 0}`
- `payments`: `{"status": "not_provided", "rows": 0, "valid_rows": 0, "bad_rows": 0}`
- `bids`: `{"status": "not_provided", "rows": 0, "valid_rows": 0, "bad_rows": 0}`

## 警告与跳过

- employees 模块：未提供输入
- payments 模块：未提供输入
- bids 模块：未提供输入
- split-order：未提供 approval_thresholds
