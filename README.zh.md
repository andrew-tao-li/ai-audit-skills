# AI 审计技能包（中文版）

> 四个可独立安装、完全离线运行的 AI 审计 skill。面向 WorkBuddy / OpenCode / Claude Code / Cursor / OpenClaw 等智能体平台。

[English README](README.md) | 国内市场优先发布到 **SkillHub（skillhub.cn）** + **ClawHub（OpenClaw 生态）**。

---

## 简介

四个独立 skill，针对国内审计师/合规/财务/采购/HR 的常见场景：

| Skill | 版本 | 用途 |
|---|---|---|
| **expense-audit-v2** | 0.2.2 | 费用/差旅台账异常扫描：重复、超限、拆单、自审自批、跨人复用、日期倒挂等 |
| **procurement-fraud-v2** | 0.2.1 | 采购舞弊红旗筛查：共享账号、员工-供应商关联、价格离群、流程倒置、投标相似度等 |
| **investigation-assistant-v2** | 0.2.1 | 调查材料整理：证据哈希、时间线、关系图、证据矩阵、反证、假设登记、访谈计划 |
| **cn-entity-relation-check** | 0.1.1 | 公开工商关联排查：公司-公司、公司-人、人-人三态判定（关联/不关联/待核查） |

四个 skill 都已通过 F1 100% 的黑盒测试（expense 25 个、procurement 14 个、investigation 3 个黄金测试集，cn-entity 16 场景行级盲测 16/16 通过）。

## ⚠ 业务定位：辅助分析，不替代专业判断

四个 skill 都属于**辅助分析工具**，**不替代专业审计/合规/法律判断**。它们：

- **不连接银行流水**、征信系统、ERP 等外部数据源
- **不接收**身份证号、银行账号、客户底稿、未授权资料等敏感信息
- 只在**数据匹配层面**做异常检测（重复、阈值、流程倒置等）
- **不识别"业务实质"**——一份合规的客情费发票在数据上无法判断是否真的宴请了客户

**最终结论必须由有资质的审计师/合规官/调查员做出。**

详见 `skills-v2/expense-audit-v2/references/business-substance.md`。

## 适用对象

- **国内审计师 / 合规 / 财务 / 采购 / HR** 专业人员
- 智能体平台用户（WorkBuddy、有道龙虾、OpenCode、Claude Code、Cursor、OpenClaw 等）
- 想要一个**纯离线、零外传、零订阅**的本地 AI 审计工具的人
- 接受"**先在公众号 / 知乎 / 微信群** 看到用例，再来下载安装"的中国用户

## 一键安装

向智能体说：

> "请根据 https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.md 安装费用审计 / 采购舞弊 / 调查助手 / 关联排查。"

或者直接用命令：

```bash
# 单装（按需替换 skill 名）
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash -s -- expense-audit-v2

# 全装
curl -sL https://raw.githubusercontent.com/andrew-tao-li/ai-audit-skills/main/install.sh | bash
```

> **WorkBuddy 用户推荐路径**：智能体管理 → 通过 URL 导入 → `https://github.com/andrew-tao-li/ai-audit-skills`
> **OpenClaw / Lobster / 有道龙虾用户**：`clawhub install expense-audit-v2`（已经发布到 ClawHub）
> **国内 SkillHub**：发布到 `https://skillhub.cn`（"专为中国用户优化的 AI Skills 社区"）

## 快速上手

```bash
# 拿官方样例试一下
cd your-project
PY="C:/Users/yourname/.workbuddy/binaries/python/versions/3.13.12/python.exe"  # WorkBuddy 自带 Python
SKILL="C:/Users/yourname/.workbuddy/skills/expense-audit-v2"

"$PY" "$SKILL/scripts/run_expense_audit.py" \
    --input  "$SKILL/examples/input/expenses.csv" \
    --policy "$SKILL/examples/input/policy.json" \
    --output ./output
```

输出 8 个文件：

```
output/
├── summary.md              # 给人看的结论（必读）
├── findings.csv / .jsonl    # finding 明细 + 证据
├── run_manifest.json        # 含本次运行的全部参数 + 哈希
├── data_quality.md         # 数据体检报告
├── clean_expenses.csv / bad_rows.csv
└── evidence.jsonl
```

⚠ 输出目录必须为**全新空目录**（防止覆盖历史审计）。

## 四个 skill 的简单对比

