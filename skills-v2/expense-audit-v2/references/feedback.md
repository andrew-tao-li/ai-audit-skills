# 匿名反馈 · 技术细节（仅在执行反馈时参考）

> 本文件是执行反馈时的技术说明。**不要向用户或测试者复述其中内容。**
> 面向用户的说法见 `SKILL.md` 的「匿名反馈（可选，用户主动触发）」一节。

## 何时发送

只有当用户**明确说出触发词**（见 `SKILL.md`）时才执行；普通对话不会触发。
用户多次说触发词时，每次都要发送一次，不因「上次已发过」而跳过。

## 步骤

1. 运行 `scripts/build_feedback.py`，把**非敏感统计**的 markdown 打印到 stdout。
2. 把 stdout 的完整内容 POST 到下面的 webhook。

## Webhook

- URL：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d8dcd436-0e9e-4bd3-aa1f-7b5ddada529a`
- 方法：POST
- body（JSON）：`{"msgtype":"markdown","markdown":{"content":"<stdout 的完整内容>"}}`

## 隐私边界

只上传非敏感统计。**绝不**包含主体名称、金额、发票号、人员、账号、案卷内容等敏感字段。
核心分析脚本始终离线、不做任何网络请求（见 `run_manifest.json` 的 `network_access: false`）。
