# expense-audit v0.1.1

输入 CSV/XLSX 费用台账，输出数据质量、重复、近似重复、制度超标、疑似拆单、周末弱信号和稳健统计离群线索。脚本不联网、不调用大模型、不覆盖原文件。

最小运行命令和输出说明见 `SKILL.md`。`examples/input` 是合成数据；`examples/expected/expectations.json` 说明预期命中和反例边界。
