"""Tool registry construction."""

from app.retrieval.hybrid import HybridRetriever
from app.tools.access_tools import RequestAccessTool, ResetPasswordTool
from app.tools.asset_tools import GetAssetTool, ListMyAssetsTool
from app.tools.base import Tool
from app.tools.knowledge_tools import EscalateToHumanTool, SearchKnowledgeTool
from app.tools.registry import ToolRegistry
from app.tools.software_tools import RequestSoftwareTool
from app.tools.ticket_tools import CreateTicketTool, GetTicketTool, ListMyTicketsTool


def build_tool_registry(retriever: HybridRetriever) -> ToolRegistry:
    """Process-scoped registry. DB-backed tools resolve the request session lazily."""
    registry = ToolRegistry()
    # Explicit annotation: the concrete classes mix RepositoryBackedTool with Tool,
    # so an unannotated list literal widens to `object` and fails type checking.
    tools: list[Tool] = [
        GetTicketTool(),
        ListMyTicketsTool(),
        GetAssetTool(),
        ListMyAssetsTool(),
        CreateTicketTool(),
        RequestAccessTool(),
        ResetPasswordTool(),
        RequestSoftwareTool(),
        SearchKnowledgeTool(retriever),
        EscalateToHumanTool(),
    ]
    for tool in tools:
        registry.register(tool)
    return registry
