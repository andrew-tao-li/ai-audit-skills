# 豆包（豆包 / 豆包工作）安装与验证

## 当前状态

- **已在 Windows 的「豆包工作」客户端实机安装成功**（真实审计师，2026-10；安装后技能可正常加载运行）。
- ⚠️ **只有 Windows / macOS 桌面客户端有 Skill 功能**；网页版、手机 App 没有。
- 需要切到客户端的**「工作任务」模式**（不是普通对话模式）。

## ⚠️ 先分清：「豆包」和「豆包工作」是两个产品、两套目录

它们是**不同的应用**，数据目录名也不一样。安装脚本两套都探测，但你自己手动找的时候别找错：

| 产品 | 应用目录 | 用户数据目录（profile） |
|---|---|---|
| **豆包工作**（办公 / Agent 场景，审计师常用） | `DoubaoWork` | `.doubaowork` |
| 豆包（个人版） | `Doubao` | `.doubao` |

> 2026-10 的真实审计师环境是 **`DoubaoWork` / `.doubaowork`**。本项目早期只写了个人版路径，
> 导致在「豆包工作」上自动探测失败——**已修正**（`install.sh` / `install.ps1` 现在两套都认）。

## 技能放哪里

豆包是 Electron 应用，用户自装技能放在工作区的 **`.user_skills/`** 下（豆包官方帮助中心亦称 `user_skills`）：

```
Windows 豆包工作: %LOCALAPPDATA%\DoubaoWork\User Data\Default\.doubaowork\agent_mode\workspace\.user_skills\<skill-name>\
Windows 豆包:     %LOCALAPPDATA%\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\<skill-name>\
macOS   豆包工作: ~/Library/Application Support/DoubaoWork/User Data/Default/.doubaowork/agent_mode/workspace/.user_skills/<skill-name>/
macOS   豆包:     ~/Library/Application Support/Doubao/User Data/Default/.doubao/agent_mode/workspace/.user_skills/<skill-name>/
```

**先确认到底用哪个**（不联网、不安装，只打印解析结果）：

```bash
# macOS / Linux（Git Bash / WSL）
bash install.sh --detect-only
```
```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -DetectOnly
```

## 四种装法（按「省事程度」排序）

```bash
# ① Windows 推荐：原生 PowerShell 安装脚本（不需要 bash）
powershell -ExecutionPolicy Bypass -File .\install.ps1

# ② macOS / Git Bash / WSL：bash 安装脚本
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | HOST=doubao bash

# ③ 零命令行（最不吓人，适合不放心「远程脚本」的人）：
#    浏览器打开 https://github.com/andrew-tao-li/ai-audit-skills/releases/latest
#    下载需要的 <skill>.zip → 右键「全部解压缩」→ 把整个文件夹放进上面的 .user_skills\ 目录

# ④ 手动：把 skills-v2/<skill-name>/ 整个目录复制到上面的 .user_skills/ 下
```

> 安装脚本的探测顺序是 OpenCode → WorkBuddy → LobsterAI → **豆包** → Claude / Cursor / Codex / Gemini。
> **豆包排在最后**，所以如果你机器上同时有别的 Agent 目录，脚本会按原优先级装到那边，并打印提示；
> 想明确装到豆包就用 `HOST=doubao`（或 PowerShell 的 `-Agent doubao`）。

## 装完怎么用

1. 打开豆包客户端 → 切到**「工作任务」**模式。
2. 在输入框用 `/`（或点「更多技能」）能看到已安装的技能；也可以直接用自然语言触发。
3. 第一次先跑包内 `examples/input` 的合成样例，确认产物与边界措辞后再上真实数据。

## 已知注意

- **云端沙箱与本地环境隔离**：用「云电脑」跑任务时，安装的技能不互通。
  官方说明里，**通过技能商店上传的技能以及 `user_skills` 目录不受影响**——所以放在 `.user_skills/` 是稳的。
- **如果宿主 Agent 提示「危险指令」**：那通常是它在执行「下载 + 解压」。我们的官方包只做两件事——
  从 GitHub 下载 `releases` 里的 `<skill>.zip`、解压到 `.user_skills`。**先看命令内容再决定**；
  不放心就走上面的「装法 ③」（浏览器下载 + 解压），完全不需要放开命令执行。
- 路径可能随豆包版本调整。若上述目录不存在，先确认客户端已装、且进入过「工作任务」模式；仍找不到就用
  `PREFIX=<你的技能目录>`（PowerShell：`-Prefix <目录>`）显式指定。

## 证据

- 豆包官方帮助中心：[使用工作任务模式](https://www.doubao.com/work/docs/zh-cn/articles/047323472965-work-task-mode)（其中明确提到 `user_skills` 目录）
- 本项目真实审计师实机报告：
  - 2026-09：确认技能放到 `.user_skills/` 后可正常运行。
  - 2026-10：Windows「豆包工作」实机安装成功；据此修正了「豆包工作」的应用目录（`DoubaoWork`）与
    profile 目录（`.doubaowork`），并新增 Windows 原生 `install.ps1`。
