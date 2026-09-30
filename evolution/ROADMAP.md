# Audit Skill Box — 路线图

> **这份文档**：长期路线图，每个 Layer 完成时更新。
>
> 完成一项就**勾掉**——这样你回来能一眼看到进度。

---

## 📋 当前 To-Do（2026-09-30 整理）

> 分三类：**卡在用户手上** / **AI 可自动做** / **暂缓（有理由）**。

### 🔴 卡在用户手上（AI 做不了）
1. **等 SkillHub 审核**（9/29 提交，3–7 工作日 → 预计 10/2–10/9）
2. **（可选）改昵称** —— 个人页当前显示「学涛」；不想公开真名就改笔名
3. **`clawhub login`** —— ClawHub 发布必须本人 GitHub 授权（5 分钟）
4. **公众号定稿发文** —— `docs/wechat-article.md` 已就绪，4 个标题候选待选
5. **找 1–2 位真实审计师试用** —— Layer 3 的真正起点

### 🟢 AI 可自动做（已在做 / 待做）
6. **ClawHub 上架准备**：分类/主题映射进配置、复用净化版、写发布脚本（只差 login）
7. **`CONTRIBUTING.md`**（Layer 1 唯一遗留）
8. **SkillHub 审核状态跟踪**：日报里增加"审核状态变化"提醒
9. **公众号草稿自动同步**：把最新能力（交叉核验/分类/两版架构）写进 `docs/wechat-article.md`
10. **平台数据周报视图**：日报现在只有当日快照，可加"本周 vs 上周"

### ⏸ 暂缓（有理由，不是忘了）
11. L2 反馈/评分机制（用户太少；平台评论已覆盖主要场景）
12. 企查查真实 Provider（等 cn-entity 实机跑通三态）
13. expense 数据层聚合（weekend 噪声 / 缺配置提示）——会动 F1 期望，需同步改黄金集
14. 代报销（区分报销人/实际出差人）——要改数据模型
15. `--header-row`（表头不在第一行）——已在接入指南写明是已知边界

### ⛔ 客观做不到
16. GUI 平台（WorkBuddy/龙虾/Cursor）自动测试 —— Mac mini 够不着用户的 GUI

---

## ⏸ 暂缓事项（下次回顾框架时提醒）

- **ClawHub 上架**（⬜ **已完全准备好，只差 `clawhub login`**，2026-09-30）：
  - ⚠️ **关键决定：ClawHub 也发净化版**（`dist-v2/skillhub/<skill>/`），不是 canonical——
    canonical 里的「反馈外发 webhook」与 `curl|bash` 正好撞上 ClawHub 安全审计的三个关注点
    （**凭据暴露 / 不安全执行 / 过度代理**）。与 SkillHub 同一逻辑：**市场版=净化版，GitHub canonical=全功能版**。
  - **ClawHub 没有"质量评估"**，它有**安全审计**（Audit status `Pass/Review/Warn/Malicious` + Risk `Low/Medium/High` + findings）；
    扫描方 = SkillSpector + **腾讯朱雀 A.I.G** + 自研 ClawScan；以 **OWASP Agentic Skills Top 10** 为透镜。
    与我们互补（SkillHub 答"好不好"，ClawHub 答"安不安全"）。审计页：`/<owner>/skills/<slug>/security-audit`。
  - 顺带：ClawHub **拒收含 `.pyc/.pyo/.pyd` 的 skill**（某 CVE 未修）——我们纯 `.py`，不受影响。
  - **ClawHub 分类体系统统与 SkillHub 不同**（`security/finance/operations/knowledge/research…`，最多 3 分类 + 5 主题），
    已映射进 `scripts/skillhub_config.py` 的 `clawhub_categories` / `clawhub_topics`。
  - `scripts/publish-clawhub.sh` **已重写**：改用净化版 + 从配置读 ClawHub 分类/主题 + 带来源仓库信息；
    已用 `--dry-run` 验证（`Would publish expense-audit-v2@0.2.10`）。
  - **唯一卡点**：`clawhub login`（设备流，必须用户本人 GitHub 授权）。另外官方要求「GitHub 账号足够老才能过上传闸门」。
  - 好处：打开国际/OpenClaw 生态（我们 SKILL.md 已声称支持它）· **SkillHub 会自动镜像 ClawHub**（多一个国内分发源）·
    **可引用的第三方安全结论**（可写进 README/公众号）· 真实安装量 · 为 SkillHub 的"认领"做准备。
  - 历史：`clawhub` CLI 已装（v0.23.3，`/opt/homebrew/bin/clawhub`）、license 已改 MIT-0。剩两件事待用户：① 跑 `clawhub login`（设备流）或给 API token；② ~~决定仓库根 `LICENSE` 是否也改 MIT-0~~ → **已决（2026-09-28）：仓库根保持 Apache-2.0，与 skill 的 MIT-0 通过 README 明确划分范围，不再统一**。发布命令已备好（见 install.md 或 `clawhub skill publish ./skills-v2/<skill> --slug ... --version 0.2.0`）。

