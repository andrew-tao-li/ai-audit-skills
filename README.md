# AI Audit Skill Pack

一组可独立安装、默认离线、结果可追溯的审计 Agent Skills（v0.2.0，canonical 版本）：

- `expense-audit-v2`：费用、报销与发票异常全量扫描。
- `procurement-fraud-v2`：采购舞弊红旗、供应商关系、价格、拆单、流程和标书相似度筛查。
- `investigation-assistant-v2`：把举报、邮件、消息和日志整理成证据清单、时间线与调查工作空间。

三个 skill 都遵循同一原则：确定性计算先行；事实、推断和假设分开；异常只用于确定复核优先级；正式 finding 必须能回到证据；最终认定由有权人员完成。

关键取舍及其理由见 [docs/design-decisions.md](docs/design-decisions.md)，安全与权限边界见 [docs/security-model.md](docs/security-model.md)。

## 快速体验

在仓库根目录运行：

```bash
python3 skills-v2/expense-audit-v2/scripts/run_expense_audit.py \
  --input skills-v2/expense-audit-v2/examples/input/expenses.csv \
  --policy skills-v2/expense-audit-v2/examples/input/policy.json \
  --output /tmp/expense-audit-demo

python3 skills-v2/procurement-fraud-v2/scripts/run_procurement_audit.py \
  --input-dir skills-v2/procurement-fraud-v2/examples/input \
  --config skills-v2/procurement-fraud-v2/examples/input/config.json \
  --output /tmp/procurement-audit-demo

python3 skills-v2/investigation-assistant-v2/scripts/build_case_workspace.py \
  --input-dir skills-v2/investigation-assistant-v2/examples/input \
  --scope skills-v2/investigation-assistant-v2/examples/input/scope.json \
  --output /tmp/investigation-demo
```

运行全部自动化测试：

```bash
python3 -m unittest discover -s skills-v2/expense-audit-v2/tests -v
python3 -m unittest discover -s skills-v2/procurement-fraud-v2/tests -v
python3 -m unittest discover -s skills-v2/investigation-assistant-v2/tests -v
python3 -m unittest discover -s evals/tests -v
python3 evals/validate_pack.py --run-tests
python3 evals/blackbox/score_blackbox.py --version v0.2.0-baseline
```

`evals/fixtures/` 另提供 6 个文件级正反向场景，专门验证正常数据零误报、坏行隔离、缺失可选表、中文字段映射、范围过滤、原件哈希/只读副本和未授权先拒绝。对 Agent 宿主生成的结果可运行：

```bash
python3 evals/verify_file_regression.py --root /path/to/host-output
```

生成某个宿主的 120 条路由验收记录表：

```bash
python3 evals/run_trigger_eval.py init \
  --host Codex \
  --host-version "填实际版本" \
  --output /path/to/codex-trigger-results.csv

# 在独立会话中逐条测试并填写 observed_skill 后评分
python3 evals/run_trigger_eval.py score \
  --input /path/to/codex-trigger-results.csv
```

脚本只使用 Python 标准库；读取 `.xlsx` 时额外需要 `openpyxl`。所有示例数据均为合成数据。

## 安装

每个 `skills-v2/<name>/` 文件夹都可以单独复制。各宿主的放置位置见 `adapters/`。Canonical skill 不依赖任何宿主私有字段；`agents/openai.yaml` 只提供 Codex/ChatGPT 的可选界面信息。

`dist-v2/` 提供按 skill 分开的 ZIP 快照（另见 GitHub Releases）。正式使用前仍应阅读 `SKILL.md`、检查脚本，并先运行包内合成样例。路由验收必须在独立的新会话中执行，不能在已透露预期 skill 的同一上下文里自测。

已完成的实机验证：Codex 项目级发现与安装路径执行通过；WorkBuddy 5.5.6 与 LobsterAI 2026.5.22 均已实际执行三个 skill 的综合样例，并分别完成 6/6 文件级回归。两端产物都通过统一校验器复核。LobsterAI 清理旧版后的 6 条隐式路由为 6/6，但调查助手有 1 条输入来源行为失败；本地 `investigation-assistant 0.1.2` 已修订，尚待宿主替换复测。正式 120 条/宿主的隐式路由验收、Pi 和 OpenClaw 实测仍未完成，详见 [测试摘要](evals/test-report-2026-09-15.md) 与 [跨 Agent 验收矩阵](evals/cross-agent-matrix.md)。

## 目录

```text
ai-audit-skills/
├── skills-v2/              三个独立 skill（v0.2.0 canonical）
├── docs/                   公共数据协议与方法边界
├── adapters/               各 Agent 的安装说明
├── dist-v2/                按 skill 分开的 ZIP 快照
└── evals/                  pack 级结构、黑盒评分、触发和跨 Agent 评估
```

当前版本：`expense-audit-v2`、`procurement-fraud-v2`、`investigation-assistant-v2`（均 0.2.0）。
