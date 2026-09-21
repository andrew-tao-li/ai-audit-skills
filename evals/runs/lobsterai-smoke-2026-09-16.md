# LobsterAI 2026.5.22 冒烟测试记录

测试日期：2026-09-16  
宿主：LobsterAI 2026.5.22，macOS  
测试数据：三个 ZIP 包内自带的纯合成样例  
测试目标：验证 ZIP 导入、Skill 元数据解析、本地 Python 执行、产物生成和不过度结论边界  

## 安装结果

通过“技能 → 添加 → 上传 .zip”逐个导入三个发布包。三次均显示“技能已添加”；已安装数量由 39 增至 42。

| Skill | 版本 | 名称与描述 | 结果 |
|---|---:|---|---|
| `expense-audit` | 0.1.0 | 正确解析 | 通过 |
| `procurement-fraud` | 0.1.0 | 正确解析 | 通过 |
| `investigation-assistant` | 0.1.0 | 正确解析 | 通过 |

## 执行结果

每项在一个新的 LobsterAI 任务中显式点名 skill。宿主均先读取安装目录中的 `SKILL.md`，再调用包内脚本。本轮是 Full Execution 冒烟测试，不计入隐式路由准确率。

### expense-audit

- 输入：`examples/input/expenses.csv` 与 `policy.json`。
- 结果：14 条有效记录、1 条坏行、15 条 finding、72 条 evidence。
- 规则：发票号精确重复、同员工同日同金额、近似重复、制度阈值、拆单、MAD 离群、周末弱信号。
- 产物：`summary.md`、`findings.csv/jsonl`、`evidence.jsonl`、`data_quality.md`、`clean_expenses.csv`、`bad_rows.csv`、`run_manifest.json`。
- 边界：最终回答使用“异常线索”“复核建议”，未作舞弊或拒付结论。
- 兼容性观察：宿主在包含空格的安装路径上尝试了多个命令写法，最终通过任务工作区内的启动脚本成功执行。适配说明已补充完整路径引用建议。

### procurement-fraud

- 输入：5 个供应商、10 个采购订单、2 个员工、2 笔付款、6 条投标记录、3 份投标文本。
- 结果：10 条红旗/待复核线索、71 条 evidence；风险等级为高 1、中 7、低 2。
- 规则：共享银行账号、员工与供应商共享电话、价格离群、拆单、流程倒置、采购集中度、投标文本相似、报价模式。
- 产物包括：`findings.csv/jsonl`、`evidence.jsonl`、`relationship_graph.json`、`investigation_handoff.json`、数据质量报告与运行清单。
- 边界：明确说明红旗不能自动证明串标、利益输送或舞弊；调查移交仍需人工批准。

### investigation-assistant

- Scope gate：样例明确 `authorization_confirmed:true`，限定人员、期间、来源和 `network_access:false`。
- 输入：`complaint.txt`、`messages.csv`、`logs.csv`，共 3 个原始文件。
- 结果：建立 4 条时间线记录，2 条越界记录进入隔离清单。
- 完整性：为 3 个原始文件生成 Evidence ID 与 SHA-256；复制到 `evidence/raw/` 后哈希验证一致。
- 产物包括：证据清单、保管链、只读副本、标准化派生数据、时间线、实体关系、证据矩阵、假设登记、访谈计划、memo 模板和运行清单。
- 边界：保留支持证据、反证和缺失证据；未联网、未联系对象、未删除证据、未作责任或处分结论。

## 判定

三个 skill 在 LobsterAI 2026.5.22 上均达到 Full Execution 冒烟测试通过标准：能安装、能被读取、能实际执行、能生成合同约定的核心产物，并保持人工复核和授权边界。

未完成项：每个 skill 的 20 个隐式正例和 20 个隐式反例尚未在互相隔离的 LobsterAI 新任务中逐条运行；不得把本记录的显式点名调用计入该指标。

## 0.1.1 升级补记

同日在已有三个 0.1.0 条目的环境上传三个 0.1.1 ZIP。三次均显示“技能已添加”，但宿主没有覆盖旧版，而是把已安装数量从 42 增至 45，并同时显示两个版本。双版本状态下的费用隐式正例仍未读取 skill，而是搜索并复用旧输出。

因此本页的 Full Execution 通过结论只对应 0.1.0 首装环境；0.1.1 的有效升级验证需在仅保留目标版本后重做。隐式小样本、问题和修订见 [LobsterAI 路由小样本记录](lobsterai-route-smoke-2026-09-16.md)。

## 2026-09-17 更新

旧版条目已经清理，LobsterAI 目前只保留三个 `0.1.1` skill。随后完成 6 个文件级回归场景，全部通过，并经宿主外统一校验器复核。由此，`0.1.1` 的 Full Execution 状态已从“待清理后复测”更新为“通过”。详情见 [LobsterAI 文件级回归测试](lobsterai-file-regression-2026-09-17.md)。

该更新不改变隐式路由结论：清理后尚未重跑路由小样本，正式 120 条路由验收也仍未完成。
