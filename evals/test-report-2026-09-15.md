# AI Audit Skill Pack 0.1.x 测试摘要

测试期间：2026-09-15 至 2026-09-17  
范围：`expense-audit`、`procurement-fraud`、`investigation-assistant`  
原则：把“技能能否发现/回答”与“技能能否处理真实文件并生成可复核产物”分开计分。

## 总结

| 层级 | 范围 | 结果 |
|---|---|---|
| 本地自动化 | 3 个 skill 单元测试 + pack 级文件场景 + 路由工具 | 23/23 PASS |
| 原综合样例 | Codex、WorkBuddy、LobsterAI 的完整正向样例 | 每个已测宿主 3/3 PASS |
| 新文件级回归 | 正常对照、脏数据、范围过滤、拒绝未授权 | WorkBuddy 6/6；LobsterAI 6/6 |
| 宿主外产物复核 | 对两端实际输出运行同一校验器 | 2/2 PASS |
| 隐式路由小样本 | 每个 skill 1 正 1 反，共 6 条/宿主 | WorkBuddy 路由 5/6；LobsterAI 清理后路由 6/6、行为 5/6 |
| 正式隐式路由 | 每个 skill 20 正 + 20 反，共 120 条/宿主 | 尚未完成 |

“文件级回归”是本轮新增的实质性测试：输入是 CSV、JSON 和 TXT，测试会实际运行 skill 脚本并读取产物，不以回答措辞作为通过条件。

## 23 项本地自动化测试

| 测试组 | 结果 |
|---|---|
| `expense-audit` | 4/4 PASS |
| `procurement-fraud` | 5/5 PASS |
| `investigation-assistant` | 6/6 PASS |
| 新增文件场景 | 6/6 PASS |
| 路由验收工具 | 2/2 PASS |

整包结构、脚本语法、禁止网络/模型 SDK、密钥模式、120 条触发数据集数量与正反例平衡也由 `evals/validate_pack.py --run-tests` 检查。每个 skill 的 `SKILL.md` 仍低于 500 行，测试样例与脚本均随包存在。

`investigation-assistant-0.1.2.zip` 另做了解压后独立校验：Skill Creator 结构校验通过，包内 6 项调查单元测试全部通过，SHA-256 已写入 `dist/SHA256SUMS`。

## 新增文件场景覆盖

### expense-audit

- `clean-control`：使用中文字段名，6 条正常工作日费用应全部有效，0 坏行、0 finding、0 evidence。用于检验字段别名和零误报。
- `dirty-input`：同时包含非法日期、非法金额、缺失员工号和空币种。期望 2 条有效、3 条隔离，空币种默认 CNY，坏行不能进入标准化结果。

### procurement-fraud

- `clean-control`：供应商、采购单、员工、付款和投标五张表全部提供；正常数据不得产生 finding，handoff 必须为 `not_recommended`。
- `dirty-input`：必需表中放入 3 条坏行，只提供供应商和采购单；脚本既要保留有效行，也要明确记录 employees/payments/bids 未提供，不能静默跳过或拼凑历史数据。

### investigation-assistant

- `scope-filter`：三个原始文件正常登记，但四条结构化记录全部超出人员或日期范围。期望时间线为 0、越界表为 4、finding 为 0，同时原件副本哈希一致且只读。
- `authorization-denied`：`authorization_confirmed:false`。期望返回码 2，错误信息明确，且在拒绝前不创建输出目录、不登记或复制证据。

场景文件见 [fixtures/README.md](fixtures/README.md)，机器断言见 [tests/test_file_scenarios.py](tests/test_file_scenarios.py)。

## WorkBuddy 实机结果

- 三个 `0.1.1` skill 已完成安装、发现和本地 Python 执行。
- 原综合样例 3/3 通过。
- 新文件级回归 6/6 通过。
- 独立校验器对输出返回 `status: pass`。
- 6 条隐式路由小样本为 5/6，费用正例漏触发。

详情见 [WorkBuddy 文件级回归](runs/workbuddy-file-regression-2026-09-17.md) 和 [WorkBuddy 实机记录](runs/workbuddy-smoke-2026-09-16.md)。

## LobsterAI 实机结果

- 已清理旧 `0.1.0` 条目，仅保留三个 `0.1.1` skill。
- 原综合样例 3/3 通过；`0.1.1` 新文件级回归 6/6 通过。
- 独立校验器对输出返回 `status: pass`。
- 清理后 6 条隐式路由小样本为路由 6/6、行为 5/6。
- 行为失败来自调查正例：宿主正确加载 skill，但仍浏览工作目录和包内示例后才索取 scope 与材料。未执行案件脚本，也未生成案件工作空间。
- 该缺陷已推动本地 `investigation-assistant 0.1.2` 增加前置输入来源限制；宿主仍安装 `0.1.1`，修复复测待完成。

详情见 [LobsterAI 文件级回归](runs/lobsterai-file-regression-2026-09-17.md)、[LobsterAI Full Execution](runs/lobsterai-smoke-2026-09-16.md) 和 [LobsterAI 路由小样本](runs/lobsterai-route-smoke-2026-09-16.md)。

## 已验证的边界

- 正常对照数据可以得到零 finding，避免只测“能否报异常”。
- 坏行会被隔离并保留原因；有效行继续处理。
- 缺失可选采购表会被明确标记，不搜索目录或复用历史输出。
- 调查范围外记录单列，不进入时间线；原始证据副本经过哈希核对并设置只读。
- 未授权调查在创建输出前停止。
- 所有 finding 都是复核线索，不自动形成舞弊、串标、有罪、停付、拒付或处分结论。

## 未完成事项

- Codex、WorkBuddy、LobsterAI 各自的 120 条正式隐式路由验收尚未完成。
- `investigation-assistant 0.1.2` 尚未替换两个宿主中的 `0.1.1`，输入来源修复尚未做宿主级复测。
- Pi 与 OpenClaw 尚未实机安装和测试。
- 当前文件回归使用合成数据；真实机构数据仍需在授权、脱敏、制度配置和人工复核条件下另行试点。

## 第一版限制

- 核心脚本直接支持 CSV/XLSX/TXT/MD；PDF、OCR、邮箱专有归档和 Office 文档需由宿主先做可追溯提取。
- 供应商实体连接以规范化后的精确属性为主，不自动执行模糊主体合并。
- 不访问工商、税务、制裁名单、汇率或其他外部数据源。
- 统计与文本规则是可解释 baseline，需要用组织制度和历史数据校准阈值。
- 文件系统只读用于防误改，不等于司法封存或不可篡改存储。