- **SkillHub.cn 上架**（✅ **已提交，2026-09-29，审核中**）：
  - 命名空间：`@indiv-ai-audit`（用户已设，7 天可改一次；**改名会让原坐标/@名称/Slug 立即失效**，慎改）
  - 4 个 skill 已发布（skillId `256491`–`256494`），状态 **pending review**（3–7 个工作日）：
    `andrew-tao-li-expense-audit@0.2.9` / `-procurement-fraud@0.2.4` / `-investigation-assistant@0.2.4` / `-cn-entity-relation@0.1.4`
  - **slug 是全网唯一的**（不是命名空间内唯一）：`expense-audit` 已被 `@clawhub_mohitagw15856` 与 `@org-0ll53pt7` 占用，
    故保留 `andrew-tao-li-` 前缀——**这是必要的，不是冗余**（平台文档也建议 slug 带上作者标识）
  - 发布命令：`skillhub publish dist-v2/skillhub/<skill> --changelog "..."`（注意**限频**：连续发 4 个会撞 429，需间隔约 1 分钟）
  - 审核通过后可用：`skillhub comment list <slug>`（用户评论）、`skillhub skill evaluation <slug>`（**平台 AI 五维评估报告**）、
    `skillhub skill reports <slug>`（科恩+云鼎安全报告）、`skillhub skill rankings`（下载/安装/收藏/排名）
  - **已接入每日日报**（2026-09-29）：`evolution/skillhub_stats.py` + `evolve.sh` Step 6b——
    下载/安装/收藏/评论 + GitHub star/issue，带**增量**（↑安装 3、💬新评论 1）；只读、失败不中断。
  - **分类（2026-09-29 实测）**：
    - 官方 CLI 的 publish payload **没有** `category` / `subCategories` → CLI 发出来永远「未分类」，而分类决定能否进**分类浏览**。
    - **但服务端接受这两个字段**（实测 HTTP 201，且分类**立即生效**，新版本号仍需审核）→
      新增 `scripts/publish-skillhub.py`（照官方 multipart 契约自己发 + 带分类 + 自动限频 70s）；
      分类的单一来源是 `scripts/build-skillhub.py` 的 `SKILLS`。
    - 网页端也能改（个人中心 → 我的 Skill → 编辑），但会触发内容重审。
    - 四个 skill 现已全部设为 `professional`（行业专业）+ 对应子类。
  - **版本对齐**：为了让 SkillHub 版与 canonical 一致，发了 **v0.3.9**（纯版本号 + 发布器，**脚本零变化**）。
  - **下一步**：等审核通过（3–7 个工作日），届时日报里的数字开始动
  - 平台要求 SKILL.md frontmatter 含 `slug/displayName/version/summary/license`（与我们的 `name/description/metadata` 不同）。
  - 三线安全审核：**内容合规 + 科恩实验室漏洞扫描 + 云鼎 AI 模型安全评估**，3–7 工作日；任一不过即拒。
  - 我们 canonical 里有两处**会被安全审核盯上**（对 GitHub 分发合理，但不能直接上传）：
    ① 反馈机制向作者固定 webhook POST（`references/feedback.md` 硬编码 key）→ 判「数据外发」；
    ② SKILL.md 的 `curl … | bash` 一键更新 → 判「远程执行」。
  - **已解决**：`scripts/build-skillhub.py` 生成净化版到 `dist-v2/skillhub/<skill>/` —— 删反馈外发、删 curl|bash、补 frontmatter、规范化 `__import__` 写法；**canonical 与 GitHub release 不受影响**。已自检（无 key / 无外发 / 无 curl|bash / 无动态导入）。
  - 上架命令（认证完成后）：`skillhub login --key skh_xxx --host https://api.skillhub.cn` → `skillhub publish dist-v2/skillhub/<skill> --dry-run` → 去 `--dry-run` 正式发。
  - **LICENSE 不一致已了结**（2026-09-28）：许可范围**明确划分**——各 skill = **MIT-0**（manifest + SkillHub frontmatter），仓库脚手架 = **Apache-2.0**（根 `LICENSE`）；中英文 README 均已写明，不再标"待统一"。理由：两者实质差异对本项目≈0（无专利/NOTICE），明确划分即可消除法务 review 的歧义。

