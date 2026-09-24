# Audit Skill Box — 路线图

> **这份文档**：长期路线图，每个 Layer 完成时更新。
>
> 完成一项就**勾掉**——这样你回来能一眼看到进度。

---

## ⏸ 暂缓事项（下次回顾框架时提醒）

- **ClawHub 上架**（已调研完毕，暂缓，2026-09-22）：`clawhub` CLI 已装（v0.23.3）、license 已改 MIT-0、SKILL.md frontmatter（version/author）已就绪。剩两件事待用户：① 跑 `clawhub login`（设备流）或给 API token；② 决定仓库根 `LICENSE` 是否也改 MIT-0。发布命令已备好（见 install.md 或 `clawhub skill publish ./skills-v2/<skill> --slug ... --version 0.2.0`）。

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

- **审批闭环（半自动 AI 提案 → 人类审批 → 自动应用）**（已定位缺口，待接，2026-09-24）：Layer 2 的「工具」都写好了（`guardrail.py` 的 apply/verify/rollback、`evolve.sh` 的提案生成、OpenCode web），但「闭环」没接起来——现状是「半自动的工具箱，不是半自动的流水线」。
  三个缺口：
  1. `evolve.sh` 的 LLM 提案**只在「失败数 > 0」时生成** → 现在 F1=100% 天天跳过，健康时永远不进化（等于 F1 满后停摆）。
  2. 提案生成后**不推送审批**：通知只说「有提案」+ 路径，从不问「批不批」。
  3. `guardrail.py apply` **没有 y/n 交互**：所谓「人类审批」实际就是「作者自己决定要不要手敲这条命令」。
  设计要点（下次可直接开工）：
  - 先定一个产品决策：**健康时（F1=100%）要不要也定期让 LLM 主动提议改进**（比如基于 baseline_warning「单 finding 设计」这类提示），否则这套框架在满分后就失去进化动力。
  - evolve.sh 有提案时，通知文案加一句引导（如「有新提案 evolution/proposals/xxx.md，可上 OpenCode 网页审阅并决定是否 apply」）。
  - 给 `guardrail.py apply` 加真正的 approve 入口（至少 `--confirm` 的 y/n 交互；更完整则是 OpenCode web 里的审批流），把「审阅 diff → 批准 → 自动 apply」串起来。

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
