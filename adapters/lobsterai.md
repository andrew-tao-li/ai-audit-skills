# LobsterAI / 有道龙虾导入与验证

## 当前状态（推荐做法）

- **已在 LobsterAI 2026.5.22（macOS）实测通过**首次安装与 Full Execution。
- **安装方式**：
  1. 打开「技能」。
  2. 选择「添加 → 上传 .zip」。
  3. 逐个上传四个 skill 的当前版本 ZIP：`expense-audit-v2` / `procurement-fraud-v2` / `investigation-assistant-v2` / `cn-entity-relation-check`。
     **版本从 [releases/latest](https://github.com/andrew-tao-li/ai-audit-skills/releases/latest) 取**（不要用早期 `0.1.x` 包；各 skill 版本见 `VERSIONS.json`）。
  4. 每次确认界面出现「技能已添加」，并核对名称、版本、描述与已安装数量。
- 四个包都会被安装到 LobsterAI 的本地 Skill 目录，能读取 `SKILL.md`、运行包内 Python 脚本。**本包不需要 LobsterAI 专用分支。**

## ⚠️ 版本升级注意事项（实测踩过）

同日把新版 ZIP 上传到**已有旧版**的宿主时，LobsterAI **不会原位覆盖**，而是**新增同名条目**——界面会同时保留两个版本。
> 双版本状态下，宿主**可能仍读到旧版**。**不要把「技能已添加」当成「升级已完成」。**

正确做法：
1. 先核对新包校验值、留好可恢复副本；
2. 在宿主中**移除旧版、仅保留目标版本**（删除会改变宿主状态，需用户明确确认）；
3. 再重跑显式 fixture 与隐式路由用例。

## 运行建议

- 第一次只跑各 skill 的 `examples/input` 合成样例；确认产物、边界措辞与 `network_access:false` 后，再处理组织数据。
- **输出目录用全新目录**。若工作目录或路径含空格，给完整路径加引号，或先在当前任务工作区建一个短的启动脚本；**不要**因此改写源数据。
- CSV/TXT 核心流程可直接运行；**XLSX 仍需宿主 Python 环境具备 `openpyxl`**。
- 不要把真实调查材料上传到尚未确认数据处理、保留与权限边界的环境。
- 若某个 LobsterAI 版本不再提供 ZIP 导入或本地 Python，则明确标记为 **Host Native / Reasoning Only**，不要假设 Full Execution 仍兼容。

## 历史记录（2026-09）

- 2026-09-16：macOS、LobsterAI 2026.5.22 首次安装并执行；初次综合样例使用 `0.1.0`。
- 清理旧版后，`0.1.1` 完成 6/6 文件级回归；清理后小样本隐式路由 6/6、行为 5/6（正式 120 条仍未完成）。
- 当时暴露的「调查助手输入来源行为」缺陷已在后续版本修复——**当前版本早已覆盖，无需再关心 `0.1.2`**。
- 背景资料可参考 [YoudaoNote 龙虾类 Agent 指南](https://note.youdao.com/help-center/skill-install-guide-agent.html)；**本页安装结论以本项目的实机记录为准**。

## 证据

- [LobsterAI 冒烟测试记录](../evals/runs/lobsterai-smoke-2026-09-16.md)
- [文件级回归记录](../evals/runs/lobsterai-file-regression-2026-09-17.md)
- [LobsterAI 路由小样本记录](../evals/runs/lobsterai-route-smoke-2026-09-16.md)
