# Evaluation design

## 自动化层

每个 skill 的 `tests/test_*.py` 使用独立临时目录运行合成 fixture，检查：

- 正例是否命中关键规则；
- 合理异常反例是否保持低优先级或被白名单排除；
- finding/evidence/graph/timeline 引用是否完整；
- manifest 是否记录离线运行、参数和输入 hash；
- 授权 gate、非空输出目录等停止条件是否生效。

`evals/fixtures/` 另提供跨 skill 的文件级回归数据，`evals/tests/test_file_scenarios.py` 对 `expectations.json` 中的可观察结果作精确断言。这里同时包含正常对照和故意损坏的数据，避免只验证“能否报出异常”。

`validate_pack.py` 负责结构、frontmatter、progressive disclosure、触发样例数量、私有模型 SDK/网络库、绝对路径和界面元数据检查。

Agent 宿主执行同一批文件场景后，使用 `verify_file_regression.py --root <宿主输出根目录>` 独立复核实际产物。校验器不采信宿主的自然语言总结，而是重新读取 manifest、CSV/JSONL、哈希和文件权限。

## Trigger eval

`trigger-prompts.jsonl` 为每个 skill 提供 20 个应触发和 20 个不应触发 prompt。跨 Agent 人工评估时记录：是否选中正确 skill、是否误触发相邻 skill、是否加载完整 SKILL.md。

用 `run_trigger_eval.py init` 生成记录表。每条 prompt 必须进入独立新会话，测试人员只能看到 prompt，不应把 `expected_trigger` 或目标 skill 暴露给被测 Agent。完成后填写 `observed_skill` 为实际选中的 skill、`none` 或 `other`，再用 `run_trigger_eval.py score` 计算混淆矩阵。空白结果一律算未测试，不能算作正确拒绝。

## 行为评估

不要只对比文字。至少检查：

- 实际运行了哪条确定性脚本；
- 输出文件是否齐全；
- 同一 fixture 的关键 finding 类型和 evidence 是否一致；
- 是否把异常升级为舞弊认定；
- 是否报告数据质量、跳过模块和覆盖范围；
- 调查流程是否尊重授权、人员和时间范围。

## 隔离

所有 eval 使用合成数据与新的临时输出目录。真实数据、外部联网、业务系统写回和对人员的联系不属于自动化测试范围。
