# AI Audit Skills — Install Manifest

> **GitHub 是唯一主安装路径。** 一行命令从 `raw.githubusercontent.com` 拉脚本 → 脚本去 GitHub releases 拿最新 zip → 解压到当前 Agent 的 skills 目录。**与是否发布到任何 marketplace（ClawHub / SkillHub）完全无关。**
>
> Agent 可读区。如果你（智能体）被用户要求装 andrew-tao-li 提供的审计 skill：
> 1. 找下表的「中文/英文友好名」，得到对应的 `skill-id`。
> 2. 跑下面「Install 命令」对应那行；**Windows 且机器上没有 bash 的，改用 `install.ps1`**（见「Windows 用户」一节）。
>
> 整个文件就是一个「统一安装入口」，URL 永远指向 `main` 分支、`install.sh` 内部自动取 GitHub 最新 tag。本文件是 mirror，权威源在仓库。

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
- 自动检测 Agent 类型（OpenCode / WorkBuddy / LobsterAI / 豆包 / Claude Code / Cursor / Codex 等），装到对应 `skills/` 目录
- 装完报告装到哪、装了哪些
- 打错字会立刻报错，不会静默失败

### Windows 用户：没有 bash 也能装（两条路，任选其一）

> Windows 自带的是 PowerShell；`install.sh` 是 bash 脚本，需要 Git Bash / WSL。**没有 bash 时走下面两条。**

**路 1（推荐）：PowerShell 安装脚本**（与 `install.sh` 等价：自动探测 → 下载最新版 → 解压）

```powershell
$f="$env:TEMP\ai-audit-install.ps1"; iwr -UseBasicParsing https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.ps1 -OutFile $f; powershell -ExecutionPolicy Bypass -File $f
```

只装某一个就在结尾加 `-Skills expense-audit-v2`；不确定装到哪，先跑 `-DetectOnly` 看解析出的目录。

**路 2（零命令行）：浏览器下载 + 解压**（最不吓人，不需要放开任何命令执行）

1. 打开 <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest>
2. 下载需要的 `<skill>.zip`
3. 右键「全部解压缩」
4. 把解出来的整个文件夹，放进你的 Agent 技能目录（见文末表格，或 `install.ps1 -DetectOnly` 的输出）

### 如果宿主提示「危险指令」怎么办

安装技能本质上就两步：**从 GitHub 下载一个 zip、解压到技能目录**。宿主之所以提示，通常是因为
「下载 + 解压/执行」这个动作撞上了它的安全策略。**请先看命令内容再决定**：

- 我们的官方命令只会访问 `github.com` / `raw.githubusercontent.com` / `api.github.com`，只会写到你自己的技能目录；
- 不放心就走**路 2**（浏览器下载 + 手动解压），**完全不需要放开命令行**；
- 也不建议让宿主 Agent「自己想办法」装（它可能会逐个文件去抓，版本和完整性都不受控）——用上面这两条官方路径。

---

## 各个智能体平台怎么装（**全部走 GitHub，没有 marketplace 依赖**）

下面的每条都**只**用 GitHub 上的内容，不依赖任何 marketplace 是否上架。

### 优先用平台原生"通过 URL 导入"（WorkBuddy 沙箱里 curl|bash 会反复弹"是否在沙箱执行"的高风险确认）

**WorkBuddy（推荐，最稳）**：技能管理 → "通过 URL 导入" → 填入 GitHub 仓库地址：
```
https://github.com/andrew-tao-li/ai-audit-skills
```
（或某个 skill 子目录，如 `https://github.com/andrew-tao-li/ai-audit-skills/tree/main/skills-v2/expense-audit-v2`）

**LobsterAI / 有道龙虾 / OpenClaw 体系**：与 WorkBuddy 相同，技能管理 → "通过 URL 导入" → 填入上面的 GitHub 仓库地址。

**OpenCode / Claude Code / Cursor / Codex CLI**：用通用 `npx @skill-hub/cli install <url>`（一个客户端装到 9+ Agent 平台）：
```
npx @skill-hub/cli install https://github.com/andrew-tao-li/ai-audit-skills/tree/main/skills-v2/expense-audit-v2 --agent opencode
```
支持的 `--agent`：claude / cursor / opencode / windsurf / cline / roo / codex / gemini / copilot 等。**这条命令直接拉 GitHub 仓库内容，不依赖 SkillHub 平台是否索引。**

### 兜底：直接 `curl | bash`（任何有 shell 的环境）