- **真实审计师反馈驱动的改进（2026-09-29，已完成 v0.3.7）**：一位真实审计师用**真实差旅台账**（155 有效行、3 人）实测 expense-audit-v2，报告见对话记录。核心发现与处理：
  - 🔴 **最严重**：真实台账带「审批状态」列（已同意/已撤回/已拒绝），而脚本没有状态概念 → **47 条发现里 39 条（83%）是"撤回后又重提"造成的假阳性**。→ **已修（v0.2.8）**：新增可选 `status_filter`；被排除行写入 `excluded_by_status.csv`（绝不静默丢弃）。
  - 🟠 **附带红利**：有状态后可做新规则 → **「撤回/拒绝后重提且金额增加」**（报告里真发现 1 例 +¥2,400）→ **已做**。
  - 🟠 **装入错平台**：`install.sh` 只认 opencode/workbuddy/lobsterai，豆包被回退成 opencode → **已修**：新增豆包支持（`Doubao/User Data/Default/.doubao/agent_mode/workspace/.user_skills`，Win=`%LOCALAPPDATA%` / mac=`Application Support`），**追加在探测顺序最后，不影响任何既有平台**；多 Agent 并存时给提示。
  - 🟠 **多列金额要手工预处理** → **已做**：`amount_columns` 多列求和 + 新增 `references/field-mapping-guide.md`（含"表头不在第一行"这一已知边界）。
  - ⚪ 附件名 `&amp;` → 判定为对方下载工具问题，非本工具缺陷。
  **仍未做（P2，需单独立项）**：
  1. **代报销**（区别"报销人"与"实际出差人"）——报告里 81/78 条交叉验证发现都指向它；
  2. ~~**交叉验证**（报销 × 出差申请 × 打卡）~~ → **已做（v0.2.9）**。原判断（"需单开 skill"）被用户驳回且**用户是对的**：出差的真实性本来就靠打卡/出差申请印证，属同一审计问题；且与"没发票→发票规则跳过"是同一模式（可选输入→自动唤醒）。已实现：`--travel-requests` / `--attendance` 可选输入 + 4 条规则 + 「是否在公司」三层判定（显式布尔/经纬度+半径/地点关键词）；不提供辅助数据时零影响。；
  3. 表头不在第一行（`--header-row`）——目前靠预处理，未做配置项。

- **L2 反馈/评分机制**（已出设计，暂缓，2026-09-23）：让作者收到技能在别人 Agent 上的使用反馈。暂缓原因：① 现在用户太少、反馈稀疏；② 平台适配不确定，现在做可能牺牲稳健性。
  设计要点（已定，下次可直接开工）：
  - 核心原则：离线脚本一行不动、绝不自动上报；反馈是「旁路」，完全可选、默认关。
  - 三触点：① 输出里加「反馈邀请 + 三档评分(👍帮上忙/😐一般/👎没帮上) + 可选文字框 + 隐私说明」文字；② SKILL.md 给宿主「如何邀请」指引（话术 + 约每 3 次才主动提一次、绝不打断/强制）；③ 独立 `--report` 命令（脱敏上报，走企业微信 webhook 或 GitHub Issue）。
  - 隐私话术要点：「数据始终留在本地；只有主动提交才回传脱敏摘要（评分+文字+运行统计），不含金额/人员/供应商/发票号等敏感信息；可随时跳过」。
  - 明确不做 L3（每次全自动上报），因与离线设计冲突。

