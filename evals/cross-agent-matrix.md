# Cross-agent evaluation matrix

| Host | Discovery | Python execution | Trigger 40/skill | File/fixture execution | Schema/evidence | Result |
|---|---|---|---|---|---|---|
| Codex | 通过：项目级可发现 3 个 skill | 通过 | 待独立会话实测 | 原综合样例 3/3；新增文件场景 6/6 | 通过 | Full Execution 通过；正式路由待测 |
| Pi | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 |
| OpenClaw | 待测 | 待测 | 待测 | 待测 | 待测 | 待测 |
| WorkBuddy 5.5.6 / macOS | 通过：3 个 `0.1.1` skill 已安装 | 通过 | 6 条小样本 5/6；正式 40/skill 待测 | 原综合样例 3/3；新增文件场景 6/6 | 统一校验器通过 | Full Execution 通过；隐式路由部分通过 |
| LobsterAI 2026.5.22 / macOS | 通过：已清理 `0.1.0`，宿主当前为 `0.1.1` | 通过 | 清理后小样本：路由 6/6、行为 5/6；正式 40/skill 待测 | 原综合样例 3/3；`0.1.1` 新增文件场景 6/6 | 统一校验器通过 | Full Execution 通过；调查输入来源缺陷已在本地 `0.1.2` 修订，宿主待复测 |

每次测试必须记录宿主版本、操作系统、安装位置、调用方式、实际输出目录、失败原因和人工判断。不能运行 Python 的宿主应单独标记 Host Native/Reasoning Only，不与 Full Execution 混为同一结果。

## 已完成证据

- 本地确定性自动化测试共 23 项：三个 skill 的 15 项单元测试，加上 pack 级文件场景 6 项与路由工具 2 项，全部通过。
- 新增 6 个文件级场景，覆盖正常数据零误报、坏行隔离、缺失可选表、中文表头、默认值、范围排除、原件哈希/只读副本，以及未授权时不创建输出。
- WorkBuddy 与 LobsterAI 均在真实宿主中执行这 6 个场景，分别为 6/6 通过；宿主外统一校验器对两份输出均返回 `status: pass`。
- WorkBuddy 记录见 [文件级回归](runs/workbuddy-file-regression-2026-09-17.md)，LobsterAI 记录见 [文件级回归](runs/lobsterai-file-regression-2026-09-17.md)。

## 尚未完成

- Codex、WorkBuddy、LobsterAI 尚未完成每个 skill 20 个隐式正例和 20 个隐式反例，共 120 条/宿主的正式路由验收。
- Pi 与 OpenClaw 尚未安装和实机测试。
- `investigation-assistant 0.1.2` 尚未替换 LobsterAI/WorkBuddy 中的 `0.1.1`，新输入来源防护仍待宿主复测。

120 条路由测试必须让每条 prompt 进入不含预期答案的独立会话；显式点名 skill 的文件执行测试不能计入隐式路由准确率。
