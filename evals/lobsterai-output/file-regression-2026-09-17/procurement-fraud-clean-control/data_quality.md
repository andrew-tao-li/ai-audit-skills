# 采购数据质量报告

- Bad rows 合计：0

## 各表

- `vendors`: `{"status": "loaded", "rows": 3, "valid_rows": 3, "bad_rows": 0, "mapping": {"vendor_id": "vendor_id", "vendor_name": "vendor_name", "legal_name": "legal_name", "tax_id": "tax_id", "bank_account": "bank_account", "phone": "phone", "email": "email", "address": "address", "legal_representative": "legal_representative", "created_at": "created_at"}}`
- `purchase_orders`: `{"status": "loaded", "rows": 4, "valid_rows": 4, "bad_rows": 0, "mapping": {"po_id": "po_id", "vendor_id": "vendor_id", "buyer_id": "buyer_id", "category": "category", "item": "item", "unit": "unit", "region": "region", "quantity": "quantity", "unit_price": "unit_price", "total_amount": "total_amount", "currency": "currency", "order_date": "order_date", "approval_date": "approval_date", "receipt_date": "receipt_date"}}`
- `employees`: `{"status": "loaded", "rows": 2, "valid_rows": 2, "bad_rows": 0, "mapping": {"employee_id": "employee_id", "employee_name": "employee_name", "department": "department", "phone": "phone", "email": "email", "address": "address", "bank_account": "bank_account"}}`
- `payments`: `{"status": "loaded", "rows": 2, "valid_rows": 2, "bad_rows": 0, "mapping": {"payment_id": "payment_id", "po_id": "po_id", "vendor_id": "vendor_id", "amount": "amount", "currency": "currency", "payment_date": "payment_date", "bank_account": "bank_account"}}`
- `bids`: `{"status": "loaded", "rows": 3, "valid_rows": 3, "bad_rows": 0, "mapping": {"tender_id": "tender_id", "lot_id": "lot_id", "bidder_id": "bidder_id", "bid_price": "bid_price", "currency": "currency", "document_path": "document_path", "submitted_at": "submitted_at"}}`