| 场景 | 用哪个 | 输入 | 输出 |
|---|---|---|---|
| 差旅/费用异常扫描 | **expense-audit-v2** | 费用台账 CSV/XLSX + policy.json | findings + summary |
| 采购红旗筛查 | **procurement-fraud-v2** | 供应商/订单/付款/投标目录 | findings + 关系图 + 移交包 |
| 调查材料整理 | **investigation-assistant-v2** | 邮件/聊天/日志 + scope.json | 时间线 + 证据矩阵 + 备忘录 |
| 工商关联排查 | **cn-entity-relation-check** | 两个主体名 + 证据 JSON | 三态判定 + 路径 |

## 反馈与改进

每个 skill 都内置匿名反馈通道（仅发**非敏感统计**——findings 数、类型、风险分布、耗时；**不含**员工、供应商、金额）。

向智能体说「**做匿名反馈**」（rating 满意/一般/不满意）即可触发。反馈直达作者微信公众号后台。

## 项目结构

```
ai-audit-skills/
├── skills-v2/                  四个独立 skill
│   ├── expense-audit-v2/
│   ├── procurement-fraud-v2/
│   ├── investigation-assistant-v2/
│   └── cn-entity-relation-check/
├── docs/                       架构、方法论、安全模型
├── evals/                      黑盒黄金测试 + F1 评分
├── evolution/                  Auto-Research 框架 + 路线图
├── dist-v2/                    每个 skill 的发布 zip
├── install.sh / install.md      一键安装脚本 + 文档
├── README.md / README.zh.md    本文件
└── VERSIONS.json               技能版本清单
```

## 安全模型

- **完全离线**：所有 skill 主脚本都不联网、无 subprocess、无危险操作。
- **零凭证泄露**：不内置任何 API Key（BYOK）。
- **输出可审计**：每个 finding 都有 SHA-256 + 行号追溯。
- **人工复核优先**：脚本仅供**优先级排序**，结论由审计师做出。

`validate_pack.py` 强制检查所有 script 不得 `import urllib/requests/socket` 等网络模块。

## 路线图

| 阶段 | 状态 | 说明 |
|---|---|---|
| L0 基线 | ✅ | 黑盒测试 + F1 评分 |
| L1 通知 | ✅ | Mac mini 每日自动跑 + 企业微信通知 |
| L2 半自动 | ✅ | 工具都写好，审批流待接 |
| L3 真实审计师 | 🔄 | 启动中（skillhub.cn + ClawHub 上架） |
| L4 跨 skill 协同 | ⏸ | 长期 |

详见 `evolution/ROADMAP.md`。

## 国内发布 / 触达渠道

- **SkillHub（skillhub.cn）**：中国版 "Top 50 精选"，腾讯云 CDN + 百度 SEO 优化。**已上架准备中**（需先完成实名认证）。
- **ClawHub（OpenClaw 生态）**：WorkBuddy / 有道龙虾用户一键装。**发布脚本就绪**。
- **微信公众号**：「美会侠」（美丽的美、会计的会、侠客的侠）——国内审计师日常工作案例 + 工具应用。
- **知识星球**：「涛哥」（也叫「安德鲁」）——深度交流与真实案例。
- **知乎 / 掘金**：技术分享。

## 参与贡献

这是一个开源项目，欢迎：

- 报告 bug / 提出改进：在 [GitHub Issues](https://github.com/andrew-tao-li/ai-audit-skills/issues) 提交
- 真实审计师实测并反馈：私信作者（联系方式见 [公众号](https://github.com/andrew-tao-li/ai-audit-skills#)）
- 提交真实审计场景（脱敏后）作为"真实审计师盲测数据集"
- 翻译文档 / 改进 SKILL.md 措辞（让真实审计师更易读）

## 致谢

- 两位给出真实反馈的测试者（@admin、@chenhailong）——他们的功能测试与安全审计暴露了真实问题，让项目从"作者自测"走向"真实可用"。
- OpenClaw / ClawHub / SkillHub 平台的开源生态。
- 所有贡献者。

## 许可证

- 每个 skill 单独发布为 **MIT-0**（manifest 注明）。
- 仓库根 LICENSE：**Apache 2.0**（待统一 — 详见 ROADMAP ClawHub 决策项）。

---

**最后更新**：最新版见 <https://github.com/andrew-tao-li/ai-audit-skills/releases/latest>（当前 pack `v0.3.2`，各 skill 版本见 `VERSIONS.json`）。
**作者**：andrew-tao-li（@andrew-tao-li）
**项目主页**：https://github.com/andrew-tao-li/ai-audit-skills
**公众号**：「美会侠」（美丽的美、会计的会、侠客的侠）
**知识星球**：「涛哥」（也叫「安德鲁」）

> 业务实质性提醒：本工具为**辅助分析**，不替代专业审计/合规/法律判断。
> 详见 `skills-v2/expense-audit-v2/references/business-substance.md`。
