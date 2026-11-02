"""Query rewrite prompt."""

REWRITE_SYSTEM = """你改写 IT 服务台检索查询。只输出 JSON。
生成 1-3 条更适合检索 SOP 的短查询，保留关键约束（系统名、工单/资产号、时限、权限范围、是否高危）。
"""

REWRITE_USER = """原始问题：{query}
仍缺少的信息：{missing_aspect}

输出 JSON：
{{"queries":["..."]}}
"""