如果你的 Agent 没有 "URL 导入" 入口（纯 CLI 场景），用上面那行 `curl -sL .../install.sh | bash` 命令。脚本会：
- 探测 Agent 类型
- 去 GitHub releases 拿最新 zip
- 解压到正确的 skills 目录

完全自包含，**不调用任何 marketplace API**。

### 自定义路径

```
HOST=opencode bash           # 显式指定 Agent
PREFIX=~/.my-custom-path bash  # 显式指定安装目录
```

---

## 已发布用户的快捷方式（可选，与主安装无关）

> 这一节**仅当你已经把这个 skill 发布到 ClawHub / SkillHub / SkillPay 等 marketplace 时才需要看**。如果还没发，跳过。

### 通过 marketplace 一键装

- **SkillHub.cn（中国版 · ✅ 已上架）**：见下方「SkillHub.cn 安装」
- **ClawHub（国际 / OpenClaw 生态）**：`clawhub install <slug>`（⬜ 尚未上架）
- **SkillHub.club（国际版）**：`npx @skill-hub/cli install <slug> --agent <agent>`（⬜ 尚未上架，**与 skillhub.cn 是两个平台**）
- 三者都是**辅助选项**——你没登录任何平台也能完整使用这些 skill（全部从 GitHub 装）。

### SkillHub.cn 安装（我们的 4 个技能已上架）

命名空间：**`@indiv-ai-audit`**。官方 CLI：

```bash
# 通用形式（--dir 必须指向当前 Agent 的 skills 目录，否则会装到 ./skills/ 不被识别）
skillhub install <slug> --namespace indiv-ai-audit --dir <skills 目录>

# 我们的四个（skills 目录按你的 Agent 换，例如 ~/.claude/skills）
skillhub install andrew-tao-li-expense-audit            --namespace indiv-ai-audit --dir ~/.claude/skills
skillhub install andrew-tao-li-procurement-fraud        --namespace indiv-ai-audit --dir ~/.claude/skills
skillhub install andrew-tao-li-investigation-assistant  --namespace indiv-ai-audit --dir ~/.claude/skills
skillhub install andrew-tao-li-cn-entity-relation       --namespace indiv-ai-audit --dir ~/.claude/skills
```

**或者给 AI 一句话**（官方安装指引：<https://skillhub.cn/install/skillhub.md>）：

> 根据 https://skillhub.cn/install/skillhub.md 安装 `andrew-tao-li-expense-audit`（namespace: `indiv-ai-audit`）

技能主页（可直接浏览/复制 prompt）：<https://skillhub.cn/skills/andrew-tao-li-expense-audit> ·
<https://skillhub.cn/skills/andrew-tao-li-procurement-fraud> ·
<https://skillhub.cn/skills/andrew-tao-li-investigation-assistant> ·
<https://skillhub.cn/skills/andrew-tao-li-cn-entity-relation>

### 发布到 marketplace 的步骤（作者用）

- **SkillHub.cn**：`skillhub login --key skh_xxx --host https://api.skillhub.cn` →
  `python3 scripts/build-skillhub.py`（生成净化版）→ `python3 scripts/publish-skillhub.py`（**带分类**，官方 CLI 不带）。
  发布有**限频**，连发多个需间隔约 70s（脚本已内置）。
- **ClawHub**：`clawhub login` → `scripts/publish-clawhub.sh`（用净化版 + ClawHub 自己的分类/主题）。

---

## 人类补充说明（agent 可忽略）

### 四个 Agent 的默认安装位置

| Agent | 默认安装目录（脚本自动检测） |
|---|---|
| OpenCode | `~/.config/opencode/skills` |
| WorkBuddy | `~/.workbuddy/skills` |
| LobsterAI | `~/Library/Application Support/LobsterAI/SKILLs`（macOS；另有 `~/.lobsterai/skills` 兜底） |
| **豆包工作**（DoubaoWork） | `<数据目录>/DoubaoWork/User Data/Default/.doubaowork/agent_mode/workspace/.user_skills`（Windows `%LOCALAPPDATA%` / macOS `Application Support`） |
| **豆包**（个人版） | `<数据目录>/Doubao/User Data/Default/.doubao/agent_mode/workspace/.user_skills` |
| Claude Code | `~/.claude/skills` |
| Cursor | `~/.cursor/skills` |
| Codex | `~/.codex/skills`（另有 `~/.agents/skills` 兜底） |
| Gemini CLI | `~/.gemini/skills` |

