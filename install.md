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
| 关联排查 / 关联分析 | `cn-entity-relation-check` | 核查两个公司/自然人的中国公开工商关联，输出关联/不关联/待核查 |

> **默认行为（开关 = 单装）**：表里列全部 4 个，**只是为了让 agent 把中文友好名映射到 skill-id**。**不要**因为表里有 4 个就主动推荐用户顺便把其他几个也装了。用户问装哪一个，就只装哪一个。
>
> **全装开关（开关 = 装全部）**：**只有**用户明确说「全部 4 个」「全套」「full set」「all of them」「四个都装」等明显要全套的措辞时，才跑不带 `--skill-id` 的命令（即装全部 4 个）。其他情况默认走单装。

## Install 命令

**装单个**（把 `<skill-id>` 换成上表的 skill-id）：
```
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash -s -- <skill-id>
```

**装全部 4 个**（不带参数就是全部）：
```
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
```

脚本会自动：
- 去 GitHub 查「最新 tag」下载最新版（**不写死版本号，永远最新版**）
- 自动检测 Agent 类型（OpenCode / WorkBuddy / LobsterAI），装到对应 `skills/` 目录
- 装完报告装到哪、装了哪些
- 打错字会立刻报错，不会静默失败

---

## WorkBuddy / 有道龙虾 用户：优先用「通过 URL 导入」而非 curl

如果你的 Agent 是 **WorkBuddy** 或 **有道龙虾（LobsterAI）**，别用上面的 `curl | bash`（它会反复弹「是否在沙箱执行」的确认，因为 curl|bash = 下载并执行远程脚本，属于高风险操作）。改用平台原生导入，更顺、不弹窗：

- **WorkBuddy**：技能管理 → 「通过 URL 导入」/「GitHub 仓库导入」→ 填：
  ```
  https://github.com/andrew-tao-li/ai-audit-skills
  ```
  （或某个 skill 子目录，如 `https://github.com/andrew-tao-li/ai-audit-skills/tree/main/skills-v2/expense-audit-v2`）

- **有道龙虾（LobsterAI）**：Skill Store 里直接装，或命令行：
  ```
  clawhub install expense-audit-v2
  ```
  （LobsterAI 支持 GitHub 全量 skills 安装）

> `curl | bash` 只当**兜底**（给那些没有「URL 导入」入口的 Agent 用）。每个 skill 根目录还带了 `manifest.json`（id/name/version/description/author/type/triggers/tags/license），WorkBuddy / ClawHub 直接认这个格式。

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
VERSION=v0.3.1 curl ... | bash -s -- expense-audit-v2
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

### Windows / WorkBuddy 沙箱已知注意（实测踩坑）

以下问题与 skill 质量无关，是 **Windows + WorkBuddy 沙箱**的固有行为，遇到时按右边规避：

| 问题 | 现象 | 规避 |
|---|---|---|
| 裸 `python3` 是商店 stub | exit 49 / 打不开 | 用真实 Python 的绝对路径（如 WorkBuddy 托管 Python） |
| Git Bash 路径传参错乱 | `/c/Users/...` 被拼成 `C:\c\Users\...`（双 c） | 给脚本传参一律用 `C:/Users/...` 或相对路径 |
| 沙箱拒绝写 `/tmp` 子目录 | `curl(23)`「系统找不到指定的文件」 | install.sh 已改为下载到目标目录（见下）；手动装则直接解压到 skills 目录 |
| HEAD 请求超时 | `curl -I` 对 release URL 返回 000 | 用 GET；或 API JSON（带 `User-Agent`） |
| 沙箱拒绝删除部分路径 | 删除被 Blocked | 测试产物留在原位即可 |

> install.sh 已针对这些做过加固：版本探测改用 API+`User-Agent`+`sed`（不依赖 python3），下载直接落目标目录（不用 mktemp/`/tmp`）。

### ZIP 直链（不走 install.sh，手动下载/检查用）

- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.3.1/expense-audit-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.3.1/procurement-fraud-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.3.1/investigation-assistant-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/download/v0.3.1/cn-entity-relation-check.zip>

最新版永远在 <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest>。

### 源码 & 自定义
- 四个 skill 的源码：`skills-v2/<skill-name>/`
- 重新打包 release zip：跑 `./scripts/build-dist.sh`
- 黑盒黄金测试：`python3 evals/blackbox/score_blackbox.py --version v0.2.0-baseline`
- 端到端校验：`python3 evals/validate_pack.py --run-tests`
