# Audit Skill Box — 架构文档

> **这份文档的目的**：让你（用户）隔几天回来时，看这一份文档就能刷新整个项目的记忆。
>
> 当 OpenCode 发邮件提醒时，配合这份文档，能在 5 分钟内想起"我们做的是什么、现在到哪、下一步该做什么"。

---

## 文档地图

| 文档 | 作用 | 在哪 |
|---|---|---|
| **本文件（ARCHITECTURE.md）** | 系统是什么 + 怎么跑 | `evolution/ARCHITECTURE.md` |
| **ROADMAP.md** | 系统要往哪走 | `evolution/ROADMAP.md` |
| **state.json** | 当前机器可读状态 | `evolution/state.json` |
| **AGENTS.md** | 协议和约束 | `AGENTS.md`（根目录） |
| **升级指南** | 怎么用新版本 | `dist-v2/升级指南.md` |

---

## 图 1：架构全景（最重要，先看这张）

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                      AUDIT SKILL BOX — 架构全景                            ║
║                                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

   ┌─────────────────────────────────────────────────────────────────┐
   │  你（用户）                                                       │
   │  ├─ 看企业微信通知                                                   │
   │  ├─ 审 proposals/*.md（LLM 提议）                                    │
   │  ├─ 决策 yes / no                                                   │
   │  └─ 任何地方通过浏览器（Tailscale）访问 OpenCode 网页改代码       │
   └─────────────────────┬───────────────────────────────────────────┘
                         │
             【企业微信】 │  【浏览器: http://<tailscale-ip>:4096】
                         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  🖥️  Mac mini（长期开机）                                          │
   │                                                                   │
   │   launchd 常驻服务（两个）：                                        │
   │     com.audit.skill.box  → 每天 9:00 跑 evolve.sh                 │
   │     com.opencode.web    → opencode serve（网页工作台，端口 4096）  │
   │       │                                                            │
   │       ▼                                                            │
   │   evolve.sh ← 循环引擎（4 步）                                    │
   │     Step 1: 跑测试（CPU only）                                    │
   │     Step 2: 评分 precision/recall/F1                             │
   │     Step 3: 写 state.json                                        │
   │     Step 4: 调 MiniMax（回退 DeepSeek），写 proposals/            │
   │                                                                   │
   └─────────────────────┬───────────────────────────────────────────┘
                         │
                     【HTTP API】
                         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  ☁️  LLM API（云端）                                               │
   │  └─ MiniMax-M3（回退 DeepSeek deepseek-chat）                     │
   └─────────────────────────────────────────────────────────────────┘

                         ▲
                         │
   ┌─────────────────────────────────────────────────────────────────┐
   │  💾 Git 仓库（本地 + GitHub 远端备份）                              │
   │                                                                   │
   │  skills-v2/             ← 三个 skill 的代码                         │
   │  evals/blackbox/        ← 测试 fixture + ground truth              │
   │  evolution/             ← state.json + proposals/ + log/          │
   │  evolve.sh              ← 循环入口                                │
   │  call_llm.py            ← LLM 调用                                │
   └─────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════

数据流（贯穿全图）：

   Git 仓库  ◄─── 一切代码与数据的"单一真相源"
       │
       ├─ state.json       (当前状态，机器可读)
       ├─ proposals/*.md    (LLM 提议，人类可读)
       ├─ log/*.json        (历史评分轨迹)
       └─ fixtures/         (黄金测试集)
```

---

## 图 2：当前状态卡（一眼看到"做到哪了"）

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       状态卡 (今天: 2026-09-22)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

  ┌─ 已完成 (✅) ──────────────────────────────────────────────────┐
  │  ✅ 黄金测试集        26 fixture + ground truth                 │
  │  ✅ 评分脚本         score_blackbox.py (precision/recall/F1)    │
  │  ✅ 状态机          evolution/state.json                       │
  │  ✅ 循环引擎         evolve.sh                                  │
  │  ✅ LLM 调用         call_llm.py (直接 curl MiniMax)             │
  │  ✅ 端到端跑通       test → score → LLM → proposal 全跑通        │
  │  ✅ 通知机制         企业微信 Webhook（notify.sh 已修复）        │
  │  ✅ 健康检查         ping MiniMax API + 状态写入 state.json     │
  │  ✅ launchd 部署     每天 9:00 自动跑（已迁出 ~/Documents）      │
  │  ✅ GitHub 公开仓库   andrew-tao-li/ai-audit-skills 已推        │
  └──────────────────────────────────────────────────────────────────┘

  ┌─ 待做 (❌) ────────────────────────────────────────────────────┐
  │  ❌ Token 充值       MiniMax rate_limited（已配 DeepSeek 回退） │
  │  ❌ 半自动 apply    OpenCode web 让 AI 改代码（用户决策）       │
  │  ❌ 真实审计师      还没找, 系统价值的"基准"                    │
  └──────────────────────────────────────────────────────────────────┘

  下一步最重要的 3 件事：
    1. 给 MiniMax 充值，恢复 LLM 分析（当前 rate_limited）
    2. 修 11 个 open_failures（3 个高危漏报优先）
    3. 找真实审计师  ← 系统的价值基准
```

---

## 图 3：邮件通知长什么样（规划中）

```
From: audit-box@macmini.local
To:   your-email
Subject: [Audit Box] 2026-09-21: 11 failures待分析

  ┌────────────────────────────────────────────────────────────┐
  │  Audit Skill Box 每日报告                                  │
  │  ────────────────────────                                │
  │                                                            │
  │  ✓ 测试: 26/26 跑通                                      │
  │  ✗ 失败: 11 个 (与上次相同)                              │
  │  ⚠ token: 充足                                            │
  │                                                            │
  │  expense:       F1=93%                                   │
  │  procurement:   F1=91%                                   │
  │  investigation: F1=100%                                  │
  │                                                            │
  │  最新提案:                                                  │
  │  evolution/proposals/2026-09-21-llm-analysis.md            │
  │                                                            │
  └────────────────────────────────────────────────────────────┘
```

---

## 图 4：你收到邮件后的决策树

```
                         📧 收到邮件
                              │
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
            [一切正常]    [有失败]    [⚠ token/API]
              关掉        5 分钟       15 分钟
                  │           │           │
                  ▼           ▼           ▼
              (关邮件)    ssh + cat    续费/修配置
                            proposal
                              │
                              ▼
                        AI 已写好分析
                              │
                              ▼
                        看 5-10 分钟
                              │
                  ┌───────────┼───────────┐
                  ▼           ▼           ▼
              同意         拒绝       需更多信息
              (git commit  (改 fixture   (在 OpenCode 里
               by AI in    or 改代码)    让 AI 深入)
               OpenCode)
                  │           │           │
                  ▼           ▼           ▼
              下次跑测试  下次跑测试  下次跑测试
```

---

## 关键概念词典（任何时候忘了回查这里）

| 术语 | 含义 |
|---|---|
| **Audit Skill Box** | 整个自我演化系统的代号 |
| **skill** | 三个审计模块：expense / procurement / investigation |
| **fixture** | 测试样本（含 ground truth 期望输出） |
| **state.json** | 当前机器可读状态：版本/分数/失败案例 |
| **proposal/*.md** | LLM 提议（人类可读） |
| **evolve.sh** | 每日循环入口 |
| **call_llm.py** | 直接 curl MiniMax API 的脚本 |
| **F1 分数** | 测试集准确率综合指标 (precision/recall) |
| **handoff** | 不同 skill 之间交接的证据包（procurement-fraud → investigation） |
| **scope gate** | investigation-assistant 的强制授权检查 |
| **Pareto 改进** | 不牺牲原有优点 + 让能力更强（不是"finding 数不变"） |
| **四层标记** | fact / inference / hypothesis / judgment 分类（防止误判） |

---

## 当你 2-3 天没碰项目后，10 分钟恢复记忆

```
1. 看图 1（架构全景）—— 系统是什么、谁在哪、数据怎么流
2. 看图 2（状态卡）—— 现在哪些 ready、哪些 TODO
3. cat evolution/state.json | python3 -m json.tool —— 看机器记录的当前状态
4. ls -lt evolution/proposals/ —— 看最近有哪些 LLM 提议
5. 决定要不要：
   - 应用某个 proposal（去 OpenCode web）
   - 跳到下一阶段（看 ROADMAP.md）
   - 找真实审计师试用（FOR-AUDITORS.md）
```

---

## 维护规则（防止文档腐烂）

- **每个 Tier 完成后**更新本文件的"状态卡"
- **每次加新组件**更新图 1 的架构
- **每完成 ROADMAP 一项**勾掉对应行
- **每季度 review 一次**整个文档

如果有一天这份文档和实际代码严重不一致，**文档是错的**，以代码为准并立即更新文档。
