# AI Audit Skill Pack 开发约束

- 用户的明确指示优先于本文件和各 skill 的默认流程。
- 每个 skill 必须能脱离本仓库独立运行，不得引用 `../../shared`。
- 核心脚本不得调用大模型 API、上传数据、写入业务系统或保存密钥。
- 默认只读输入；输出必须写入用户指定的新目录，不覆盖原始资料。
- 先做数据体检和确定性分析，再由宿主 Agent 解释结果。
- `finding` 必须引用存在的 `evidence_id`；不得把异常、相似或关联写成舞弊认定。
- 事实、推断、假设和最终判断必须分开。脚本不产生最终责任判断。
- 新规则必须有合成数据正例、合理异常反例和可解释参数。
- 路径使用 `pathlib.Path`，文本使用 UTF-8，兼容 Windows、macOS 和 Linux。
- 修改后运行对应 skill 的单元测试及 `python3 evals/validate_pack.py`。
