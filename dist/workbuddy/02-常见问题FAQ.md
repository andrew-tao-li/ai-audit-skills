# 常见问题 FAQ — 腾讯 WorkBuddy

> 写给第一次用审计 Skill 的用户。如果下面的回答解决不了你的问题，填写 [`03-反馈表.md`](03-反馈表.md) 发回给我们。

---

## Q1：上传 ZIP 后一直卡在"安全检测中"怎么办？

**症状**：上传 `expense-audit-0.1.1.zip` 后，WorkBuddy 进度条停在"安全检测"步骤，超过 1 分钟没动静。

**原因**：WorkBuddy 5.5.6 在 2026-09-16 实测时遇到检测服务超时。这不是 ZIP 包的问题，是 WorkBuddy 云端检测服务的状态。

**解决**：
1. 再等 30 秒
2. 如果仍无响应，看界面是否弹出"是否仍要继续"或"跳过本次检测"
3. 选择"**仍要继续**"

**预防**：实测发现首次安装都会触发这个情况，三个 ZIP 都要"等 + 跳过"一次。

---

## Q2：WorkBuddy 不认我的 skill，提示"找不到"或"未加载"

**逐项检查**：
- [ ] ZIP 文件完整下载了吗？看文件大小，应该大于 20 KB
- [ ] ZIP 是从 `zips/` 目录里选的吗？不要解压直接上传
- [ ] ZIP 是最新版本吗？看文件名末尾的版本号（0.1.1 或 0.1.2）
- [ ] 是否跟宿主版本兼容？建议 WorkBuddy 5.5.6 或更新
- [ ] 上传时是否被安全检测拦截？回到 Q1
- [ ] 是否要重启宿主？少数版本需要重启后才会加载

**重新安装**：
1. 删除已安装的 skill
2. 重启 WorkBuddy
3. 重新上传 ZIP

---

## Q3：跑出来 0 个 finding，是数据太干净还是 skill 出了问题？

**两种情况**：

| 情况 | 怎么判断 | 怎么办 |
|---|---|---|
| 数据真的干净 | `data_quality.md` 显示有效记录数 > 0，bad_rows = 0 | 放心使用，0 finding 是好事 |
| Skill 没跑全 | `run_manifest.json` 里有 `skipped_rules` 列表 | 把 skipped_rules 内容贴给我们 |

**强制检查清单**：
- [ ] `clean_expenses.csv` 行数 = 你的 CSV 行数 - 1（表头）
- [ ] `bad_rows.csv` 行数 = 解析失败的记录数
- [ ] `run_manifest.json` 里 `network_access: false`

如果 `clean_expenses.csv` 是空的或行数不对，说明数据没读进来，回到 Q2 检查 skill 安装。

---

## Q4：finding 数量爆炸（>100 条），是数据问题还是阈值问题？

**症状**：`summary.md` 显示 finding 几百甚至上千条。

**两个常见原因**：
1. **数据本身有问题**（如同一笔报销被多次导入）
   - 看 `data_quality.md` 的"字段空值率"和"重复业务主键"
   - 如果 `expense_id` 有重复，先去重
2. **阈值过严**
   - 默认 `near_duplicate_amount_tolerance: 0.02`（2%）可能在你的数据上太严
   - 调整方法：让 WorkBuddy "把 near_duplicate_amount_tolerance 改成 0.05 重新跑"

**快速缩小范围**：
- 看 `summary.md` 的 finding 类型分布
- 如果某个类型占大多数（如 weekend-signal 占 60%），这个规则可能对你的场景不适用
- 调整方法：让 WorkBuddy "把 policy 里的 weekend_check 设为 false 重新跑"

---

## Q5：XLSX 文件读不了，提示"需要 openpyxl"

**原因**：脚本读 XLSX 需要 Python 的 openpyxl 包，宿主不一定预装。

**两种选择**：
1. **推荐：把 XLSX 另存为 CSV**
   - Excel 打开 → 文件 → 另存为 → 选 "CSV UTF-8 (逗号分隔)"
2. **不推荐：自己装 openpyxl**
   - 需要打开终端（macOS 启动"终端"应用）
   - 输入：`pip3 install openpyxl`
   - 然后重启 WorkBuddy

