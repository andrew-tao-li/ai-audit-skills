# expense-audit v0.2.4

输入 CSV/XLSX 费用台账，输出数据质量、重复、近似重复、制度超标、疑似拆单、周末弱信号和稳健统计离群线索。脚本不联网、不调用大模型、不覆盖原文件。

最小运行命令和输出说明见 `SKILL.md`。`examples/input` 是合成数据；`examples/expected/expectations.json` 说明预期命中和反例边界。

---

## 版权与署名

本 skill 由 **Andrew Tao Li (andrew-tao-li)** 开发（源码与全部版本：https://github.com/andrew-tao-li/ai-audit-skills）。

许可证为 **MIT-0**（MIT No Attribution）：使用、修改、再分发**均无需署名**，条款见
同目录 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。

若用于商业产品、对外服务或再分发到第三方平台，欢迎注明出处 —— 这不是许可条件，
只是对作者的实际支持。

问题 / 建议：微信公众号「美会侠」（回复「费用审计」）· 邮箱 andrew.tao.li@foxmail.com
