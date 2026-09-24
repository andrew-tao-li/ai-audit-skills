# Changelog

## v0.3.0 — 2026-09-24（pack release）

包级发布：发布标签对齐内容版本，收口上一阶段的所有增量。

- **第 4 个 skill 上线**：`cn-entity-relation-check`（关联排查 v0.1.0）——三态判定协议 + capability gate + 分平台数据源引导。
- **expense-audit-v2 0.2.1**：修 missing-expense-type max/min bug；新增时空冲突 / 跨期入账 / 高频小额三规则；业务实质性声明。
- **黄金测试集**：expense 22→25 fixture，F1 全 100%。
- **文档**：install.md / README 的版本号与 skill 计数（3→4）对齐；ZIP 直链补上第 4 个 skill。

## v0.2.1 — 2026-09-24（expense-audit-v2）

由真实审计师提供的「16 场景带答案」数据（`出差费用模拟数据.xlsx`，含「审计说明」答案表）驱动。

- **修复 bug**：`missing-expense-type` 计算「最严格上限」误用 `max()` 应为 `min()`（单限额时不暴露，多限额时漏报）。
- **新增三条规则**（均为真实盲点）：
  - `space-time-conflict`（时空冲突）：同一员工同一天在多个城市产生定位型消费。
  - `cross-period`（跨期入账）：提交日期距费用发生超过 N 个月（`cross_period_months`，默认 3）。
  - `high-frequency-small-amount`（高频小额）：同一员工短期内 ≥N 笔同类型小额（`high_frequency_min_count`/`window_days`/`max_amount`）。
- **新增字段别名**：`origin_city`（出发城市）、`dest_city`（目的城市）。
- **黄金测试集**：expense 22→25 fixture（新增 13/14/15 三个新规则回归用例），F1 保持 100%。
- **外部盲测基准**：新增 `evals/blackbox/expense/auditor-scenario/`（行级覆盖率评分器），16/16 场景检出。
- **业务实质性声明**：由审计师口头反馈驱动，在 `summary.md` 新增结构化「业务实质性声明」（数据匹配 ≠ 业务实质、未发现 ≠ 没问题、附深入核查佐证清单）；新增 `references/business-substance.md`；SKILL.md 补充原则并更新人工复核必查项表（频繁小额/跨期入账现标为已支持）。

## v0.2.0 — 2026-09-22（canonical）

- **v0.2.0 成为唯一 canonical 版本**：`skills-v2/` 取代 `skills/`，`dist-v2/` 取代 `dist/`。v0.1.x（`skills/`、`dist/`）已退役删除。
- 三个 skill 命名为 `expense-audit-v2` / `procurement-fraud-v2` / `investigation-assistant-v2`。
- 黑盒黄金测试集 F1 全部 100%（expense 16 / procurement 8 / investigation 3 fixture）。
- 修完 11 个复合场景暴露的失败：校准 split-expense、robust-outlier、sequential-invoice、near-duplicate、split-order、price-outlier、process 流程检测器；补全 2 处 ground truth。
- `opencode.json` 注册 `skills-v2/`；`validate_pack.py` 与 `trigger-prompts.jsonl` 同步到 v2 命名。

### 面向审计人员的输出体验（专项）

- **P0 审计语言翻译**：`facts` 去掉数据分析术语（MAD / robust z-score / peer group / 容差 / 窗口），改为审计语言（如「是同类费用正常水平的约 X 倍」「金额接近、集中在 N 天内」）；`risk_factors` 剥离内部参数（robust_z、peer_group、run_length 等），只保留规则名 + 分值。
- **P1 输出分层**：`summary.md` 明确区分「审计结论（summary/findings）」与「技术审计轨迹（data_quality/run_manifest/clean/bad/evidence）」；`data_quality.md` 与 `run_manifest.json` 标注「技术附录，非审计结论」。
- **P2 中文化**：`summary.md` 的「发现类型」「风险优先级」从英文 key 改为中文审计术语（`cross-employee-invoice`→`发票跨人复用`、`high/medium/low`→`高/中/低`）；`finding_type` 英文 key 保留在 findings 里供黑盒评分比对。
- **安装鲁棒性**：`install.sh` 下载改用目标目录（不用 mktemp，避开 Windows 沙箱拦截）；版本探测加 User-Agent、用 sed 替代 python3、重定向改 GET；支持位置参数选子集 + 校验 skill 名 + 自动探测 Agent。

## Unreleased — 2026-09-17

- 新增 6 个文件级正反向回归场景及 `expectations.json`，覆盖正常对照、坏行隔离、缺失可选表、范围过滤、只读证据副本和未授权拒绝。
- 新增 pack 级文件测试类；自动化测试由 17 项增至 23 项。
- 新增跨宿主产物统一校验器 `evals/verify_file_regression.py`。
- 在 WorkBuddy 5.5.6 与 LobsterAI 2026.5.22 上分别完成 6/6 文件级回归，并更新测试摘要和跨 Agent 矩阵。
- 清理 LobsterAI 中并存的旧 `0.1.0` 条目，确认单版本 `0.1.1` Full Execution 通过。
- 清理后重跑 LobsterAI 的 6 条隐式路由小样本：路由 6/6、行为 5/6。

## investigation-assistant 0.1.2 — 2026-09-17

- 根据 LobsterAI 行为复测，把输入来源限制提升到 scope gate 前置要求。
- 当前任务未提供 scope 和案件材料时，明确禁止先浏览工作区、包内 `examples/` 或历史案卷；必须直接索取当前输入。
- 脚本与 manifest 版本同步为 `0.1.2`；算法和输出 schema 未改变。

## 0.1.1 — 2026-09-16

- 在 LobsterAI 2026.5.22 完成三个 ZIP 的导入和 Full Execution 合成样例实测。
- 根据隐式路由实测，扩充 `expense-audit` 的数据清洗/坏行/标准化触发描述。
- 明确当前任务没有附件、路径或粘贴数据时，不得搜索工作目录或复用历史输出。
- 记录 LobsterAI 同名版本并存问题与 6 条隐式路由小样本结果，不把上传成功误判为升级成功。
- 在 WorkBuddy 5.5.6 实测 ZIP 上传入口和安装前安全检测；本次检测服务超时，后续安装需单独确认。
- 更新 LobsterAI、WorkBuddy 适配说明、跨 Agent 验收矩阵和实机测试记录。

## 0.1.0 — 2026-09-15

- 首次发布 `expense-audit`、`procurement-fraud` 和 `investigation-assistant`。
- 提供离线确定性脚本、合成正反例、端到端测试和统一输出契约。
- 提供 Codex、Pi、OpenClaw、WorkBuddy、LobsterAI 适配说明与跨 Agent 验收矩阵。
- 明确异常仅为人工复核线索，禁止自动作出舞弊、串标、有罪、停付或处分结论。
