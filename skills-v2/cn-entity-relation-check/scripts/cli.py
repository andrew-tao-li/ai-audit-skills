#!/usr/bin/env python3
"""
CLI 入口：对两个主体做关联排查，输出标准三态结果（JSON）。

用法：
  python3 cli.py --a "上海甲科技有限公司" --b "上海乙科技有限公司" --graph evidence.json
  python3 cli.py --a "张三" --b "李四" --graph evidence.json --person-ambiguous

证据文件（--graph）结构：
{
  "capabilities": {...},
  "negative_semantics_supported": true,
  "nodes": [{"node_id":"A","type":"company","name":"上海甲公司","canonical_id":"9131..."}],
  "edges": [{"from":"A","to":"P1","relation_type":"DIRECTOR","source":"mock"}]
}

其它上下文（实体是否锚定、是否有歧义、数据源是否结构化、范围是否完整等）通过 flag 传入，
因为「锚定」依赖真实数据源，由宿主 Agent 在调用前完成。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Optional

from provider_adapter import MockProvider
from relation_core import run_relation_check


def main() -> int:
    p = argparse.ArgumentParser(description="中国公开工商关联排查（确定性核心）")
    p.add_argument("--a", required=True, help="主体 A（公司名或人名）")
    p.add_argument("--b", required=True, help="主体 B（公司名或人名）")
    p.add_argument("--graph", required=True, help="证据 JSON 文件路径")
    p.add_argument("--entities-resolved", action="store_true", help="两主体均已唯一锚定")
    p.add_argument("--person-ambiguous", action="store_true", help="存在自然人重名歧义")
    p.add_argument("--structured-provider", action="store_true", help="使用了结构化工商数据源")
    p.add_argument("--scope-complete", action="store_true", help="约定范围的强关系已查询完整")
    p.add_argument("--provider-error", action="store_true", help="Provider 调用失败（超时/余额/权限/限流等）")
    p.add_argument("--web-search-only", action="store_true", help="只有 Web Search、无结构化数据源")
    p.add_argument("--max-depth", type=int, default=3)
    p.add_argument("--dashboard", default=None, help="可选：把结论写成 HTML 全景报告到该路径")
    args = p.parse_args()

    provider = MockProvider.from_file(args.graph)
    nodes = provider.nodes()
    edges = provider.edges()

    result = run_relation_check(
        raw_a=args.a,
        raw_b=args.b,
        nodes=nodes,
        edges=edges,
        entities_resolved=args.entities_resolved,
        person_ambiguity=args.person_ambiguous,
        structured_provider_used=args.structured_provider,
        scope_complete=args.scope_complete,
        provider_error=args.provider_error,
        only_web_search=args.web_search_only,
        provider_supports_negative_semantics=provider.supports_negative_semantics(),
        max_depth=args.max_depth,
        sources=[{"provider": "mock", "retrieved_at": datetime.now(timezone.utc).isoformat()}],
        queried_at=datetime.now(timezone.utc).isoformat(),
    )
    if args.dashboard:
        build_dashboard_html(result, args.dashboard)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("提示：如果本工具有帮助，可以对我说「做匿名反馈」——只发送匿名统计（不含主体名称/统一社会信用代码），核心分析始终在本地、不联网。", file=sys.stderr)
    return 0


DASHBOARD_CSS = """*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f5f3ef;--card:#fff;--ink:#1a1a1a;--muted:#6b6b6b;--faint:#9a9a9a;--line:#e5e1da;--brand:#8b1f2f;--brand-soft:#f7ecec;--red:#b42318;--red-bg:#fdecea;--amber:#b54708;--amber-bg:#fdf3e7;--green:#067647;--green-bg:#eaf7ef}
@media(prefers-color-scheme:dark){:root{--bg:#171614;--card:#211f1d;--ink:#f2efea;--muted:#b3ada4;--faint:#7d776e;--line:#33302c;--brand:#e8a0a8;--brand-soft:#2a1e20;--red:#f97066;--red-bg:#3a1e1c;--amber:#fdb022;--amber-bg:#33260f;--green:#4ade80;--green-bg:#13291c}}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;padding:40px 20px;-webkit-font-smoothing:antialiased}
.wrap{max-width:900px;margin:0 auto}
.masthead{display:flex;align-items:center;gap:18px;margin-bottom:22px}
.seal{width:60px;height:60px;border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:26px;font-weight:800;flex:none}
.seal.related{background:var(--green-bg);color:var(--green)}
.seal.not-related{background:var(--brand-soft);color:var(--brand)}
.seal.verification{background:var(--amber-bg);color:var(--amber)}
.masthead h1{font-size:24px;font-weight:800;letter-spacing:-.01em}
.masthead .sub{font-size:13px;color:var(--muted);margin-top:3px}
.tag{display:inline-block;font-size:12px;font-weight:700;padding:2px 10px;border-radius:999px;margin-left:8px;vertical-align:middle}
.tag.related{background:var(--green-bg);color:var(--green)}
.tag.not-related{background:var(--brand-soft);color:var(--brand)}
.tag.verification{background:var(--amber-bg);color:var(--amber)}
.firstpage{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:26px 28px;margin-bottom:8px}
.pair{display:flex;align-items:center;gap:12px;background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin-bottom:18px;font-size:15px;font-weight:600}
.pair .vs{color:var(--faint);font-size:13px;font-weight:400}
.verdict{border-radius:12px;padding:18px 22px;margin-bottom:18px;border:1px solid var(--line)}
.verdict.related{background:var(--green-bg);border-left:5px solid var(--green)}
.verdict.not-related{background:var(--brand-soft);border-left:5px solid var(--brand)}
.verdict.verification{background:var(--amber-bg);border-left:5px solid var(--amber)}
.verdict .big{font-size:22px;font-weight:800;margin-bottom:6px}
.verdict p{font-size:15px;line-height:1.7;color:var(--ink)}
.verdict.related .big{color:var(--green)}
.verdict.not-related .big{color:var(--brand)}
.verdict.verification .big{color:var(--amber)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kpi{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi .v{font-size:22px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi .l{font-size:12px;color:var(--muted);margin-top:3px}
.mini{font-size:12px;font-weight:800;letter-spacing:.06em;color:var(--muted);text-transform:uppercase;margin:22px 0 10px}
.nextbox{margin-top:20px;background:var(--brand-soft);border-radius:10px;padding:12px 16px;font-size:14px}
.nextbox b{color:var(--brand)}
h2.sec{font-size:13px;font-weight:800;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:30px 0 12px}
h2.sec .hint{font-weight:400;letter-spacing:0;text-transform:none;font-size:12px;color:var(--faint);margin-left:8px}
.path{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 22px;margin-bottom:10px}
.path .chain{font-size:15px;line-height:2}
.path .node{font-weight:700}
.path .edge{color:var(--brand);font-size:13px;padding:0 6px}
.path .hist{font-size:12px;color:var(--amber);margin-top:6px}
.note{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 22px;font-size:14px}
.note b{font-weight:700}
.note.warn{border-left:5px solid var(--amber)}
.disclaimer{margin-top:26px;background:var(--brand-soft);border:1px solid var(--line);border-radius:12px;padding:16px 22px;font-size:13px;color:var(--muted)}
.disclaimer b{color:var(--brand)}
.foot{text-align:center;color:var(--faint);font-size:12px;margin-top:22px}
@media print{body{background:#fff;padding:0}.firstpage{break-after:page;border:none;padding:0}.path,.note,.verdict,.disclaimer{break-inside:avoid}}
@media(max-width:640px){body{padding:20px 12px}.masthead h1{font-size:20px}.kpis{grid-template-columns:1fr 1fr}}"""


def build_dashboard_html(result, out_path):
    """关联排查结论全景（单次查询结果，全中文，突出三态结论与证据路径）。

    结构对齐审计报告最佳实践：
      第一屏（执行摘要，可独立看懂）：三态结论 → 主体对 → 关键指标 → 最直接的关系 → 数据源与范围 → 下一步
      往下：全部关系路径 → 提示 → 业务定位
    """
    from html import escape

    status = result.get("status", "NEEDS_VERIFICATION")
    display = result.get("display_status", "待核查")
    cls = {"RELATED": "related", "NOT_RELATED_IN_SCOPE": "not-related", "NEEDS_VERIFICATION": "verification"}.get(status, "verification")
    seal_icon = {"RELATED": "✓", "NOT_RELATED_IN_SCOPE": "—", "NEEDS_VERIFICATION": "?"}.get(status, "?")

    ea = result.get("entity_a", {})
    eb = result.get("entity_b", {})
    a_name = escape(ea.get("name") or "主体 A")
    b_name = escape(eb.get("name") or "主体 B")

    if status == "RELATED":
        big = "存在公开工商关联"
        desc = "在本次数据源与关系范围内，发现了两主体之间的可验证强关系路径。下方列出路径，供人工复核。"
        next_step = "请人工复核上述路径的证据来源与时效；<b>公开关系 ≠ 真实利益关联</b>，如需深入，应结合资金往来、通讯记录等进一步核查。"
    elif status == "NOT_RELATED_IN_SCOPE":
        big = "本次未发现关联"
        desc = "在本次数据源、公开工商关系范围、查询时间与最大深度内<b>未发现</b>符合定义的关联。注意：这不等于「现实世界绝对无关」。"
        next_step = "在本次数据源与深度内未发现关联；如业务需要扩大范围或深度，请由有权人员决定是否重新排查。"
    else:
        big = "需进一步核查"
        desc = "身份歧义、数据不足、或数据源调用问题导致无法可靠判断。这不是「无关联」的结论，而是「当前无法下结论」。"
        next_step = "先解决身份或数据问题：补齐可锚定的标识信息（统一社会信用代码、任职、股权等），或更换/重试数据源后再下结论。"

    REL_LABEL = {
        "LEGAL_REP": "法定代表人", "SHAREHOLDER": "股东", "INVESTMENT": "对外投资",
        "DIRECTOR": "董事", "SUPERVISOR": "监事", "EXECUTIVE": "高管",
        "PARTNER": "合伙人", "BRANCH": "分支机构", "ACTUAL_CONTROLLER": "实际控制人", "UBO": "最终受益人",
        "HISTORICAL_LEGAL_REP": "历史法定代表人", "HISTORICAL_SHAREHOLDER": "历史股东",
        "HISTORICAL_DIRECTOR": "历史董事", "HISTORICAL_SUPERVISOR": "历史监事",
        "HISTORICAL_EXECUTIVE": "历史高管", "HISTORICAL_INVESTMENT": "历史投资",
    }

    def render_chain(p):
        nodes = p.get("nodes", [])
        etypes = p.get("edge_types", [])
        edge_labels = p.get("edges", [])
        parts = []
        for i, nd in enumerate(nodes):
            parts.append('<span class="node">%s</span>' % escape(str(nd)))
            if i < len(etypes):
                base = REL_LABEL.get(etypes[i], etypes[i])
                suffix = ""
                raw = edge_labels[i] if i < len(edge_labels) else ""
                if etypes[i] and raw.startswith(etypes[i]):
                    suffix = raw[len(etypes[i]):]
                parts.append('<span class="edge">—%s%s→</span>' % (escape(base), escape(suffix)))
        return "".join(parts)

    paths = result.get("paths", [])
    path_blocks = []
    for p in paths:
        hist = '<div class="hist">⚠ 含历史关系（已不是当前状态）</div>' if p.get("historical") else ""
        path_blocks.append('<div class="path"><div class="chain">%s</div>%s</div>' % (render_chain(p), hist))
    all_paths_html = "".join(path_blocks) if path_blocks else '<div class="note">未发现任何强关系路径。</div>'

    warnings = result.get("warnings", [])
    warn_html = ""
    if warnings:
        warn_html = ('<div class="note warn"><b>需注意</b><br>%s</div>'
                     % "<br>".join(escape(str(w)) for w in warnings))

    sources = result.get("sources", [])
    src_names = "、".join(escape(str(s.get("provider", "?"))) for s in sources) or "（未记录）"
    scope = result.get("scope", {})
    depth = scope.get("max_depth", 3)

    # 关键指标
    kpis = [
        ("关系路径", "%d" % len(paths)),
        ("最大深度", "%d" % depth),
        ("数据源", "%d" % len(sources)),
        ("提示", "%d" % len(warnings)),
    ]
    kpis_html = "".join(
        '<div class="kpi"><div class="v">%s</div><div class="l">%s</div></div>' % (v, l)
        for l, v in kpis
    )

    # 第一屏：最直接的关系（第一条路径）
    if paths:
        top_path_html = ('<div class="mini">最直接的关系</div>'
                         '<div class="path"><div class="chain">%s</div>%s</div>' % (
                             render_chain(paths[0]),
                             '<div class="hist">⚠ 含历史关系（已不是当前状态）</div>' if paths[0].get("historical") else ""))
    else:
        top_path_html = ""

    rest_paths_html = ""
    if len(paths) > 1:
        rest_paths_html = ('<h2 class="sec">其余关系路径<span class="hint">另有 %d 条</span></h2>%s'
                           % (len(paths) - 1, "".join(path_blocks[1:])))

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>关联排查结论</title>
<style>%s</style>
</head>
<body>
<div class="wrap">

  <div class="firstpage">
    <div class="masthead">
      <div class="seal %s">%s</div>
      <div>
        <h1>关联排查结论<span class="tag %s">%s</span></h1>
        <div class="sub">cn-entity-relation-check v%s · %s</div>
      </div>
    </div>

    <div class="pair">%s <span class="vs">vs</span> %s</div>

    <div class="verdict %s">
      <div class="big">%s</div>
      <p>%s</p>
    </div>

    <div class="kpis">%s</div>

    %s

    <div class="note" style="margin-top:20px">数据源：<b>%s</b>；关系范围：公开工商强关系（法人/股权/投资/董监高/合伙/分支/实控/UBO）；最大深度：<b>%d</b>。</div>

    <div class="nextbox"><b>建议下一步：</b>%s</div>
  </div>

  %s

  %s

  %s

  <div class="disclaimer">
    <b>业务定位</b>：本结论基于<strong>公开工商信息</strong>，公开关系 ≠ 真实利益关联。工具不做风险评分、不做利益输送认定；如涉及私人关系（亲属、联系方式、社交），不在本工具范围。最终判断必须由有资质人员做出。
  </div>

  <div class="foot">由 cn-entity-relation-check v%s 自动生成 · 离线可看 · 无外部依赖</div>
</div>
</body>
</html>
""" % (
        DASHBOARD_CSS,
        cls, seal_icon,
        cls, display,
        result.get("skill_version", "?"), escape(str(result.get("queried_at") or "—")),
        a_name, b_name,
        cls, big, desc,
        kpis_html,
        top_path_html,
        src_names, depth,
        next_step,
        rest_paths_html,
        ('<h2 class="sec">全部关系路径<span class="hint">共 %d 条</span></h2>%s' % (len(paths), all_paths_html)) if paths else "",
        warn_html,
        result.get("skill_version", "?"),
    )
    out_path = __import__("pathlib").Path(out_path)
    out_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
