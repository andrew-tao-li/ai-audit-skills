# Procurement data contract

## Required files

- `vendors`: `vendor_id`、`vendor_name`。推荐 `legal_name`、`tax_id`、`bank_account`、`phone`、`email`、`address`、`legal_representative`、`created_at`。
- `purchase_orders`: `po_id`、`vendor_id`、`buyer_id`、`unit_price`、`total_amount`、`order_date`。推荐 `category`、`item`、`unit`、`region`、`quantity`、`approval_date`、`receipt_date`。

## Optional files

- `employees`: `employee_id`，以及 `phone/email/address/bank_account` 中至少一个。
- `payments`: `payment_id`、`po_id`、`vendor_id`、`amount`、`payment_date`、`bank_account`。
- `bids`: `tender_id`、`lot_id`、`bidder_id`、`bid_price`、`document_path`、`submitted_at`。`document_path` 指向输入目录内 `.txt` 或 `.md`；不得使用 `..` 跳出输入目录。

文件名和字段支持常见中英文别名。用 config 的 `files` 和 `field_maps` 显式覆盖，例如：

```json
{
  "files": {"vendors": "供应商.xlsx", "purchase_orders": "采购订单.xlsx"},
  "field_maps": {"vendors": {"vendor_id": "供应商编码"}}
}
```

标识符按字符串处理；电话、邮箱、银行账号和地址只生成归一化匹配键，输出仍保留原值以便受权人员回源。真实数据分享前必须脱敏。
