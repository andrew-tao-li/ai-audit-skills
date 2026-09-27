# 关联排查（cn-entity-relation-check）

输入两个公司或自然人，快速判断中国公开工商信息中是否存在可验证关联。

结果只有三种：

- ✅ 关联
- ⚪ 不关联
- 🟡 待核查

示例：

> 帮我查一下 A 公司和 B 公司有没有关联。
> 张三和上海 XX 公司有没有关联。
> 李四和王五工商上有没有关联。

## 它做什么 / 不做什么

- **做**：实体锚定、自然人重名消歧、强弱证据分层、三态判定、可追溯关系路径。
- **不做**：风险评分、舞弊/利益输送认定、私人背景调查（家庭、私人联系方式、社交）。

## 关键保证

- 「没搜到」绝不等于「不关联」。
- API 失败 / 超时 / 余额不足 / 分页未完成 / 身份歧义 → 一律「待核查」。
- 自然人姓名不是唯一标识，必须有 person_id 或「姓名+任职企业」锚点。
- V0.1 只有工商强关系（法人/股权/投资/董监高/合伙/分支/实控/UBO 及历史）能独立「关联」。

## 数据源

不绑定单一数据商。按「能力」找工具（企查查/天眼查/启信宝/官方/Web），已授权结构化数据优先。无结构化数据时走 Web fallback——Web 只能证明「有」，不能证明「无」。

不内置任何 API Key。BYOK：`QCC_API_KEY` / `TIANYANCHA_TOKEN` / `QIXINBAO_API_KEY`。

## 运行确定性核心（离线）

```bash
python3 scripts/cli.py --a "上海甲科技有限公司" --b "上海乙科技有限公司" \
  --graph examples/input/company_company_related.json \
  --entities-resolved --structured-provider --scope-complete
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 目录

- `SKILL.md` — 核心协议
- `references/` — 范围定义、三态协议、自然人消歧、证据等级、输出 schema、隐私、Provider、故障恢复
- `scripts/` — 确定性判定核心（entity_normalizer / evidence_normalizer / path_finder / result_validator / relation_core / provider_adapter / cli）
- `assets/` — 配置示例 + 结果 JSON schema
- `examples/` — 三个演示场景（全虚构数据）
- `tests/` — 单元测试
