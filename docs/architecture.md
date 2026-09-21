# 架构与运行 Profile

## 分工

```text
业务数据 → 体检/标准化 → 规则/统计/文本/关系分析 → Finding + Evidence
                                                        ↓
                                             宿主 Agent 解释与补证计划
                                                        ↓
                                                   人工判断
```

脚本负责可重复的计算；宿主 Agent 负责理解制度、归纳模式、提出开放问题和起草沟通材料；有权人员负责调查决定、责任认定和处置。

## 三种运行 Profile

- Full Execution：有 Python 和本地文件能力，运行随 skill 提供的脚本。
- Host Native：不能运行 Python，但有表格或 SQL 工具，按 `SKILL.md` 与数据协议复现同一规则和输出。
- Reasoning Only：只获得少量粘贴数据时，仅做局部分析，明确覆盖范围，不推断全量异常率。

每个 skill 可单独复制运行。跨 skill 只通过版本化 JSON handoff 交换信息，不直接引用另一个 skill 的代码。