- **企查查 MCP 能力映射 + 真实 QccProvider**（暂缓，2026-09-24）：把企查查 182 个原子工具里与关联排查相关的，映射到内部 `STRONG_RELATION_TYPES`，在 `provider_adapter.py` 的 `MockProvider` 旁补一个真实 `QccProvider` 骨架。暂缓原因：用户要求先简化、先保证多平台稳健跑通，不急着做真实 provider 接入的复杂度。
  设计要点（已定，下次可直接开工）：
  - 只映射 V0.1 强关系（法人/股权/投资/董监高/合伙/分支/实控/UBO + 历史），弱线索（同电话/地址/诉讼等）不进强图。
  - 企查查 MCP 原生「强语义负向防御」→ 直接映射 `provider_supports_negative_semantics=true`（可输出「不关联」）。
  - 企查查有「关系图谱 / 股权穿透」能力，可评估是否替代本地 BFS（但三态协议 + result_validator 仍保留，做确定性兜底）。
  - 测试需一个企查查 API Key（BYOK，只本地用，绝不进仓库）。
  - 优先级：等第 4 技能在 WorkBuddy 等平台实机跑通三态后，再回头做。

- **审批闭环（半自动 AI 提案 → 人类审批 → 自动应用）**（机制已建，2026-09-26）：Layer 2 的「工具」都写好了（`guardrail.py` 的 apply/verify/rollback、`evolve.sh` 的提案生成、OpenCode web），但「闭环」没接起来——现状是「半自动的工具箱，不是半自动的流水线」。
  **已实现（2026-09-26）**：
  - `evolution/propose_fix.py`：读失败（state.json 的 `open_failures` + **OpenCode 验收结果**）→ 隔离工作区 → 建分支 → 用 OpenCode（`opencode run --auto`）尝试修复 → push → **开 PR** → 企业微信通知。
  - `evolution/patrol.py`：**定期主动巡检**（每 7 天，4 个审视角度轮换：描述触发准确性 / 文档一致性 / 规则覆盖盲点 / 审计语言可用性）→ 没失败也主动找一条最小改进 → 开 PR。
  - `.github/workflows/pr-verify.yml`：每个 PR 自动跑 `validate_pack --run-tests` + 黑盒 F1，任一退步则 PR 检查失败。
  - **审批 = 在 GitHub 上合并 PR**（原生 diff 审阅 + CI 校验 + 合并即生效）；拒绝 = 关闭 PR。
  - `evolve.sh`：Step 4b（有失败→propose_fix）、Step 4c（每 7 天→patrol）。
  - 用户已给 PAT 补 `Pull requests: read and write` 权限；**全流程已实测通过**（PR #1 冒烟、PR #2、PR #3 真实巡检 + 合并生效）。
  - **隔离修复**：propose_fix/patrol 先把无关改动 `git stash` 隔离，避免 `git add -A` 把未提交的手工改动/例行副作用扫进 PR。
  - **安装冒烟测试**（`evals/install_smoke.py`，2026-09-27）：端到端验证**用户真正的安装路径**——从 `releases/latest/download/` 下载 → `install.sh` 装到临时目录 → 真跑一遍，核对「release 版本 == main」「sha256 == 本机 dist」「装完产出 dashboard」。这是以前**零覆盖**的一段（已因此踩坑两次），现接 `evolve.sh` Step 1c 每日跑。
  - **「未执行」显性化**（2026-09-27）：日报单独列「⚠️ 未执行: …」，避免「失败: 0」掩盖「这一项根本没跑」；验收/冒烟行带 ✅/⚠️ 前缀。
  - **launchd PATH 修复**（2026-09-27）：`opencode` 装在 `/opt/homebrew/bin`（Apple Silicon），而 launchd 的 PATH 不含该目录 → **每日 OpenCode 验收一直「跳过」**。修法：`evolve.sh` 自行前置 Homebrew 路径（不依赖 plist）+ 修正 plist 模板与已安装 plist。
  **⚠ 关键前提：必须给定时任务配 GITHUB_TOKEN，否则闭环是「哑」的（2026-09-26 发现）**：
  - `propose_fix` / `patrol` 都需要 `GITHUB_TOKEN`；**launchd 默认没有**，所以每天 9:00 的例行只发「每日报告」，**永远不会开 PR**。
  - 配置方式：仓库外私有文件 `~/.config/ai-audit-skills/env`（内容 `export GITHUB_TOKEN=...`，chmod 600）；`evolve.sh` 启动时会自动 source 它。**密钥绝不写进仓库，也不写进 plist。**
  - 只有手动在带 token 的 shell 里跑 `patrol.py` / `propose_fix.py` 才会开 PR 并通知——**如果收到「去 GitHub 审阅」的通知却找不到东西，多半是手动测试发的**。
  **通知措辞已澄清**：标题改为「有 N 个待审批的 Pull Request」；正文明确「在 GitHub 的 **Pull requests** 里审阅，合并 = 采纳，关闭 = 拒绝」并给「全部待审批 PR」链接；每日报告新增「待审批 PR: N 个」一行。**本仓库只用 PR，不用 Issue。**
  **测试防打扰**：`patrol.py` / `propose_fix.py` 新增 `--no-notify`，测试时用它，不再往企业微信刷通知。
  **仍未做**：
  - `evolve.sh` 的 LLM 分析步骤仍只在「失败数 > 0」时生成；不过巡检已覆盖了"健康时也进化"的需求。

