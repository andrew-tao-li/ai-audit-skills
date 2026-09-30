"""SkillHub / ClawHub 上架的**单一配置源**：展示名 / 简介 / 标签 / 分类 / 详细介绍。

谁在用：
  - scripts/build-skillhub.py       → 生成 dist-v2/skillhub/<skill>/ 的 frontmatter
  - scripts/publish-skillhub.py     → 发布时带 category / subCategories
  - scripts/gen-skillhub-listing.py → 生成 docs/skillhub-listing.md
"""

LICENSE = "MIT-0"
HOMEPAGE = "https://github.com/andrew-tao-li/ai-audit-skills"

SKILLS = {
    "expense-audit-v2": {
        # ClawHub 有独立的分类体系（与 SkillHub 不同），最多 3 分类 / 5 主题
        "clawhub_categories": ['finance', 'security'],
        "clawhub_topics": ['audit', 'expense', 'reimbursement', 'fraud-detection', 'offline'],
        "display_name": '费用报销审计',
        "tags": ['审计', '费用审计', '报销', '发票', '差旅', '反舞弊', '财税处理', '风险风控'],
        "slug": "andrew-tao-li-expense-audit",
        "category": "professional",
        "sub_categories": ["pro-tax-accounting", "pro-risk-control"],
        "summary": "扫描费用/报销/发票/差旅台账，识别重复报销、超制度上限、拆分报销、自审自批、发票跨人复用等异常，输出可追溯证据与经理可读报告。辅助分析，不替代专业审计判断。",
        "intro": "给审计/财务人员用的**费用报销异常扫描**工具。喂进一张费用台账（CSV/XLSX），它做两件事：\n① **数据体检**——分离坏行、标准化字段、给出数据质量报告；\n② **确定性规则扫描**——重复发票号、同员工同日同金额、超制度上限、拆分报销、统计离群、自审自批、发票跨人复用、提交早于消费、未来日期、缺费用类型、发票连号/格式异常、大额低层级审批、时空冲突、跨期入账、高频小额等。\n\n产出：**给经理看的 HTML 全景报告**（第一页就是结论：几条高风险、涉及多少钱、先看哪三条）、`summary.md`、`findings.csv`、`evidence.jsonl`（每条线索都能追回源行）。\n\n**边界**：只做\"数据之间对得上\"的核对，**不判断业务是否真实发生**（例：一张合规的客情费发票，无法判断当时是否真的在宴请客户）。未发现问题 ≠ 没有问题；最终结论必须由有资质的审计师做出。\n\n**隐私**：全程离线，不联网、不上传、不需要任何 API Key。",
    },
    "procurement-fraud-v2": {
        # ClawHub 有独立的分类体系（与 SkillHub 不同），最多 3 分类 / 5 主题
        "clawhub_categories": ['security', 'finance'],
        "clawhub_topics": ['audit', 'procurement', 'fraud-detection', 'vendor', 'offline'],
        "display_name": '采购舞弊红旗筛查',
        "tags": ['审计', '采购', '反舞弊', '供应商', '招投标', '价格异常', '风险风控'],
        "slug": "andrew-tao-li-procurement-fraud",
        "category": "professional",
        "sub_categories": ["pro-risk-control", "pro-tax-accounting"],
        "summary": "对供应商主数据、采购订单、付款、员工与投标文本做舞弊红旗筛查：共享账户、价格离群、拆单、流程倒置、投标文本雷同等。仅输出复核线索，不做舞弊认定。",
        "intro": "给审计/采购/合规人员用的**采购红旗筛查**工具。输入供应商主数据、采购订单、付款、员工与投标文本（CSV/XLSX），输出可追溯的红旗清单。\n\n覆盖：供应商间共享银行账号/电话/邮箱/地址/法人、**员工—供应商**共享属性（利益冲突红线）、peer-group 价格离群、拆单采购、付款早于下单、收货早于审批、下单早于审批、超额付款、新成立供应商接大单、采购员—供应商集中度、投标文本字符级 TF-IDF 相似度、报价子簇异常等。\n\n产出：HTML 全景报告（含**调查移交建议**）、`findings.csv`、`relationship_graph.json`（供应商关系图）、`investigation_handoff.json`。\n\n**边界**：共享账号、价格离群、流程异常、文本雷同都只是**复核线索**，不能单独或自动证明串标、利益输送或舞弊。未发现问题 ≠ 没有问题；最终结论必须由有资质人员做出。\n\n**隐私**：全程离线，不联网、不上传、不需要任何 API Key。",
    },
    "investigation-assistant-v2": {
        # ClawHub 有独立的分类体系（与 SkillHub 不同），最多 3 分类 / 5 主题
        "clawhub_categories": ['security', 'knowledge'],
        "clawhub_topics": ['audit', 'investigation', 'evidence', 'compliance', 'offline'],
        "display_name": '授权内调查材料整理',
        "tags": ['审计', '内部调查', '证据链', '内控', '合规', '举报处理', '法律合规', '风险风控'],
        "slug": "andrew-tao-li-investigation-assistant",
        "category": "professional",
        "sub_categories": ["pro-legal", "pro-risk-control"],
        "summary": "在已获授权、范围明确的前提下，把举报、邮件、消息与日志整理为可追溯调查工作空间：证据清单与哈希、时间线、证据矩阵、反证、访谈计划。不做责任认定。",
        "intro": "给内部调查/内审/合规人员用的**调查材料整理**工具。**必须先取得显式授权**（授权文号、涉及人员、时间范围、允许来源），否则拒绝读取内容——这是硬门槛。\n\n在授权范围内：登记原始文件并计算 SHA-256、生成只读副本与保管链、抽取时间线（时区感知）、建立实体索引与关系、生成「事项 × 证据」矩阵（同时保留**支持证据、反证、替代解释、缺失证据**）、假设登记、访谈计划与案卷模板。越界数据单独隔离。\n\n产出：HTML 全景报告（授权范围与待验证事项一屏可见）、`timeline.csv`、`evidence_matrix.csv`、`hypothesis_register.csv`、`interview_plan.csv`、`chain_of_custody.jsonl`。\n\n**边界**：本工具只做**证据整理**，不做责任认定。用户指控与关键词命中均为待验证线索，不是事实。未命中不代表事项未发生；最终判断必须由有资质人员做出。\n\n**隐私**：全程离线，不联网、不上传、不需要任何 API Key。",
    },
    "cn-entity-relation-check": {
        # ClawHub 有独立的分类体系（与 SkillHub 不同），最多 3 分类 / 5 主题
        "clawhub_categories": ['security', 'research'],
        "clawhub_topics": ['audit', 'due-diligence', 'related-party', 'china', 'offline'],
        "display_name": '中国工商关联排查',
        "tags": ['审计', '关联方', '工商信息', '尽职调查', '实际控制人', '利益冲突', '风险风控'],
        "slug": "andrew-tao-li-cn-entity-relation",
        "category": "professional",
        "sub_categories": ["pro-legal", "pro-risk-control"],
        "summary": "核查两个主体（公司/自然人）在中国公开工商信息中是否存在可验证关联，输出「关联 / 不关联 / 待核查」三态结论。公开关系 ≠ 真实利益关联。",
        "intro": "给审计/尽调/合规人员用的**关联方排查**工具，回答一个问题：**这两个主体有没有可验证的公开工商关联？**\n\n支持公司—公司、公司—自然人、自然人—自然人三类组合。基于公开工商**强关系**（法人、股东、对外投资、董监高、合伙人、分支机构、实际控制人、最终受益人，含历史），做最大深度 3 的路径查找，并输出三态结论：\n- **关联**：给出可复核的关系路径（如「甲公司 —法定代表人→ 张三 —股东35%→ 乙公司」）；\n- **不关联**：在本次数据源、关系范围、时间与深度内未发现——**这不等于\"现实世界绝对无关\"**；\n- **待核查**：身份歧义、数据不足或数据源问题导致无法可靠判断——**这不是\"无关联\"，而是\"当前无法下结论\"**。\n\n自然人重名会做消歧；强/弱证据分层（同电话、同地址等弱线索**不能单独给出\"关联\"**）。\n\n**边界**：基于公开工商信息，**公开关系 ≠ 真实利益关联**；工具不做风险评分、不做利益输送认定；亲属、私人联系方式、社交关系不在范围内。\n\n**隐私**：决策核心离线；如接入结构化工商数据源，需你自备 API Key（BYOK），**本项目不内置任何 Key**。",
    },
}