**怎么选**：如果你不懂命令行，**直接转 CSV** 是最快的方式。CSV 跟 XLSX 在审计分析上没区别。

---

## Q6：路径含空格或中文，提示"找不到文件"

**症状**：报错"FileNotFoundError"或"No such file or directory"，但你确定文件存在。

**原因**：macOS / Windows 默认目录常含空格或中文（如 `~/Desktop/腾讯文件/`）。

**解决**：
- 桌面 / 文档目录 → 改名成英文（如 `~/Desktop/audit-2026/`）
- 文件本身 → 改名成英文或拼音
- 命令行调用 → 用双引号包路径（但普通用户不需要用命令行）

**最简单的方法**：把所有文件都放到一个纯英文路径下，比如 `~/Desktop/audit-test/`，再上传。

---

## Q7：想用 investigation-assistant 但 WorkBuddy 拒绝运行

**原因**：调查类 skill 有最严格的"权限 gate"。脚本会读取 `scope.json` 里的 `authorization_confirmed` 字段，**必须是 `true`** 才会跑。

**为什么这样设计**：调查工作涉及员工个人信息、举报内容、监控记录，必须由公司合规部门正式授权后才开始处理。脚本不能在没有授权的情况下读取任何材料。

**怎么办**：
1. **必须**先获得合规部门、纪检或董事会审计委员会的书面授权
2. 在 `scope.json` 里填 `authorization_confirmed: true`
3. 同时填 `authorization_reference: "授权文件编号"`
4. 在 `persons_in_scope` 里**只列**经过审批可纳入调查的人员
5. 在 `date_range` 里**只列**调查期间

**不要做**：
- 自行设置 `authorization_confirmed: true`（除非真的获得了授权）
- 把所有人、所有期间都放进去
- 用 skill 处理未授权的举报信或私人聊天记录

如果不确定，请联系你的合规部门，不要"先试试看"。

---

## Q8：finding 是什么意思？high 和 medium 哪个更严重？

**finding** = 一条"需要审计师关注的线索"，不是"已证实的问题"。

**两个独立维度**：

| 维度 | 含义 | 影响 |
|---|---|---|
| `risk_priority`（优先级） | 这条线索**多值得优先看** | high > medium > low > critical |
| `evidence_strength`（证据强度） | 证据本身**多可信** | strong > moderate > weak |

**两个维度故意分开**。比如：
- 一笔 50 万的异常付款（high 优先级），但只有口头说法（weak 证据）→ 仍需复核，但**不能据此处罚**
- 一笔 5000 元的重复发票（medium 优先级），但有完整系统记录（strong 证据）→ 复核价值高

**审计师实际工作的重点**：
- **第一档**：high + strong → 必须立刻复核
- **第二档**：high + moderate / medium + strong → 优先复核
- **第三档**：其他 → 按工作量排序

**脚本不做的**：
- 不写"已证实舞弊""虚假报销""拒付"等结论
- 不算"舞弊金额""损失金额"
- 不触发任何处置动作

最终判断仍由审计师做出。

---

## Q9：哪些数据**不要**上传？

**即使 skill 脚本完全离线运行（不主动联网），WorkBuddy 仍可能把你的输入上传到云端大模型做推理。**

**可以上传**：
- 包内合成样例（完全虚构）
- 已脱敏的演示数据（如把"张三"改为"员工A"，把真实金额改为"¥xxxx"）
- 公开新闻里提到的事件（已公开的不算敏感）

**不要上传**：
- ❌ 真实员工姓名、身份证号、银行账号、电话
- ❌ 真实供应商名称、税号、对公账户、合同金额
- ❌ 真实的举报信、聊天记录、邮件、监控记录
- ❌ 受合规保密、未公开的数据
- ❌ 涉及个人隐私、未脱敏的医疗或财务数据

**第一次测试只上传包内合成样例**。当你确认流程能跑通后，再考虑用自己的数据，并先咨询你的合规部门是否允许。

---

## Q10：我应该先试哪个 skill？

**推荐顺序**：

1. **先试 expense-audit**——最成熟、最简单、输入只需一个 CSV
2. **再试 procurement-fraud**——稍复杂，需要 5 个 CSV
3. **最后试 investigation-assistant**——最敏感，必须有合规授权

每个 skill 都先用包内合成样例跑通，再换自己的数据。
