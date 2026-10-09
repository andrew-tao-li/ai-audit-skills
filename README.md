# AI Audit Skill Pack

一组可独立安装、默认离线、结果可追溯的审计 Agent Skills（最新版见 [releases/latest](https://github.com/andrew-tao-li/ai-audit-skills/releases/latest)）。**分析脚本本身离线**；唯一的联网动作是**可选的版本检查**（只读一个公开的版本号文件，可关闭），每个 skill 的 `SKILL.md` 开头都有「**联网与风险（必读）**」把边界说清：

- `expense-audit-v2`：费用、报销与发票异常全量扫描。
- `procurement-fraud-v2`：采购舞弊红旗、供应商关系、价格、拆单、流程和标书相似度筛查。
- `investigation-assistant-v2`：把举报、邮件、消息和日志整理成证据清单、时间线与调查工作空间。
- `cn-entity-relation-check`：核查两个公司/自然人的中国公开工商关联，输出关联/不关联/待核查。

四个 skill 都遵循同一原则：确定性计算先行；事实、推断和假设分开；异常只用于确定复核优先级；正式 finding 必须能回到证据；最终认定由有权人员完成。

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
python3 evals/blackbox/score_blackbox.py --version local-check
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

三种方式，按你的 Agent 选：

**① 一句话安装（curl 兜底，任何 Agent 通用）**

```bash
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash -s -- expense-audit-v2
```

只装一个就把 `expense-audit-v2` 换成你要的（`procurement-fraud-v2` / `investigation-assistant-v2` / `cn-entity-relation-check`）；不带参数就是装全部 4 个。脚本会自动取 GitHub 最新版、检测 Agent 类型、装到对应 skills 目录。详见 [install.md](install.md)。

**② 平台原生导入（WorkBuddy / 有道龙虾推荐，不弹沙箱）**

- **WorkBuddy**：技能管理 → 「通过 URL 导入」→ 填 `https://github.com/andrew-tao-li/ai-audit-skills`（或某个 skill 子目录，如 `…/tree/main/skills-v2/expense-audit-v2`）。
- **有道龙虾（LobsterAI）**：Skill Store 直接装，或 `clawhub install expense-audit-v2`（**通道已就绪、尚未上架**）。
- **豆包 / 豆包工作**：把 skill 目录复制到工作区的 `.user_skills/` 下。**注意这是两个产品、两套目录**——「豆包工作」用 `DoubaoWork\…\.doubaowork\…`，个人版「豆包」用 `Doubao\…\.doubao\…`（Windows 在 `%LOCALAPPDATA%` 下，macOS 在 `~/Library/Application Support/` 下）。用安装脚本亦可：`HOST=doubao`（Windows 见下方「Windows 用户」）。
- **Windows 用户**：`install.sh` 是 bash 脚本，需要 Git Bash / WSL。没有 bash 请用同目录的 `install.ps1`（PowerShell），或直接「浏览器下载 release zip + 解压」——见 [install.md](install.md)。

每个 skill 根目录带 `manifest.json`（id/name/version/description/author/type/triggers/tags/license），WorkBuddy / ClawHub 直接认。

**③ 手动复制 / ZIP**

每个 `skills-v2/<name>/` 文件夹可单独复制（各宿主放置位置见 `adapters/`）；`dist-v2/` 提供按 skill 分开的 ZIP 快照（另见 GitHub Releases）。正式使用前仍应阅读 `SKILL.md`、检查脚本，并先运行包内合成样例。路由验收必须在独立的新会话中执行，不能在已透露预期 skill 的同一上下文里自测。

**已完成、且每日自动复跑的验证**：

- **黑盒 F1**：expense 25 / procurement 14 / investigation 3 个黄金测试集，全部 **100%**。
- **OpenCode 全自动验收**（`evals/cross-agent/`）：**4/4** —— 在真实 Agent 上验证「该触发时是否加载正确 skill、是否执行脚本、是否产出预期文件」，含一条负面对照。
- **安装冒烟**（`evals/install_smoke.py`）：从 `releases/latest` 下载 → `install.sh` 安装 → 真跑一遍，**24 项全过**；并断言装出来的是**原版**（而非 SkillHub 净化版）。
- **宿主实机**：Codex 项目级发现与安装路径执行通过；WorkBuddy 5.5.6 与 LobsterAI 2026.5.22 均已执行综合样例并完成文件级回归。
- **仍未完成**：各宿主的**完整隐式路由验收**（每 skill 20 正 + 20 反，共 120 条/宿主）。详见 [测试摘要](evals/test-report-2026-09-15.md) 与 [跨 Agent 验收矩阵](evals/cross-agent-matrix.md)。

## 目录

```text
ai-audit-skills/
├── skills-v2/              四个独立 skill
├── docs/                   公共数据协议与方法边界
├── adapters/               各 Agent 的安装说明
├── install.sh              一键安装（bash：macOS / Linux / Git Bash / WSL）
├── install.ps1             一键安装（Windows PowerShell）
├── dist-v2/                按 skill 分开的 ZIP 快照
└── evals/                  pack 级结构、黑盒评分、触发和跨 Agent 评估
```

当前版本：见 [VERSIONS.json](VERSIONS.json)（各 skill 独立版本号）。

## License

Scope is explicit, no ambiguity:

- **Each skill** (`skills-v2/<skill>/`) is licensed **MIT-0** (MIT No Attribution) — see each skill's `manifest.json` and its `license` field on SkillHub. **No attribution required** when you use a skill.
- **Everything else** (this README, `evals/`, `evolution/`, `scripts/`, `docs/`, …) is under the **Apache License 2.0** — see the root [`LICENSE`](LICENSE).

In short: **skills you install from a marketplace or release are MIT-0; the repository's own scaffolding is Apache-2.0.**
