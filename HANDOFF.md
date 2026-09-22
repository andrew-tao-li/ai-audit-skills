# OpenCode 接手文档（HANDOFF）

> **目的**：让 Mac mini 上的 OpenCode CLI/Desktop 接手 debug + 修复 Audit Skill Box 后台任务。
>
> **使用方法**：
> 1. 打开 OpenCode（CLI 或 Desktop），cd 到 `/Users/rockymary/Documents/ai-audit-skills/repo`
> 2. 把下面"给 OpenCode 的 prompt"粘贴进去
> 3. OpenCode 会自动排查 + 修复 + 验证

---

## 项目背景

我们正在把一个"自我演化审计 skill"项目部署到 Mac mini。整套架构：

```
GitHub: andrew-tao-li/ai-audit-skills  (公开仓库，4 个 commit)
Mac mini: /Users/rockymary/Documents/ai-audit-skills/repo
launchd 任务: com.audit.skill.box (期望每天 9:00 自动跑 evolve.sh)
通知渠道: 企业微信 Webhook (已配)
```

完整设计文档：
- `evolution/ARCHITECTURE.md` —— 系统全景图
- `evolution/ROADMAP.md` —— 路线图
- `evolution/MIGRATION.md` —— 部署指南
- `AGENTS.md` —— 项目协议

---

## 给 OpenCode 的 prompt（直接复制粘贴）

```
你是一个自动化 debug 助手。你的任务是让 Mac mini 上的 launchd 任务 com.audit.skill.box 正常运行。

## 你可以用的工具
- bash 工具：跑任何 shell 命令
- 文件读写：读 / 写项目内文件
- 你能调 MiniMax API（OpenCode 已配）

## 当前状态（我已经知道的）
- Mac mini 系统：macOS 25.4.0 arm64，用户 rockymary
- 项目在：/Users/rockymary/Documents/ai-audit-skills/repo
- launchd plist 在：~/Library/LaunchAgents/com.audit.skill.box.plist
- plist 已含：
  - WorkingDirectory: /Users/rockymary/Documents/ai-audit-skills/repo
  - StandardOutPath: /Users/rockymary/Documents/ai-audit-skills/repo/evolution/log/launchd-stdout.log
  - StandardErrorPath: /Users/rockymary/Documents/ai-audit-skills/repo/evolution/log/launchd-stderr.log
  - EnvironmentVariables.MINIMAX_API_KEY = sk-cp--... (完整 token 在文件里)
- launchctl list | grep audit 显示 10208 0 com.audit.skill.box
- launchctl start com.audit.skill.box 不报错
- 但 stdout 文件是空的
- evolution/state.json 里 health = "no_api_key"
- iteration_count 还是 10（不增加）

## 任务（请按顺序做）

### Phase 1: 排查（read-only，不要修改任何东西）

1. 确认 plist 文件实际内容：
   ```bash
   /usr/libexec/PlistBuddy -c "Print" ~/Library/LaunchAgents/com.audit.skill.box.plist
   ```
   确认 MINIMAX_API_KEY 真的有值

2. 看 launchd 任务实际状态：
   ```bash
   launchctl print gui/$(id -u) 2>&1 | grep -A 5 "com.audit.skill.box" | head -20
   ```
   （macOS 用户 session 是 gui domain）

3. 看 stdout / stderr 文件：
   ```bash
   ls -la ~/Documents/ai-audit-skills/repo/evolution/log/
   cat ~/Documents/ai-audit-skills/repo/evolution/log/launchd-stdout.log
   cat ~/Documents/ai-audit-skills/repo/evolution/log/launchd-stderr.log
   ```

4. 看上次 launchd 运行结果：
   ```bash
   launchctl print user/$(id -u) 2>&1 | grep -B 2 -A 8 "com.audit.skill.box" | head -40
   ```
   注意：last exit code、pid、运行时间

5. 看 Mac mini 系统日志（看 launchd 相关错误）：
   ```bash
   log show --predicate 'subsystem contains "launchd" and eventMessage contains "audit"' --info --last 24h | tail -20
   ```

6. **手动模拟 launchd 跑脚本**（关键测试——如果这条命令能跑通，脚本本身 OK，问题只在 launchd 传环境变量）：
   ```bash
   cd /Users/rockymary/Documents/ai-audit-skills/repo
   env $(/usr/libexec/PlistBuddy -c "Print :EnvironmentVariables" ~/Library/LaunchAgents/com.audit.skill.box.plist | grep = | sed 's/^/export /' | tr '\n' ' ') /bin/bash ./evolve.sh 2>&1 | tail -40
   ```
   （这一行从 plist 读出 EnvironmentVariables 并 export，然后跑脚本）

7. 看 ~/.zshrc 里的 API key：
   ```bash
   grep "MINIMAX_API_KEY" ~/.zshrc
   ```

### Phase 2: 修复（根据 Phase 1 诊断结果决定）

#### 方案 A: 如果 Phase 1 第 6 步跑通（手动跑成功），说明是 launchd 不传环境变量
- 把 MINIMAX_API_KEY 从 EnvironmentVariables 移到 .zshrc
- 修改 evolve.sh 第一行加 `source ~/.zshrc`
- 重跑 launchd

#### 方案 B: 如果第 3 步 stdout/stderr 是文件路径不存在
- 修改 plist 的 StandardOutPath/StandardErrorPath 到正确路径

#### 方案 C: 如果第 4 步显示 launchd 根本没启动过这个 job
- 重新 launchctl load + start

#### 方案 D: 如果第 5 步系统日志显示 plist 语法错误
- 用 plutil -lint 修语法

### Phase 3: 验证

不管哪个方案，做完都跑：

```bash
# 完全卸载重载
launchctl unload ~/Library/LaunchAgents/com.audit.skill.box.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.audit.skill.box.plist

