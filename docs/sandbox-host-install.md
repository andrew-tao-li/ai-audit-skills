# 沙箱 / 云宿主安装指南（Copilot · ChatGPT/Codex · 云 IDE 等）

> 适用场景：智能体跑在**云端容器**里，而不是你自己的电脑上。
> 典型症状：**装不上**，宿主报 `403 / Request blocked by sandbox policy`，或说"无法访问外部代码仓库"，并请你**上传 zip**。

---

## 一、先判断：你的宿主是不是"沙箱型"

| 类型 | 特征 | 技能目录（例子） |
|---|---|---|
| **沙箱 / 云宿主** | 智能体在**云端容器**里跑；出网受限 | `/home/oai/skills`（OpenAI / ChatGPT / Codex 系）· `/home/user/skills`（其它云沙箱） |
| **本机宿主**（不受此限） | 智能体在你本机 | `~/.claude/skills/`（Claude Code）· `~/.workbuddy/skills/`（WorkBuddy）· OpenCode · 本机 Copilot CLI |

**看路径就能认出来**：如果技能目录是一个 Linux 风格路径（`/home/...`），而你又没在用 Linux——那就是**云端沙箱**。

---

## 二、为什么会装不上（不是技能的问题，也不是宿主的问题）

| 症状 | 原因 |
|---|---|
| `curl \| bash` 那套装不上 | 沙箱**不允许出网执行** |
| 从 `github.com` / `raw.githubusercontent.com` 拉取返回 **403** | 沙箱的**出网白名单不含 GitHub** |
| 宿主说"我**不能真实地宣称**已完成安装" | 它拿不到文件 —— **这是它诚实的表现，值得肯定** |

> 本技能自身**完全离线**（纯标准库、运行时零联网）；"装不上"纯粹是**下载通道**被沙箱挡了。

---

## 三、怎么装（推荐路径：浏览器下载 → 上传给宿主）

### 第 1 步：在你的浏览器里下载（浏览器不受沙箱限制）

```
https://github.com/andrew-tao-li/ai-audit-skills/releases/latest/download/expense-audit-v2-sandbox.zip
```

> ⚠️ **务必用 `-sandbox.zip` 这一版。**
> 它的**内部是单个顶层文件夹** `expense-audit-v2/`——这是**平台上传**要求的形状。
> 普通版 `expense-audit-v2.zip` 是**扁平**的（文件直接躺在根目录），是给 `install.sh` 解压到指定目录用的；
> 拿普通版去平台上上传，平台会因"没有单一顶层目录"而**拒绝或把文件散落**到技能根目录。

其余四个技能的沙箱版（把技能名换掉即可）：

```
.../releases/latest/download/procurement-fraud-v2-sandbox.zip
.../releases/latest/download/investigation-assistant-v2-sandbox.zip
.../releases/latest/download/cn-entity-relation-check-sandbox.zip
.../releases/latest/download/audit-sql-builder-sandbox.zip
```

### 第 2 步：把 zip 上传给宿主，并这样说

> 请把这个 zip 解压到技能目录（例如 `/home/oai/skills/`），
> 确认 **`<技能目录>/expense-audit-v2/SKILL.md`** 存在，然后重新加载技能。

### 第 3 步：验证

- 目录里应有 `SKILL.md`、`scripts/`、`references/`、`requirements.txt`；
- 让它跑 `python3 scripts/run_expense_audit.py --check-env`，应看到 `network_required: false`。

---

## 四、如果手上只有普通版 zip，自己套一层目录即可

```bash
unzip -q expense-audit-v2.zip -d expense-audit-v2
zip -qrX expense-audit-v2-sandbox.zip expense-audit-v2   # 重新打包
```

（内容与官方 `-sandbox.zip` **逐字节一致**，只是外壳不同。）

---

## 五、⚠️ 两条重要提醒

1. **沙箱通常是临时的**
   `/home/oai/skills` 这类目录**可能每次新会话就重置**，技能得重装。
   → **长期使用，请装到本机宿主**（Claude Code / WorkBuddy / OpenCode / 本机 Copilot 等）。

2. **审计数据不要进云沙箱**
   本技能的设计前提是**数据不出本机**（离线运行、不上传、无外部服务）。
   把**真实费用台账**交给**云端沙箱**，等于把数据交给了第三方平台。
   → **处理真实数据，请装在本机。**

---

## 六、为什么我们不干脆只发一种包？

因为两种安装方式对 zip 形状的要求**恰好相反**：

| 安装方式 | 需要的形状 |
|---|---|
| `install.sh`：下载后解压到 `<技能名>/` | **扁平**（不能自带顶层目录，否则会套成两层） |
| 平台 / 沙箱上传（OpenAI 等） | **单个顶层文件夹** |

所以 release **同时提供两套**，内容**逐字节一致**，只是外壳不同：

- `<技能>.zip` —— 给 `install.sh` / 手动解压；
- `<技能>-sandbox.zip` —— 给平台上传 / 沙箱宿主。