- **expense 输出打磨（低优先级）**（暂缓，2026-09-24；**呈现层已于 2026-09-26 处理**）：审计师盲测暴露的两个 UX 项，**非正确性问题，可缓**。① config 驱动规则（split-expense / policy-threshold / large-amount-low-level / missing-expense-type 等）缺配置时静默跳过，虽有 `data_quality` 记录「未提供 limits」等，但首跑用户可能误以为「漏检」；② weekend-signal 占 findings 约 88% 噪声，虽已标 weak/low 且 `summary` 给了复核顺序，但 `findings.csv` 仍是一屏噪声。
   - **已做（呈现层，v0.3.5）**：dashboard 改版后，第一屏直接用**风险管理语言**翻译「多」——论点句会写明「其中数量最多的是『周末消费』共 N 条，属提示性信息…通常无需逐条处理」，并配风险分布条（高/中/低）与「按类型汇总」表。经理不会再被 88% 的噪声误导。
   - **仍未做（数据层）**：把 weekend-signal 在 `findings` 层聚合为一条「N 条周末消费，按部门抽样」而非 N 条独立 finding；以及首跑时把「因缺配置被跳过的规则」更醒目提示。
   - 若要做的方向：① 在 summary/README 把「因缺配置被跳过的规则」更醒目列出；② 在 findings 层聚合 weekend-signal（注意会改变 F1 黄金集期望，需同步更新）。

---

## 路线图总览（4 个 Layer）

```
Layer 0 (基础): 自动跑测试 ← 2026-09-21 ✅ 已完成
Layer 1 (通知): 每天自动通知用户 ← 本周目标
Layer 2 (半自动): AI 提议 + 人类审批 ← 第 2-3 周目标
Layer 3 (自给自足): 自动扩展 + 真实审计师反馈 ← 第 1-2 个月目标
Layer 4 (自适应): 跨 skill 协同 + 自我优化 ← 长期
```

---

## Layer 0: 基线 ✅ 已完成

