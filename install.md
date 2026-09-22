# AI Audit Skills — 安装

适用版本：**最新版（动态拉取）**

三个独立、可离线运行的审计 Agent Skill（canonical v0.2.0）：

| Skill 名 | 用途 |
|---|---|
| `expense-audit-v2` | 费用、报销与发票异常全量扫描 |
| `procurement-fraud-v2` | 采购舞弊红旗、供应商关系、价格、拆单、流程和投标相似度筛查 |
| `investigation-assistant-v2` | 把举报、邮件、消息和日志整理为可追溯调查工作空间 |

## 一键安装（推荐）

```bash
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
```

**特点**：

- 永远拉**最新版**（脚本内部去问 GitHub `releases/latest`，即使 GitHub API 被速率限制也会 fallback 到 `/releases/latest` 重定向）。
- 不需要记版本号，这段命令**永远有效**——下次发 v0.3 时不用改任何文字。
- 可选环境变量：`HOST=opencode|workbuddy|lobsterai`（默认 `opencode`）、`PREFIX=...`、`VERSION=v0.X.Y`（锁定）。
- 可选位置参数选子集：`... | bash -s -- expense-audit-v2 investigation-assistant-v2`。

## 各 Agent 的安装位置（脚本默认按 `HOST` 选择）

| Agent | 默认安装目录 |
|---|---|
| `opencode`（默认） | `~/.config/opencode/skills` |
| `workbuddy` | `~/.workbuddy/skills` |
| `lobsterai` | `~/.lobsterai/skills` |

例如装到 WorkBuddy：

```bash
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh \
  | HOST=workbuddy bash
```

## 卸载

```bash
rm -rf ~/.config/opencode/skills/{expense-audit-v2,procurement-fraud-v2,investigation-assistant-v2}
# 或对 WorkBuddy：rm -rf ~/.workbuddy/skills/<skill-name>
```

## 验证（手动跑一次 example）

```bash
python3 ~/.config/opencode/skills/expense-audit-v2/scripts/run_expense_audit.py \
    --input  ~/.config/opencode/skills/expense-audit-v2/examples/input/expenses.csv \
    --policy ~/.config/opencode/skills/expense-audit-v2/examples/input/policy.json \
    --output /tmp/expense-audit-demo
ls /tmp/expense-audit-demo/findings.csv
```

## ZIP 直链（不走 `install.sh`，手动下载检查用）

- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/expense-audit-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/procurement-fraud-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/investigation-assistant-v2.zip>

最新版永远在 <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest>。

## 源码 & 自定义

- 三个 skill 的源码：`skills-v2/<skill-name>/`
- 重新打包 release zip：跑 `./scripts/build-dist.sh`
- 黑盒黄金测试：`python3 evals/blackbox/score_blackbox.py --version v0.2.0-baseline`
- 端到端校验：`python3 evals/validate_pack.py --run-tests`
