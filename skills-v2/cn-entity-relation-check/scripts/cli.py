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
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