# 立即启动
launchctl start com.audit.skill.box

# 等
sleep 30

# 验证
ls -lt ~/Documents/ai-audit-skills/repo/evolution/log/ | head -3
cat ~/Documents/ai-audit-skills/repo/evolution/state.json | python3 -m json.tool | grep -A 2 "health\|iteration_count" | head -10
```

期望：
- stdout 文件**不再为空**
- state.json 的 health = "ok"
- iteration_count + 1（说明新迭代跑过）

### Phase 4: 报告

写一份简短报告：
1. 找到的根因是什么（不超过 3 句话）
2. 做了什么修复
3. 验证结果（贴 state.json 的 health 和 iteration_count）

---

## 修复后的额外动作

修完 launchd 任务后，**告诉我**——我会 commit + push 修复结果到 GitHub，让 MacBook 这边也能看到。

---

## 已知文件结构（你可以直接读）

```
/Users/rockymary/Documents/ai-audit-skills/repo/
├── AGENTS.md
├── README.md
├── evolve.sh                                  ← 主循环脚本
├── call_llm.py                                ← LLM 调用
├── score_blackbox.py                          ← 测试评分
├── scripts/
│   ├── setup-mac-mini.sh                      ← 一次性部署
│   └── mac-mini-bootstrap.sh                  ← 空白起步
├── evolution/
│   ├── state.json                             ← 当前状态
│   ├── ARCHITECTURE.md                        ← 系统全景
│   ├── ROADMAP.md                             ← 路线图
│   ├── MIGRATION.md                           ← 部署指南
│   ├── notify.sh                               ← 通知机制
│   ├── com.audit.skill.box.plist              ← launchd 任务
│   ├── notify_config.json
│   ├── proposals/                              ← LLM 提议
│   └── log/                                    ← 运行历史
└── evals/
    └── blackbox/                               ← 测试集
        ├── fixtures/
        ├── ground_truth/
        └── call_llm.py
```

---

## 常见问题速查

| 问题 | 答案 |
|---|---|
| 怎么调用 LLM? | `python3 evals/blackbox/call_llm.py --prompt "..." --out out.txt`（API key 在 shell 环境变量或 ~/.zshrc） |
| 怎么跑测试? | `python3 evals/blackbox/score_blackbox.py --version v0.2.0-baseline` |
| 怎么跑完整循环? | `./evolve.sh` |
| 怎么验证修复? | 看 `state.json` 的 health 字段（应该从 no_api_key → ok） |

---

## 完成后请回报

把以下信息贴回来给我（我不在 Mac mini 上，看不到你的环境）：

1. **找到的根因**（一句话）
2. **做了什么修复**（列步骤）
3. **最终验证**：
   - `cat ~/Documents/ai-audit-skills/repo/evolution/state.json | python3 -m json.tool | grep -A 2 health`
   - `cat ~/Documents/ai-audit-skills/repo/evolution/log/launchd-stdout.log | tail -10`
4. **是否需要修文档/setup 脚本？**（这次暴露的 bug 应该写进 setup-mac-mini.sh 防止再发生）

---

## 关键提醒

- **不要 push 到 GitHub**（除非我让你 push），保持本地工作
- **不要改 source code**（除非确认是 bug）
- **优先用只读命令排查**，定位后再改
- 改完先跑一次 `./evolve.sh` 验证再标"完成"
