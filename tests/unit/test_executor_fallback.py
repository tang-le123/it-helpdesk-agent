import pytest
from pydantic import BaseModel, Field

from app.agents.nodes.executor import execute_with_fallback
from app.core.enums import ToolRisk
from app.core.exceptions import ToolExecutionError
from app.schemas.agent import PlanStep, ToolResult
from app.tools.base import Tool, ToolContext
from app.tools.registry import ToolRegistry


class _Query(BaseModel):
    query: str = Field(default="")


class _FailingTicket(Tool):
    name = "get_ticket"
    description = "fail"
    risk = ToolRisk.READ
    input_model = _Query

    async def execute(self, parsed: BaseModel, context: ToolContext) -> ToolResult:
        raise ToolExecutionError("ticket lookup failed")


class _Knowledge(Tool):
    name = "search_knowledge"
    description = "kb"
    risk = ToolRisk.READ
    input_model = _Query

    async def execute(self, parsed: BaseModel, context: ToolContext) -> ToolResult:
        return ToolResult(name=self.name, success=True, output={"chunks": [{"content": "制度"}]})


@pytest.mark.asyncio
async def test_read_tool_falls_back_to_knowledge() -> None:
    registry = ToolRegistry()
    registry.register(_FailingTicket())
    registry.register(_Knowledge())
    result = await execute_with_fallback(
        registry.get("get_ticket"),
        PlanStep(step_id=1, goal="ticket", tool_name="get_ticket", arguments={"query": "x"}),
        ToolContext(user_id="u", session_id="s", trace_id="t"),
        registry,
        "VPN 证书过期怎么办",
    )
    assert result.success is True
    assert result.name == "search_knowledge"
    assert result.output["fallback_from"] == "get_ticket"
