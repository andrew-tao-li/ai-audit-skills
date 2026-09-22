# OpenClaw 安装与验证

推荐每个 skill 作为独立目录安装：

```bash
openclaw skills install ./skills-v2/expense-audit-v2 --as expense-audit-v2
openclaw skills install ./skills-v2/procurement-fraud-v2 --as procurement-fraud-v2
openclaw skills install ./skills-v2/investigation-assistant-v2 --as investigation-assistant-v2
```

也可放在 `<workspace>/skills/` 或 `<workspace>/.agents/skills/`；工作区 `skills/` 的优先级更高。Canonical skill 没有 OpenClaw 私有 gating，因此不需要适配副本。

安装前审查 `SKILL.md` 和脚本；运行合成 fixture 后，再接触真实企业数据。

以上路径和本地安装命令于 2026-09-15 按官方说明核对：[OpenClaw Skills](https://docs.openclaw.ai/tools/skills)。
