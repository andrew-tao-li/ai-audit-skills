# 三态判定协议（decision-protocol）

内部状态：`RELATED` / `NOT_RELATED_IN_SCOPE` / `NEEDS_VERIFICATION`。

## RELATED（关联）

必须满足：存在有效强关系路径，且关键公司已锚定、关键自然人已消歧、证据可追溯、路径边属于允许强关系。

## NOT_RELATED_IN_SCOPE（不关联）

必须**同时满足全部 7 项**：

1. 两主体已唯一锚定（entities_resolved == true）
2. 使用了结构化工商数据源
3. 约定范围的强关系已完整查询（scope_complete == true）
4. Provider 无错误
5. 自然人无重名歧义
6. Provider 支持明确的 negative semantics（能区分「成功无结果」与「调用失败」）
7. 未发现任何符合强关系定义的路径

**缺任何一项，都只能「待核查」。**

## NEEDS_VERIFICATION（待核查）

以下任一情况均归入：自然人重名、公司实体未确认、只有 Web Search、Provider 调用失败、API Key 无效、超时、余额不足、权限不足、分页不完整、图查询提前达上限、只有弱线索、数据源冲突、历史/当前状态无法确认。

## 伪代码

```python
def decide(query, evidence, context):
    if not context.entities_resolved: return "NEEDS_VERIFICATION"
    if context.person_ambiguity: return "NEEDS_VERIFICATION"
    strong_paths = find_valid_strong_paths(...)
    if strong_paths: return "RELATED"
    if context.provider_error: return "NEEDS_VERIFICATION"
    if context.only_web_search: return "NEEDS_VERIFICATION"
    if not context.scope_complete: return "NEEDS_VERIFICATION"
    if not context.provider_supports_negative_semantics: return "NEEDS_VERIFICATION"
    return "NOT_RELATED_IN_SCOPE"
```

「不关联」的真实语义是「在本次数据源、关系范围、查询时间、最大深度内未发现关联」，不是「现实世界绝对无关」。
