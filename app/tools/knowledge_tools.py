"""Knowledge tools: SOP search and human escalation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.retrieval.hybrid import HybridRetriever
from app.schemas.agent import ToolResult
from app.tools.base import Tool, ToolContext


class KnowledgeSearchInput(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="SOP 检索问句，如「VPN 怎么申请」；不要填工单号",
    )


class EscalateInput(BaseModel):
    reason: str = Field(
        min_length=1,
        max_length=200,
        description="转人工原因摘要，如「用户要求值班经理介入」；不要填工单号代替原因",
    )


class SearchKnowledgeTool(Tool):
    name = "search_knowledge"
    description = (
        "检索 IT 服务台 SOP 与制度文档片段，覆盖账号、设备、网络、软件、安全、流程六类。只读。"
        "何时用：问流程、政策、时效、材料、红线，如「VPN 怎么申请」「离职设备什么时候归还」"
        "「客户数据能不能发给外部模型」。"
        "何时不用：查某张工单用 get_ticket；查某台设备用 get_asset；要执行申请或建单用对应写工具。"
        "参数 query：1–200 字检索问句，如「外包账号有效期多久」，不要填 TKT10001。"
        "返回 chunks[{chunk_id,title,content}]，只作制度依据，不能当成某位员工的真实记录。"
    )
    risk = ToolRisk.READ
    input_model = KnowledgeSearchInput

    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    async def execute(self, parsed: KnowledgeSearchInput, context: ToolContext) -> ToolResult:
        chunks = await self._retriever.retrieve(parsed.query, top_k=4)
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "chunks": [
                    {"chunk_id": c.chunk_id, "title": c.title, "content": c.content[:400]}
                    for c in chunks
                ]
            },
        )


class EscalateToHumanTool(Tool):
    name = "escalate_to_human"
    description = (
        "转二线 IT 工程师或人工，并在队列中登记原因。"
        "何时用：用户明确要人工/找工程师；问题超出 SOP；查询与写工具都无法解决；投诉升级。"
        "何时不用：能查工单、查资产或检索 SOP 解决时不要转；不要用它代替建单。"
        "参数 reason：1–200 字概括为何转人工，如「用户要求主管审核权限申请」。"
        "返回 {ticket_id, queue:human, reason} 表示已排队，不是已经接通人工。"
    )
    risk = ToolRisk.EXTERNAL
    input_model = EscalateInput

    async def execute(self, parsed: EscalateInput, context: ToolContext) -> ToolResult:
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "ticket_id": f"esc_{context.session_id[:10]}",
                "queue": "human",
                "reason": parsed.reason,
            },
        )
