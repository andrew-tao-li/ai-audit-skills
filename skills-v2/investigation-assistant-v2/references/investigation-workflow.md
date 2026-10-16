# Investigation workspace contract

## Timeline

字段：`timestamp`、`actor`、`event_type`、`object`、`source_file`、`source_row`、`evidence_id`、`confidence`。排序只使用成功解析的时间戳；每行必须能回到 evidence。

## Entity and relationship

实体只来自结构化字段或明确格式（员工编号、邮件地址、设备、文档），不猜同名关系。关系边至少包含 `source`、`target`、`type`、`evidence_refs`。

## Evidence matrix

每个 scope issue 一行：`issue_id`、`allegation_or_issue`、`supporting_evidence_refs`、`contradictory_evidence_refs`、`missing_evidence`、`alternative_explanations`、`status`。关键词命中只是候选证据，必须回到上下文确认。

## Hypothesis register

包含 hypothesis、支持证据、反证、缺失证据、可替代解释、下一步验证和状态。初始状态保持 `open`。不要把举报表述复制到 facts。

## Interview plan

按 scope 中 interviewees 生成：访谈对象、目标、已知事实、未知事实、问题、拟出示材料、触发追问条件。访谈前由有权人员确认次序、保密和劳动法/隐私要求。

## Findings

每个 issue 可形成一条 `investigation-lead`：facts 仅来自候选记录，inferences 只说明关键词检索连接，hypotheses 放待验证指控；没有最终 judgment。风险优先级沿用 scope 的人工设定或默认 medium，不由关键词数量自动升级。

---

## v0.2.7 新增：三个**可选**开关（不配置 = 与 0.2.6 逐字节一致）

> 这三个开关来自对 `sxd007/investigation-ontology` 方法论的研究与吸收（**只学思路、自行实现**）。
> 全部写在 `scope.json` 里；**不写就完全不会出现在产出里**。

| 开关 | 取值 | 作用 | 产出变化 |
|---|---|---|---|
| `evidence_tiers` | `{"来源文件名": "HARD\|SOFT\|LEAD"}` | 给证据分强度等级 | `evidence_matrix.csv` 增一列 `evidence_tier`（取该事项支持证据中**最强**的等级；未映射的来源记 `UNSPECIFIED`） |
| `deduplicate_sources` | `true` / `false` | 同源去重：同一来源衍生的多份材料**不算独立印证** | `evidence_matrix.csv` 增一列 `independent_source_count`（该事项支持证据涉及几个**不同来源文件**） |
| `hypothesis_extended` | `true` / `false` | 可证伪化 | `hypothesis_register.csv` 增 `refutation_criteria`、`discriminating_evidence` 两列；**并为每条 `alternative_explanations` 生成一条独立的反方假设行** |

### 证据分级怎么用（HARD / SOFT / LEAD）

| 等级 | 含义 | 可否独立支撑认定 |
|---|---|---|
| `HARD` | 有原始证据直接证明（银行流水、系统日志、合同原件） | ✅ |
| `SOFT` | 多源间接关联（同电话、同地址、同 IP） | ❌ 仅作辅助线索 |
| `LEAD` | 单点弱信号 / 外部情报 / 举报线索 | ❌ 仅作侦查方向 |
| `UNSPECIFIED` | 未在 `evidence_tiers` 中映射的来源 | ❌ 先按未分级处理 |

> **当 `evidence_tiers` 开启、且某事项的最高等级不是 `HARD` 时**，脚本会在该事项 finding 的
> `open_questions` 里附一条提示：**「不能独立支撑认定；需补充直接证据后再定性」**。
> **脚本只提示，不改结论、不下判断。**

### 反方假设的生成约束（**务必遵守**）

开启 `hypothesis_extended` 后，`hypothesis_register.csv` 中：

1. **必须至少有一条真正挑战核心命题的假设**——即由 `alternative_explanations` 生成的独立反方假设行；
2. 反方假设与指控性假设**同等优先级**验证，不得只做形式登记；
3. 「举报人动机不纯」**不是**「举报不真实」的替代假设；
4. 假设状态（confirmed / rejected）**必须由调查员人工确认**，脚本只登记。

> 缺口如何归因、以及"不利推定"的严格前置条件，见 [证据缺口与不利推定边界](evidence-gaps.md)。
