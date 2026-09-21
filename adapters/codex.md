# Codex 安装与验证

Canonical skill 无需改 frontmatter。将三个 skill 目录复制到以下任一位置：

- 仓库级：`<repo>/.agents/skills/<skill-name>/`
- 用户级：`~/.agents/skills/<skill-name>/`
- 兼容旧/个人配置的路径也可按本机 Codex 设置处理。

Codex 会根据 `description` 隐式选择；也可用 `$expense-audit`、`$procurement-fraud`、`$investigation-assistant` 显式调用。`agents/openai.yaml` 仅增加界面名称和默认提示，不是运行依赖。

验证：先分别发送 `evals/trigger-prompts.jsonl` 中的正例和负例，再用对应 `examples/input` 做一次端到端运行。

当前官方说明：[Build skills](https://learn.chatgpt.com/docs/build-skills)。
