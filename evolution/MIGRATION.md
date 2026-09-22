# Mac mini 部署与恢复指南

> **目的**：在 Mac mini 上把项目从零搭起来，并接入 GitHub 持续同步。
>
> 预计耗时：30–60 分钟（一次性）。

---

## 1. 准备（一次）

### 1.1 系统要求

| 项 | 验证命令 | 期望 |
|---|---|---|
| macOS | `sw_vers` | 任意（macOS 12+） |
| Python | `python3 --version` | ≥ 3.10 |
| Git | `git --version` | 任意 |
| 磁盘空间 | `df -h ~` | ≥ 1 GB 空闲 |
| 网络 | `curl -I https://api.minimax.io` | 200 |

### 1.2 安装缺失依赖

```bash
# 如果 Python < 3.10
brew install python@3.11

# openpyxl（XLSX 输入支持）
python3 -m pip install openpyxl

# 验证
python3 -c "import openpyxl; print('openpyxl', openpyxl.__version__)"
```

### 1.3 生成 SSH key（如果还没有）

```bash
ls -la ~/.ssh/id_ed25519.pub 2>/dev/null || {
    ssh-keygen -t ed25519 -C "you@macmini.local"
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/id_ed25519
}

# 把公钥贴到 GitHub：https://github.com/settings/keys
cat ~/.ssh/id_ed25519.pub
```

---

## 2. 拉取项目

### 2.1 创建目录

```bash
mkdir -p ~/ai-audit-skills
cd ~/ai-audit-skills
```

> **为什么不用 `~/Documents`**：macOS 的 TCC 隐私保护会阻止 launchd 后台进程访问 `~/Documents`（报错 `Operation not permitted` / `getcwd: cannot access parent directories`），导致每日任务无法运行。请把项目放在 `~/ai-audit-skills` 这类不受 TCC 保护的位置。

### 2.2 Clone（用 SSH 方式）

```bash
git clone git@github.com:andrew-tao-li/ai-audit-skills.git
cd ai-audit-skills
```

### 2.3 验证

```bash
ls -la evolution/ scripts/  # 应该看到 ARCHITECTURE.md, notify.sh, setup-mac-mini.sh 等
```

---

## 3. 一键 setup

```bash
./scripts/setup-mac-mini.sh
```

setup 脚本会问几个问题：

1. **API key**：粘贴 `MINIMAX_API_KEY`（即 `sk-cp-...`）
2. **DeepSeek 回退 key**（可选）：粘贴 `DEEPSEEK_API_KEY`（即 `sk-...`）。MiniMax 配额耗尽/不可用时，`evolve.sh` 自动改用 DeepSeek。
3. **企业微信 Webhook**（可选）：
   - 在企业微信群 → 添加群机器人 → 复制 Webhook URL
   - 格式：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx`
   - 直接回车跳过（会用邮件或仅写日志）

### 完成后会

- 写 `~/.zshrc`（含 API key）
- 部署 launchd plist 到 `~/Library/LaunchAgents/`
- 加载后台任务
- 立即跑一次 `evolve.sh` 验证

---

## 4. 验证

### 4.1 立即验证

```bash
# 手动跑一次完整循环
./evolve.sh

# 看 evolution/log/ 目录
ls -lt evolution/log/ | head -5
```

### 4.2 验证 launchd

```bash
# 确认任务已加载
launchctl list | grep audit

# 立即触发（不等到 9:00）
launchctl start com.audit.skill.box
```

### 4.3 验证通知

如果配了企业微信 Webhook：
- 应该在你创建的企业微信群里看到一条消息

如果没配：
- 邮件应该在 `~/Library/Containers/com.apple.mail/Data/Library/Mail/...` 或 macOS Mail.app 里
- 或本地 `evolution/log/notifications.log` 有记录

---

## 5. GitHub 双向同步

### 5.1 Mac mini 上也配 PAT（如果想从 Mac mini 推送到 GitHub）

```bash
# 在 Mac mini 上生成另一个 PAT（推荐 fine-grained，7 天，Contents: read+write）
# 方式：
#   1. 浏览器打开 https://github.com/settings/tokens?type=beta
#   2. Generate new token
#   3. Repository access: Only select ai-audit-skills
#   4. Contents: Read and write
#   5. Expiration: 7 days
#   6. 复制 token（只显示一次）

