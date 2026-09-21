# LobsterAI / 有道龙虾导入与验证

## 已验证方式

2026-09-16 在 macOS、LobsterAI 2026.5.22 实测通过首次安装和 Full Execution：

1. 打开“技能”。
2. 选择“添加 → 上传 .zip”。
3. 逐个选择当前推荐的 `dist/expense-audit-0.1.1.zip`、`dist/procurement-fraud-0.1.1.zip` 和 `dist/investigation-assistant-0.1.2.zip`。
4. 每次确认界面出现“技能已添加”，并核对名称、版本、描述和已安装数量。

三个包都被安装到 LobsterAI 的本地 Skill 目录，并能读取 `SKILL.md`、运行包内 Python 脚本。本包不需要维护 LobsterAI 专用分支。初次综合样例使用 `0.1.0`；清理旧版后，`0.1.1` 又完成 6/6 文件级回归。

## 版本升级注意事项

同日把 0.1.1 ZIP 上传到已有 0.1.0 的宿主时，LobsterAI 没有原位覆盖，而是新增三个同名条目；已安装数量由 42 增至 45，界面同时保留两个版本。双版本状态下的费用正例仍没有稳定读取 0.1.1，因此不要把“技能已添加”当作“升级已完成”。

升级时应先确认新包校验值和可恢复副本，再在宿主中移除旧版、仅保留目标版本，然后重新运行显式 fixture 与隐式路由用例。删除旧版会改变宿主状态，应由用户明确确认后执行。本次已在用户确认后完成旧版清理，宿主当前保留三个 `0.1.1` skill；显式文件执行和 6 条隐式路由已经复测。调查正例暴露的输入来源行为问题已在本地 `investigation-assistant 0.1.2` 修订，仍需替换宿主版本后复测。

## 运行建议

- 第一次只运行各 skill 的 `examples/input` 合成样例；确认产物、边界措辞和 `network_access:false` 后再处理组织数据。
- 输出目录使用全新目录。若工作目录或路径含空格，给完整路径加引号，或先在当前任务工作区创建一个短的启动脚本；不要因此改写源数据。
- CSV/TXT 核心流程可直接运行；XLSX 仍需宿主 Python 环境具备 `openpyxl`。
- 不要把真实调查材料上传到尚未确认数据处理、保留和权限边界的环境。
- 若某个 LobsterAI 版本不再提供 ZIP 导入或本地 Python，则明确标记为 Host Native / Reasoning Only，不要假设 Full Execution 仍兼容。

完整执行结果见 [LobsterAI 冒烟测试记录](../evals/runs/lobsterai-smoke-2026-09-16.md) 和 [文件级回归记录](../evals/runs/lobsterai-file-regression-2026-09-17.md)，隐式小样本与升级问题见 [LobsterAI 路由小样本记录](../evals/runs/lobsterai-route-smoke-2026-09-16.md)。背景资料仍可参考 [YoudaoNote Skills 龙虾类 Agent 指南](https://note.youdao.com/help-center/skill-install-guide-agent.html)，但本页的安装结论以本项目的 2026-09-16 至 2026-09-17 实测为准。