- [x] 黄金测试集（26 fixture + ground truth）
- [x] 评分脚本 score_blackbox.py
- [x] 状态机 evolution/state.json
- [x] 循环引擎 evolve.sh
- [x] LLM 调用 call_llm.py
- [x] 端到端跑通：test → score → LLM → proposal

**完成时间**：2026-09-21

**关键产物**：
- `evolution/proposals/2026-09-21T07:03:03Z-llm-analysis.md`
- 第一个 LLM 分析 5893 字符

---

## Layer 1: 通知机制 ✅ 已完成（2026-09-22）

**目标**：用户不需要登录 Mac mini 就能知道系统在跑什么。

### 任务清单

- [x] **1.1 通知脚本**（半天）
  - [x] 写 `evolution/notify.sh`：企业微信 Webhook（优先）/ 邮件（fallback）/ 日志
  - [x] 处理 token 耗尽情况
  - [x] 处理 API 不可达情况
  - [x] 验证：企业微信测试通知已实发成功

- [x] **1.2 健康检查**（半天）
  - [x] evolve.sh 跑前先 ping MiniMax API
  - [x] 失败时通知 + 跳过 LLM 步骤
  - [x] 加 `state.json` 字段记录健康状态与检查时间

- [x] **1.3 Mac mini 部署**（半天）
  - [x] 复制整个项目到 Mac mini
  - [x] 安装 launchd plist（每天 9:00 自动跑）
  - [x] 迁出 `~/Documents`（解决 macOS TCC `Operation not permitted`）
  - [x] 验证 launchd 后台实际跑通

- [x] **1.4 GitHub 公开仓库**（半天）
  - [x] 推送到 GitHub（公开）
  - [x] 写 README
  - [ ] 写 CONTRIBUTING.md（待补）

**完成时间**：2026-09-22

**遗留**：MiniMax 当前 `rate_limited`（Token 配额用尽），需充值后 LLM 分析才会恢复。

---

## Layer 2: 半自动闭环 ⏳ 第 2-3 周

**目标**：AI 提议 → 人类审批 → AI 应用 → 自动验证。

### 任务清单

- [x] **2.1 OpenCode web server**（1-2 天）✅ 2026-09-22
  - [x] 在 Mac mini 后台跑 `opencode serve`（launchd 常驻，`com.opencode.web`，端口 4096）
  - [x] 设置 `OPENCODE_SERVER_PASSWORD`（basic auth，用户名 opencode）
  - [x] 用户通过浏览器访问（Tailscale `100.118.163.58:4096` / 局域网 `192.168.100.147:4096`）
  - [x] 落地脚本：`scripts/setup-opencode-web.sh` + 模板 `evolution/com.opencode.web.plist`

- [x] **2.2 半自动 apply 命令**（已完成 2026-09-22）
  - [x] `guardrail.py apply -m "..."`：跑测试对比基线，通过则 `git commit`，退步则自动回滚
  - [x] 显示 diff 给用户预览（apply 前用 `git diff` 审阅）
  - [x] 用户输入 y/n 决定（网页里审阅 diff → 同意 → 触发 apply）
  - [x] AI 应用 patch + 跑测试 + git commit（首个修复已落地：expense F1 0.9304→0.9359）

- [x] **2.3 A/B 测试保护**（已完成 2026-09-22）
  - [x] 每次改动必须保持 F1 不退步（`evolution/guardrail.py`）
  - [x] 如果退步 → 自动回滚（`guardrail.py verify --rollback`，只回滚 skills-v2/skills 代码）
  - [x] 在 state.json 记录每次改动的 before/after 分数（`guardrail_history`）

- [x] **2.4 半自动 fixture 生成**（已完成 2026-09-22）
  - [x] LLM 生成 N 个候选 fixture（`evolution/fixture_generator.py generate`，完整 CSV + ground truth）
  - [x] 跑 skill 验证一致性（`validate`，报告漏报/误报）
  - [x] 人工 review + 迁入黄金集（`promote`，复跑确认 F1 不退步）

**完成时间目标**：2026-10-12

---

## Layer 3: 自给自足 ⏳ 第 1-2 个月

**目标**：系统能自己扩展测试集 + 真实审计师反馈循环。

