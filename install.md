# AI Audit Skills — Install Manifest

> **Agent 可读区**。如果用户让你装 andrew-tao-li 提供的审计 skill：
> 1. 找下表的「中文/英文友好名」，得到对应的 `skill-id`。
> 2. 跑下面「Install 命令」对应那行。
>
> 整个文件就是一个「统一安装入口」，URL 永远指向 `main` 分支、`install.sh` 内部自动取 GitHub 最新 tag。
> 本文件是 mirror，权威源在仓库。

## Skills（友好名 → skill-id）

| 友好名（中文） | skill-id | 一句话 |
|---|---|---|
| 费用审计 / 报销审计 | `expense-audit-v2` | 费用、报销、发票异常全量扫描 |
| 采购舞弊 / 采购审计 | `procurement-fraud-v2` | 采购舞弊红旗、供应商关系、价格、拆单、流程、投标相似度筛查 |
| 调查助手 / 内部调查 | `investigation-assistant-v2` | 举报、邮件、消息和日志整理为可追溯调查工作空间 |

## Install 命令

**装单个**（把 `<skill-id>` 换成上表的 skill-id）：
```
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash -s -- <skill-id>
```

**装全部 3 个**（不带参数就是全部）：
```
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
```

脚本会自动：
- 去 GitHub 查「最新 tag」下载最新版（**不写死 v0.2.0，永远最新版**）
- 自动检测 Agent 类型（OpenCode / WorkBuddy / LobsterAI），装到对应 `skills/` 目录
- 装完报告装到哪、装了哪些
- 打错字会立刻报错，不会静默失败

---

## 人类补充说明（agent 可忽略）

### 三个 Agent 的安装位置

| Agent | 默认安装目录（脚本自动检测） |
|---|---|
| OpenCode | `~/.config/opencode/skills` |
| WorkBuddy | `~/.workbuddy/skills` |
| LobsterAI | `~/.lobsterai/skills` |

如果自动检测不对，可以显式指定（环境变量）：
```
curl ... | HOST=workbuddy bash
curl ... | PREFIX=~/.my-custom-path bash
```

### 锁定版本

默认装最新。如果想钉死某个版本：
```
VERSION=v0.2.0 curl ... | bash -s -- expense-audit-v2
```

### 验证（手动跑一次 example）

```bash
python3 ~/.config/opencode/skills/expense-audit-v2/scripts/run_expense_audit.py \
    --input  ~/.config/opencode/skills/expense-audit-v2/examples/input/expenses.csv \
    --policy ~/.config/opencode/skills/expense-audit-v2/examples/input/policy.json \
    --output /tmp/expense-audit-demo
ls /tmp/expense-audit-demo/findings.csv
```

### 卸载
```bash
rm -rf ~/.config/opencode/skills/{expense-audit-v2,procurement-fraud-v2,investigation-assistant-v2}
# 或单卸一个
rm -rf ~/.config/opencode/skills/expense-audit-v2
```

### ZIP 直链（不走 install.sh，手动下载/检查用）

- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/expense-audit-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/procurement-fraud-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/investigation-assistant-v2.zip>

最新版永远在 <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest>。

### 源码 & 自定义
- 三个 skill 的源码：`skills-v2/<skill-name>/`
- 重新打包 release zip：跑 `./scripts/build-dist.sh`
- 黑盒黄金测试：`python3 evals/blackbox/score_blackbox.py --version v0.2.0-baseline`
- 端到端校验：`python3 evals/validate_pack.py --run-tests`
