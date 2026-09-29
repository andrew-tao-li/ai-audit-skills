# 豆包（豆包工作）安装与验证

## 当前状态

- **已在「豆包工作」的工作任务模式下确认可安装**（真实审计师实测：安装、运行均正常）。
- ⚠️ **只有 Windows / macOS 桌面客户端有 Skill 功能**；网页版、手机 App 没有。
- 需要切到客户端的**「工作任务」模式**（不是普通对话模式）。

## 技能放哪里

豆包是 Electron 应用，用户自装技能放在工作区的 **`.user_skills/`** 下（豆包官方帮助中心亦称 `user_skills`）：

```
Windows: %LOCALAPPDATA%\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\<skill-name>\
macOS:   ~/Library/Application Support/Doubao/User Data/Default/.doubao/agent_mode/workspace/.user_skills/<skill-name>/
```

**两种装法**：

```bash
# ① 用安装脚本（自动探测到豆包时就直接装对地方；也可显式指定）
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | HOST=doubao bash

# ② 手动：把 skills-v2/<skill-name>/ 整个目录复制到上面的 .user_skills/ 下
```

> 安装脚本的探测顺序是 OpenCode → WorkBuddy → LobsterAI → **豆包**。
> **豆包排在最后**，所以如果你机器上同时有别的 Agent 目录，脚本会按原优先级装到那边，并打印提示；
> 想明确装到豆包就用 `HOST=doubao`。

## 装完怎么用

1. 打开豆包客户端 → 切到**「工作任务」**模式。
2. 在输入框用 `/`（或点「更多技能」）能看到已安装的技能；也可以直接用自然语言触发。
3. 第一次先跑包内 `examples/input` 的合成样例，确认产物与边界措辞后再上真实数据。

## 已知注意

- **云端沙箱与本地环境隔离**：用「云电脑」跑任务时，安装的技能不互通。
  官方说明里，**通过技能商店上传的技能以及 `user_skills` 目录不受影响**——所以放在 `.user_skills/` 是稳的。
- 路径可能随豆包版本调整。若上述目录不存在，先确认客户端已装、且进入过「工作任务」模式；仍找不到就用
  `PREFIX=<你的技能目录>` 显式指定。

## 证据

- 豆包官方帮助中心：[使用工作任务模式](https://www.doubao.com/work/docs/zh-cn/articles/047323472965-work-task-mode)（其中明确提到 `user_skills` 目录）
- 路径来源：社区同步仓库对本地 `agent_mode/workspace/.skills` 的每日同步记录（据此推出 `workspace` 目录结构）
- 本项目的真实审计师实机报告（2026-09-29）：安装到 `.user_skills/` 后可正常运行