### 任务清单

- [ ] **3.1 真实审计师招募**（2 周）
  - [ ] 写 `docs/FOR-AUDITORS.md`（30 分钟试用指南）
  - [ ] 准备 2-3 份脱敏的真实案例
  - [ ] 在审计师群、朋友圈、星球转发
  - [ ] 目标：3-5 个真实审计师试用 + 反馈

- [ ] **3.2 反馈收集机制**（3 天）
  - [ ] GitHub Issues 模板
  - [ ] 结构化反馈表
  - [ ] 月度反馈总结

- [ ] **3.3 fixture 持续扩展**（持续）
  - [ ] 每月基于审计师反馈新增 5-10 个 fixture
  - [ ] 真实业务覆盖度评估
  - [ ] 自动化 fixture 覆盖率报告

- [ ] **3.4 业务合理性 self-critique**（1 周）
  - [ ] 每个 LLM 提议前自我批评
  - [ ] 检查 4 个维度：业务意义 / 误报成本 / 反例检验 / 替代解释
  - [ ] 如果 self-critique 失败 → 不写入 proposal

**完成时间目标**：2026-11-15

---

## Layer 4: 自适应 ⏳ 长期

**目标**：跨 skill 协同 + 系统自我优化。

### 任务清单

- [ ] **4.1 跨 skill handoff 自动化**
  - [ ] procurement → investigation 自动触发
  - [ ] 多 skill 协同分析

- [ ] **4.2 长期趋势分析**
  - [ ] 哪些 finding 类型在增多？
  - [ ] 哪些业务场景盲点在变化？
  - [ ] 自动调整阈值

- [ ] **4.3 业务领域扩展**
  - [ ] 银行 / 制造业 / 服务业 各自定制版本
  - [ ] 行业模板化配置

---

## 重大决策点（不轻易改变）

| 决策 | 决定 | 原因 |
|---|---|---|
| 数据存储 | 本地 JSON | 不依赖数据库，git 可追溯 |
| AI 推理路径 | 直接 curl MiniMax | 不依赖 OpenCode GUI |
| 修改代码 | 必须人类审批 | 审计工具的特殊性 |
| fixture 来源 | 真实审计师 > LLM > 手工 | 真实性 > 覆盖度 |
| 分发渠道 | GitHub + 本地 | 开源 + 数据可控 |
| 通知机制 | 邮件（未来可加 IM） | 通用、可靠 |

---

## 月度检查清单

每月底问自己 5 个问题：

1. 这个月 F1 分数变化趋势如何？
2. 真实审计师给了哪些反馈？
3. 有没有新的盲点被发现？
4. token 消耗和预算是否合理？
5. 下一阶段的卡点是什么？

---

## 完成定义（每 Layer 的"Done"标准）

### Layer 1 Done
- [ ] 每天收到一封审计报告邮件
- [ ] Mac mini 持续运行 7 天无人工干预
- [ ] GitHub 仓库公开有 README

### Layer 2 Done
- [ ] 用户从邮件 → proposal → apply → 测试 → git commit 全流程可完成
- [ ] 至少 5 次成功应用
- [ ] 0 次因 apply 引入的回归

### Layer 3 Done
- [ ] 3 个以上真实审计师试用 + 给反馈
- [ ] fixture 库包含真实脱敏案例
- [ ] self-critique 拒绝率 < 30%（不是太严，也不是放水）

### Layer 4 Done
- [ ] handoff 自动化触发
- [ ] 系统能持续优化 6 个月以上
- [ ] 用户每月投入 < 5 小时

---

## 风险登记（持续更新）

| 风险 | 状态 | 缓解 |
|---|---|---|
| Token 配额耗尽 | 已知 | 通知 + 健康检查 |
| MiniMax API 变更 | 已知 | call_llm.py 适配层 |
| Fixture 漂移 | 进行中 | Layer 3 真实审计师校准 |
| 复杂度爆炸 | 监控中 | 每个 Layer ≤ 2 个新文件 |
| 真实审计师招不到 | 未验证 | Layer 3 第一优先级 |
