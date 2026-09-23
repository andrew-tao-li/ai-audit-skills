---
name: cn-entity-relation-check
description: "对两个主体（公司/自然人）核查中国公开工商信息中是否存在可验证关联，支持公司-公司、公司-自然人、自然人-自然人三类组合，输出关联/不关联/待核查三态结论。Use when the user asks whether two companies or people are related, requests 关联排查/关联分析/关系穿透, supplier-employee relationship checks, related-party screening, 共同股东/高管/法人 overlap, 实际控制/最终受益人, or Chinese corporate due-diligence tasks. Do not use for risk scoring, fraud conviction, benefit-transfer conclusions, personal background investigation (family, private contact, social media), or internal hidden-relationship mining."
version: 0.1.0
metadata:
  author: "andrew-tao-li"
  aiaudit_compatibility: "Agent Skills hosts; offline decision core; Python 3.10+ for scripts; structured corporate data (MCP/API) preferred, web search as fallback"
  predecessor: null
  changelog: "v0.1.0: 三态判定协议（关联/不关联/待核查）/ 实体锚定 + 自然人重名消歧 / 强弱证据分层 / 确定性决策引擎 + result_validator / max_depth=3 的 BFS 路径查找 / Provider Adapter 抽象 / 零真实 Key"
---

# 关联排查（中国公开工商关系）

## Purpose

对两个主体判断中国公开工商信息中是否存在可验证的关联，只输出三种状态：

- **关联**：存在符合定义的公开工商强关系路径。
- **不关联**：在本次数据源、关系范围、查询时间、最大路径深度内，未发现符合定义的关联。
- **待核查**：任何身份歧义、数据不足、调用失败或弱线索导致无法可靠判断时。

本 skill 的第一原则：

> **模型负责理解、调度和解释；结构化数据与确定性规则负责事实判定。**

## Use this skill when

- 用户问「A 和 B 有没有关联」「关联排查」「关联分析」「共同股东/高管/法人」「实际控制关系」「历史关联」。
- 三类组合：公司—公司、公司—自然人、自然人—自然人。
- 场景：供应商准入尽调、员工—供应商关联筛查、关联方识别、工商关系穿透。

## Do not use this skill when

- 用户要的是「这家公司有没有风险」「是不是骗子」「是不是利益输送/围标/腐败」——这些是结论判断，不在 V0.1 范围。
- 用户要查家庭、私人联系方式、社交账号等私人背景——本 skill 只做公开工商身份消歧，不做私人画像。
- 用户要求直接给出合规/违规认定或处置决定。

## Hard rules（接近不可修改）

1. 绝不以「网页没搜到」作为「不关联」的证据。
2. 任何 API 错误、超时、权限不足、余额不足、限流、分页未完成、查询深度不足，一律降级为「待核查」，不得输出「不关联」。
3. 自然人姓名不是唯一标识；必须有数据源稳定 person_id 或「姓名+已确认任职企业」锚点，否则「待核查」。
4. V0.1 只有公开工商强关系能独立产生「关联」：法人、股权、投资、董监高、合伙、分支、实控、UBO 及对应历史关系。
5. 同电话/地址/邮箱、诉讼、供应商/客户、新闻共同出现等是弱线索，只能「待核查」，不能独立「关联」。
6. 每个「关联」必须至少有一条可复核的证据路径。
7. 每个「不关联」必须披露数据源、关系范围、查询时间、最大深度。
8. LLM 不得覆盖确定性决策引擎的输出状态。

## 三态判定协议

内部状态：`RELATED` / `NOT_RELATED_IN_SCOPE` / `NEEDS_VERIFICATION`，界面显示「关联/不关联/待核查」。

- `RELATED`：存在有效强关系路径，且关键主体已锚定、自然人已消歧、证据可追溯。
- `NOT_RELATED_IN_SCOPE`：仅当「主体已锚定 + 使用结构化数据源 + 查询完成 + 范围完整 + Provider 无错误 + 自然人无歧义 + Provider 支持 negative semantics + 无有效强路径」全部满足时才允许。
- `NEEDS_VERIFICATION`：其余一切情况。

「不关联」的真实语义是「在本次数据源、公开工商关系范围、查询时间和最大深度内未发现关联」，**不是**「现实世界绝对无关」。

## 输入与输出

输入：两个自由文本主体，如「上海甲公司和上海乙公司有没有关系」「张三和上海乙公司有没有关系」。

内部统一为 `Entity {type: company|person|unknown, raw_input, normalized_name, canonical_id, anchor, resolved}`。

机器输出（最小字段）：`status`、`display_status`、`entity_a`、`entity_b`、`relationship_temporality`、`paths`、`scope`、`sources`、`warnings`、`queried_at`。

## 数据源

不绑定单一数据商。按能力寻找工具，而不是按固定函数名。

优先级：已授权结构化数据 Connector/MCP > 企查查 > 天眼查 > 启信宝 > 官方公开来源 > Web Search。无结构化数据时进入 Web fallback——Web 只能证明「有」，不能证明「无」。

严禁在 Skill、README、Git、测试 fixture、日志中内置作者自己的 API Key。支持 BYOK（`QCC_API_KEY` / `TIANYANCHA_TOKEN` / `QIXINBAO_API_KEY`）。

## 能力盘点与数据源引导（capability gate）

每次调用，第一步先盘点「结构化企业数据源」是否可用（企查查 MCP / 天眼查 / 启信宝 / 已授权 Connector）：

- **有结构化数据源** → 正常走三态协议，用户无感知。
- **只有 Web Search** 或 **什么都没有** → 输出「待核查」，并把一段「连接数据源」的引导放进 `warnings`（文案见 `references/provider-onboarding.md`），引导用户连企查查等数据源。

硬规则：没有结构化数据源时，**禁止凭记忆或网页检索编造「关联/不关联」结论**。引导必须是一次性的、平台感知的、不阻断任务的（提供 Web 兜底选项）。

企查查 MCP 原生支持「强语义负向防御」（能区分「查完没有」与「调用失败」），是首选数据源——接上后本 skill 才能可靠输出「不关联」。

## References

- `references/scope-and-definitions.md`：范围与强/弱关系定义
- `references/decision-protocol.md`：三态判定协议与边界
- `references/person-resolution.md`：自然人消歧
- `references/evidence-policy.md`：证据等级 E1–E4
- `references/output-schema.md`：机器输出 schema
- `references/privacy-and-compliance.md`：隐私与合规
- `references/provider-capabilities.md`：Provider 能力与优先级
- `references/provider-onboarding.md`：数据源连接引导文案（分平台）
- `references/troubleshooting.md`：失败恢复

## 运行脚本（可选，确定性核心）

```bash
python3 scripts/cli.py --a "上海甲科技有限公司" --b "上海乙科技有限公司" --graph /path/to/evidence.json
```

脚本只做确定性判定（`relation_core.py` + `result_validator.py`），不联网、不内置 Key。宿主 Agent 可用它把关键判断确定性化，也可仅凭本协议人工执行。