> ⚠️ **「豆包工作」和「豆包」是两个产品、两套目录**（`DoubaoWork`/`.doubaowork` 与 `Doubao`/`.doubao`）。
> 2026-10 的真实审计师用的是「豆包工作」——早期脚本只写了个人版路径，导致探测失败，**现已两套都认**。
>
> 探测顺序为 OpenCode → WorkBuddy → LobsterAI → **豆包** → Claude / Cursor / Codex / Gemini。
> 新加的都在**末尾**，因此不会改变任何既有平台的安装结果；机器上同时存在多个 Agent 目录时，
> 脚本会打印提示，并告诉你如何用 `HOST=` / `-Agent` 指定另一个。
>
> 不确定会装到哪？先自检（不联网、不安装，只打印解析结果）：
> ```bash
> bash install.sh --detect-only                 # macOS / Git Bash / WSL
> ```
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\install.ps1 -DetectOnly   # Windows
> ```

如果自动检测不对，可以显式指定（环境变量 / 参数二选一）：
```bash
curl ... | HOST=workbuddy bash
curl ... | HOST=doubao bash
curl ... | PREFIX=~/.my-custom-path bash
```
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Agent doubao
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Prefix C:\my\skills
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Skills expense-audit-v2
```

### 网络受限时（github.com 连不上、但 api / raw 能通）

部分企业网/国内网络会出现 `github.com` 超时而 `api.github.com`、`raw.githubusercontent.com` 可通。
`install.sh` / `install.ps1` 已内置**网络降级**：直连失败会自动改用 GitHub API 资产接口下载。
若仍不通，可指定镜像前缀（镜像需按 `<前缀>/<版本>/<skill>.zip` 提供文件）：

```bash
MIRROR=https://my.mirror/ bash install.sh expense-audit-v2
```
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Mirror https://my.mirror/
```

### 锁定版本

默认装最新。如果想钉死某个版本（把 `<版本号>` 换成你要的版本号）：
```
VERSION=<版本号> curl ... | bash -s -- expense-audit-v2
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

| # | 问题 | 现象 | 规避方法 |
|---|---|---|---|
| 1 | 裸 `python3` 是商店 stub | exit 49 / 打不开 | 用真实 Python 的绝对路径（如 WorkBuddy 托管 Python） |
| 2 | Git Bash 路径传参错乱 | `/c/Users/...` 被拼成 `C:\c\Users\...`（双 c） | 给脚本传参一律用 `C:/Users/...` 风格或相对路径 |
| 3 | 沙箱拒绝写 `/tmp` 子目录 | `curl(23)`「系统找不到指定的文件」 | install.sh 已改为下载到目标目录（见下）；手动装则直接解压到 skills 目录 |
| 4 | HEAD 请求超时 | `curl -I` 对 GitHub 返回 000 | 用 GET；或 API JSON（带 `User-Agent`） |
| 5 | 沙箱拒绝删除部分路径 | 删除被 Blocked | 测试产物留在原位即可 |
| 6 | 机器上没有 bash | `install.sh` 无法执行（`.sh` 需要 Git Bash / WSL） | 用 `install.ps1`，或走「浏览器下载 + 解压」 |
| 7 | `github.com` 主站不通 | 直连超时（但 `api.github.com` / `raw.githubusercontent.com` 通） | 脚本已内置降级（自动改用 API 资产接口）；必要时设 `MIRROR=` |
| 8 | 豆包目录探测不到 | 早期脚本只认「豆包」，实际是「豆包工作」 | 已修复（两套都认）；用 `-DetectOnly` 确认 |

> install.sh 已针对这些做过加固：版本探测改用 API+`User-Agent`+`sed`（不依赖 python3），下载直接落目标目录（不用 mktemp/`/tmp`），
> 并在 `github.com` 不可达时降级到 GitHub API 资产接口。**Windows 无 bash 时请改用 `install.ps1`。**

### ZIP 直链（不走 install.sh，手动下载/检查用）

> 用 `releases/latest/download/` 别名，**永远指向最新版**，不会过时。

- <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest/download/expense-audit-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest/download/procurement-fraud-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest/download/investigation-assistant-v2.zip>
- <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest/download/cn-entity-relation-check.zip>

所有版本列表见 <https://github.com/andrew-tao-li/ai-audit-skills/releases>。

### 源码 & 自定义
- 四个 skill 的源码：`skills-v2/<skill-name>/`
- 重新打包 release zip：跑 `./scripts/build-dist.sh`
- 黑盒黄金测试：`python3 evals/blackbox/score_blackbox.py --version local-check`
- 端到端校验：`python3 evals/validate_pack.py --run-tests`
