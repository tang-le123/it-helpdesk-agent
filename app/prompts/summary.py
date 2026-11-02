"""Conversation summarisation prompt."""

SUMMARY_SYSTEM = """把 IT 服务台对话压成简短摘要，保留：员工诉求、工单号/资产号、已查状态、待确认操作。只输出 JSON。"""

SUMMARY_USER = """历史：
{history}

输出 JSON：
{{"summary":"..."}}
"""
