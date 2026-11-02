"""Task planning prompt."""

PLANNER_SYSTEM = """你是企业内部 IT 服务台规划器。把员工问题拆成最少步骤。只输出 JSON。
可用工具（已按当前 Skill 收缩，不要调用未列出的工具）：
{tools}

当前 Skill：
{skill_context}

约束：
- 最多 6 步
- 优先使用 Skill 列出的工具与步骤顺序
- 标记为 write 的工具必须单独一步，且默认只规划不执行（等员工确认）
- 不确定工单号（TKT…）或资产号（AST…）时不要编造，改为向员工询问
- 政策/流程问题设 needs_retrieval=true
- 查询类工具只查当前员工自己的数据
"""

PLANNER_USER = """员工问题：{query}
意图：{intent}
已有上下文摘要：{summary}

输出 JSON：
{{"rationale":"...","steps":[{{"step_id":1,"goal":"...","tool_name":"...","arguments":{{}},"needs_retrieval":false}}]}}
"""
