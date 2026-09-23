# 隐私与合规（privacy-and-compliance）

## 数据最小化

第一版只处理合法公开的企业工商关系。能不用个人敏感数据就不用。

不主动收集：身份证、私人电话、家庭地址、银行账号、家庭成员、私人社交账号。

## 查询最小化

用户问「A 和 B 有没有关系」，不要顺便查诉讼、舆情、手机号、社交媒体、家庭、消费行为。只查完成关系判定必需的数据。

## 密钥安全

- 严禁在 SKILL.md / README.md / Git / 测试 fixture / 日志 / 最终聊天结果中内置作者 API Key。
- BYOK：`QCC_API_KEY` / `TIANYANCHA_TOKEN` / `QIXINBAO_API_KEY` 从宿主 Secret Store 或环境变量读取。
- 发布前自动搜索 `API_KEY`、`token`、`secret`、`Authorization`、`cookie`、`password`，确认无真实 Key、无真实身份证、无真实银行卡、测试数据全部虚构。

## 合规

- 不绕过验证码、登录、Cookie、付费 API、反爬限制。
- 有正式 MCP / API 时优先正式接口。
- 真实调查建议先取得合规授权。
