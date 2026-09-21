# Pi 安装与验证

可将 skill 目录复制到：

- 全局：`~/.pi/agent/skills/` 或 `~/.agents/skills/`
- 项目：`.pi/skills/` 或 `.agents/skills/`

也可以启动时使用 `--skill <path>`。显式调用格式为 `/skill:expense-audit` 等。Pi 会递归发现包含 `SKILL.md` 的目录，因此可以直接把三个 canonical skill 放入同一个 skills 根目录。

当前官方说明：[Pi Skills](https://pi.dev/docs/latest/skills)。
