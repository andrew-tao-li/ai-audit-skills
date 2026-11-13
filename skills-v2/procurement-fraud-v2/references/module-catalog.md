# Procurement module catalog v0.1.0

## A. Shared attributes

检查不同供应商共享银行账号、电话、邮箱、地址和法定代表人。银行账号强于电话，电话强于地址。支付平台账户、园区地址、集团总机等必须进入 `whitelists`；共享地址本身只给弱/中等信号。

## B. Employee-vendor relationship

对员工和供应商的标准化电话、邮箱、地址、银行账号做精确交叉匹配。关系只说明需核对是否披露、是否为公共属性或录入错误，不说明利益输送。姓名相似和亲属关系需要外部受权数据，第一版不自动推断。

## C. Price anomaly

peer group 优先使用 `item + unit + region`；item 缺失时使用 `category + unit + region`。组内用 median/MAD 计算 robust z-score，只报告高价离群；小组不计算。数量级、规格、税、运费、质量、交期和时间窗口可能解释差异。

## D. Split order

同 buyer、vendor、category、currency 在配置窗口内，多笔单笔低于审批阈值而合计超过阈值。阈值只能来自 config。框架协议、分批交付和独立需求是替代解释。

## E. Bid similarity

第一版使用可解释的字符级 TF-IDF + cosine：Unicode 标准化，删除 config 中已知公共模板短语，生成 2–5 字符 n-gram，计算同一 lot 内两两相似度。阈值是本数据集筛查参数。PDF 应先由受控文档工具提取为文本，并保留页码映射。

## F. Bidding pattern

检查同一 lot 的报价极度接近和尾数一致等弱信号。税率、预算上限、统一计价规则会造成合理聚集，不得单独认定陪标。

## G. Process order

检查 PO 日期早于审批日期、收货早于 PO、付款早于审批。系统迁移、补录、紧急采购和日期口径差异是常见解释。

## H. Concentration

按 buyer 计算供应商金额占比；达到最小订单数且份额超过配置值时形成线索。独家技术、框架协议和地区供给限制可能合理。

## Explainable scoring

默认参考：共享银行账号 +4、员工供应商共享银行 +4、共享电话/邮箱 +3、地址 +1、文本高相似 +2、价格离群 +2、拆单 +3、流程异常 +2、集中度 +1。分数只映射复核优先级，不是舞弊概率。

## v0.2.0 新增规则（脚本已实现，此前未列入 A–H）

> 以下规则于 v0.2.0 加入、`run_procurement_audit.py` 已实现，但本目录此前未收录，构成规则目录的覆盖盲点。除注明外**默认开启**、无需额外配置。

### 新供应商接大单（new-vendor-large-order）

供应商 `created_at` 到其首笔订单 `order_date` 的间隔 ≤ `new_vendor_days_threshold`（默认 90 天），且首单 `total_amount` ≥ `new_vendor_amount_threshold`（默认 20000）。强证据（3 分）。新设主体、集团内供应商、紧急替代供应商是合理解释。

### 超额付款（overpayment）

付款金额 > 关联订单金额 × (1 + `order_amount_tolerance`，默认 0.01)。强证据（3 分）。合同变更、运费、税费、事后补款是合理解释。

### 付款早于下单（payment-before-order）

`payment_date` 早于关联 PO 的 `order_date`。强证据（3 分）。预付款、紧急授权、日期口径差异是合理解释。

### 收货早于审批（process-receipt-before-approval）

`receipt_date` 早于 `approval_date`，独立于「收货早于下单」。强证据（3 分）。紧急采购、先收货后补审批是合理解释。

### 审批严重滞后（process-order-stale-approval）

仅当 `order_approval_direction: either` 时，订单与审批间隔 > 30 天报弱信号（1 分），提示补录嫌疑。

### 报价子簇（bid-price-subcluster）

全标段极差被拉大时，检测相邻报价中极差 ≤ `bid_price_close_ratio`×3 的接近子簇（≥3 家、子簇内极差 ≤ ×2）。中证据（2 分）。真实竞争组与围标组混合报价是常见解释。

对应分数：新供应商接大单 +3、超额付款 +3、付款早于下单 +3、收货早于审批 +3、报价子簇 +2、审批滞后 +1；仍只映射复核优先级，不是舞弊概率。