# 写入 Mac mini 的 netrc（避免明文存 URL）
cat > ~/.netrc <<EOF
machine github.com
login andrew-tao-li
password ghp_xxxxx_your_new_PAT_here
EOF
chmod 600 ~/.netrc

# 配置 git 用 netrc
git config --global credential.helper netrc

# 验证
git push origin main
```

### 5.2 日常拉取

```bash
# 每天手动或自动（可选 cron）拉取最新代码
cd ~/ai-audit-skills
git pull origin main
```

### 5.3 状态持久化（重要）

每次 `evolve.sh` 跑完会自动 commit 本地变更。要推到 GitHub：

```bash
# 自动推：把 push 加到 launchd
# 但 launchd 后台进程可能没 GitHub 认证
# 所以建议：手动定时拉 + 推

# 或加 cron job（macOS 不推荐用 cron，用 launchd 更稳）
```

---

## 6. 日常维护

| 频率 | 任务 | 时间 |
|---|---|---|
| 每天 | 看企业微信通知 | 30 秒 |
| 每周 | 看 state.json 趋势 + proposals | 5 分钟 |
| 每月 | review + 决定是否推进 v0.3 | 2 小时 |
| 每季度 | 找真实审计师 + 收集反馈 | 半天 |

---

## 7. 故障排查

### 7.1 API key 失效

**症状**：邮件/微信里说 `auth_error` 或 `rate_limited`

**解决**：
```bash
# 检查 key 是否过期
echo $MINIMAX_API_KEY | head -c 20

# 重新设（向 MiniMax 续费/换 key）
# 编辑 ~/.zshrc
echo 'export MINIMAX_API_KEY="新的 sk-cp-..."' >> ~/.zshrc
source ~/.zshrc

# 更新 launchd plist 里的 key
/usr/libexec/PlistBuddy -c "Set :EnvironmentVariables:MINIMAX_API_KEY '新的 key'" \
  ~/Library/LaunchAgents/com.audit.skill.box.plist
launchctl unload ~/Library/LaunchAgents/com.audit.skill.box.plist
launchctl load ~/Library/LaunchAgents/com.audit.skill.box.plist
```

### 7.2 通知没收到

**症状**：evolve.sh 跑成功但没邮件/微信

**检查**：
```bash
# 看 evolution/log/notifications.log
tail -50 evolution/log/notifications.log

# 看系统 log
log show --predicate 'eventMessage contains "audit"' --info --last 1h
```

### 7.3 launchd 没跑

**症状**：每天 9:00 没看到新 log

**检查**：
```bash
# 看任务状态
launchctl list | grep audit

# 看 macOS system log
log show --predicate 'subsystem contains "launchd"' --info --last 24h | grep audit
```

---

## 8. 迁移检查清单

打印这份清单，照着做：

```
[ ] 1. macOS 系统版本检查（sw_vers）
[ ] 2. Python 3.10+ 检查（python3 --version）
[ ] 3. openpyxl 安装（pip3 install openpyxl）
[ ] 4. SSH key 生成并贴到 GitHub
[ ] 5. clone 项目（git clone）
[ ] 6. 跑 setup 脚本（./scripts/setup-mac-mini.sh）
[ ] 7. 配企业微信 Webhook（在群机器里添加）
[ ] 8. 验证 launchd（launchctl list | grep audit）
[ ] 9. 手动跑一次（./evolve.sh）
[ ] 10. 看通知到没到（企业微信/邮件）
[ ] 11. 等到第二天 9:00 看是否自动跑
[ ] 12. （可选）配 Mac mini 上 GitHub PAT 用于推回
```

完成所有项 = 迁移完成。
