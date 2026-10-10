# 审计需求与 SQL 模板目录

模板的单一来源是 `assets/sql_templates.json`。本文件是给人看的中文说明。

| id | 需求 | 依赖字段 | 说明 |
|---|---|---|---|
| `duplicate-claim` | 重复报销（同员工 + 同日 + 同金额） | `employee_id` / `expense_date` / `amount` | |
| `duplicate-invoice` | 同一发票号重复（发票号 + 金额） | `invoice_number` / `amount` | |
| `self-approval` | 自审自批 | `employee_id` / `approver` | **覆盖「审批人是多人分号列表」**（`approver_contains_employee`） |
| `weekend-expense` | 周末消费（弱信号） | `expense_date` | 外勤/值班常见，导出后结合排班判断 |

## 方言

`sqlite`（默认，便于本地验证）/ `mysql` / `postgres` / `sqlserver` / `oracle`。
需要按方言区分的只有三处：**标识符引用**、**周末表达式**、**字符串拼接**（用于 `LIKE` 判断审批人列表里是否含报销人）。
其余 SQL 尽量用各方言都支持的写法（例如多列 `IN (子查询)`，避免表别名）。

## 怎么加一条需求

改 `assets/sql_templates.json`，加一个 `need`：`id` / `title` / `requires`（标准字段）/ `single_table` / `note` / `sql`（按方言各一份）。
模板里的占位符：`{{字段名}}`（渲染为该字段映射到的「表.列」，并按方言加引号）、`{{table}}`、`{{weekend:字段}}`、`{{approver_contains_employee}}`。

## 缺字段怎么办

**不硬凑。** 需求声明的 `requires` 里有任何一个没有映射到，就跳过该需求，并把"需要哪些字段"写进 `missing_fields.csv`——
让用户回 IT 要。
