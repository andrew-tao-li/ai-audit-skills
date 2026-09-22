# AI Audit Skills v0.2.0 — 一键安装

适用版本：**v0.2.0**  
GitHub Release：<https://github.com/andrew-tao-li/ai-audit-skills/releases/tag/v0.2.0>

本仓库提供 3 个独立、可离线运行的审计 Agent Skill（canonical v0.2.0）：

| Skill 名 | 用途 |
|---|---|
| `expense-audit-v2` | 费用、报销与发票异常全量扫描 |
| `procurement-fraud-v2` | 采购舞弊红旗、供应商关系、价格、拆单、流程和投标相似度筛查 |
| `investigation-assistant-v2` | 把举报、邮件、消息和日志整理为可追溯调查工作空间 |

ZIP 直链：
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/expense-audit-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/procurement-fraud-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/investigation-assistant-v2.zip>

## 一键安装（按 Agent 选）

### OpenCode
```bash
mkdir -p ~/.config/opencode/skills
cd ~/.config/opencode/skills
for s in expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2; do
    curl -sLO "https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/${s}.zip"
    unzip -oq "${s}.zip" -d "${s}"
    rm -f "${s}.zip"
done
```

### WorkBuddy
```bash
mkdir -p ~/.workbuddy/skills
cd ~/.workbuddy/skills
for s in expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2; do
    curl -sLO "https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/${s}.zip"
    unzip -oq "${s}.zip" -d "${s}"
    rm -f "${s}.zip"
done
```

### LobsterAI
```bash
mkdir -p ~/.lobsterai/skills
cd ~/.lobsterai/skills
for s in expense-audit-v2 procurement-fraud-v2 investigation-assistant-v2; do
    curl -sLO "https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.2.0/${s}.zip"
    unzip -oq "${s}.zip" -d "${s}"
    rm -f "${s}.zip"
done
```

### Codex / Pi / 其他 SKILL.md 宿主
把这 3 个 zip 解压到对应宿主的位置（详见 `adapters/`）。

## 只装其中一个

把上面 `for s in ...` 循环中的 3 个 skill 名换成你想装的那个就行。

## 验证（任选）

```bash
python3 ~/.config/opencode/skills/expense-audit-v2/scripts/run_expense_audit.py \
    --input ~/.config/opencode/skills/expense-audit-v2/examples/input/expenses.csv \
    --policy ~/.config/opencode/skills/expense-audit-v2/examples/input/policy.json \
    --output /tmp/expense-audit-demo
ls /tmp/expense-audit-demo/findings.csv
```

## 卸载
直接 `rm -rf ~/.config/opencode/skills/<skill-name>`（或 WorkBuddy/LobsterAI 对应目录）。

## 关于 SkillHub 用户

如果你从 SkillHub 等聚合站来到这里的，本仓库就是这个 skill 的唯一源；release 上的 zip 与本仓库的 `skills-v2/` 100% 一致（通过 `scripts/build-dist.sh` 重新打包）。
