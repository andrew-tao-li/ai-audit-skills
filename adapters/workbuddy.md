# WorkBuddy 导入与验证

## 当前状态（推荐做法）

- **已在 WorkBuddy 5.5.6（macOS）实机确认**。
- **安装方式**：进入「专家·技能·连接器 → 技能 → 添加技能 → 上传技能」，选择包含 `SKILL.md` 的**文件夹或 ZIP**。
  - 每次只处理一个 skill；保持 `<skill-name>/SKILL.md` 与相对资源路径不变。
  - 四个 skill 都可装：`expense-audit-v2` / `procurement-fraud-v2` / `investigation-assistant-v2` / `cn-entity-relation-check`。
  - **版本请从 [releases/latest](https://github.com/andrew-tao-li/ai-audit-skills/releases/latest) 取当前版**，不要用早期 ZIP（各 skill 版本号见 `VERSIONS.json`）。
  - 也可以用「通过 URL 导入」直接填仓库地址，**不弹沙箱确认**，更省事——见 [install.md](../install.md)。
- **frontmatter**：canonical 只用开放规范字段；5.5.6 已实际接受并安装当前 ZIP，**不需要维护第二套工作流正文**。
  > 历史：旧版公开文档曾把 `description_zh` / `description_en` / `version` / `author` 列为必填。若未来某个 WorkBuddy 版本解析失败，再在创建界面做这些字段的映射即可，**正文与资源目录保持原样**。
- **安全检测**：WorkBuddy 会在安装前运行安全检测。首次上传曾遇到检测服务**超时**；在用户明确确认后跳过该次宿主检测，安装、发现、执行均正常。
  > ⚠️ 超时属**宿主服务状态**，不代表本包已通过 WorkBuddy 的自动安全扫描。正式部署仍应在服务可用时重新执行宿主安全检查。
- **安装后先自检**：先用包内合成 fixture 验证宿主能否运行 Python；不能则按 `SKILL.md` 的 Host Native profile，用表格 / 数据分析能力复现规则。
  只有真实生成核心产物、并核对 `evidence` / `run_manifest` / 边界措辞之后，才可标记 **Full Execution 通过**。
- **仍未完成**：每个 skill 20 正例 + 20 反例、共 **120 条/宿主**的正式隐式路由验收。

## 历史记录（2026-09）

- 2026-09-16：macOS、WorkBuddy 5.5.6 首次安装并执行；当时 3 个 skill（`0.1.1`）综合样例 3/3。
- 2026-09-17：文件级回归 6/6；两端产物都通过统一校验器复核。
- 当时调查助手暴露的「输入来源限制须先于文件系统探查」缺陷，已在后续版本修复——**当前版本（见 `VERSIONS.json`）早已覆盖，无需再关心 `0.1.2`**。
- 上述字段要求于 2026-09-15 按公开文档核对：[WorkBuddy Skill](https://open.workbuddy.cn/en/docs/skill)。

## 证据

- [WorkBuddy 实机测试记录](../evals/runs/workbuddy-smoke-2026-09-16.md)
- [文件级回归记录](../evals/runs/workbuddy-file-regression-2026-09-17.md)
