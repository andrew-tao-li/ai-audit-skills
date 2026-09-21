# WorkBuddy 导入与验证

2026-09-16 在 macOS、WorkBuddy 5.5.6 实机确认：进入“专家·技能·连接器 → 技能 → 添加技能 → 上传技能”，可选择包含 `SKILL.md` 的文件夹或 ZIP。每次只处理一个 skill，保持 `<skill-name>/SKILL.md` 和相对资源路径不变。

WorkBuddy 在安装前会运行安全检测。首次上传 `expense-audit-0.1.1.zip` 时检测服务超时；在用户明确确认后跳过该次宿主检测，三个 `0.1.1` skill 均完成安装、发现和执行。安全检测超时是本次宿主服务状态，不代表包已通过 WorkBuddy 的自动安全扫描；正式部署仍应在可用时重新执行宿主安全检查。

本包的 canonical frontmatter 只使用开放规范字段；旧版公开文档曾把 `description_zh`、`description_en`、`version` 和 `author` 列为必填。WorkBuddy 5.5.6 已实际接受并安装当前 ZIP，因此不需要维护第二套工作流正文。若未来版本解析失败，再在创建界面映射中英文 description、metadata.version 和 metadata.author，正文与资源目录仍保持原样。

安装后先用包内合成 fixture 验证宿主是否能运行 Python；如果不能，按 `SKILL.md` 的 Host Native profile 使用表格/数据分析能力复现规则。只有真实生成核心产物并核对 evidence、manifest 和边界措辞后，才能标记 Full Execution 通过。本次宿主中的三个 `0.1.1` 综合样例为 3/3、文件级回归为 6/6，已达到该标准。当前新安装应改用 `investigation-assistant-0.1.2.zip`；该输入来源修订尚待 WorkBuddy 替换后复测。

上述字段要求于 2026-09-15 按公开文档核对：[WorkBuddy Skill](https://open.workbuddy.cn/en/docs/skill)。

本轮实机证据见 [WorkBuddy 实机测试记录](../evals/runs/workbuddy-smoke-2026-09-16.md) 与 [文件级回归记录](../evals/runs/workbuddy-file-regression-2026-09-17.md)。正式 120 条隐式路由验收仍未完成。
