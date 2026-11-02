import pytest

from app.mcp.adapter import merge_mcp_tools
from app.mcp.runtime import LOCAL_CATALOG, call_mcp_tool
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_local_mcp_executes() -> None:
    output = await call_mcp_tool(
        name="mcp_service_hours",
        arguments={},
        transport="local",
    )
    assert output["weekday"] == "09:00-19:00"
    assert output["night_p1_only"] is True
    assert output["source"] == "mcp_local"


@pytest.mark.asyncio
async def test_mcp_proxy_is_function_calling_tool() -> None:
    registry = ToolRegistry()
    merge_mcp_tools(registry, list(LOCAL_CATALOG))
    tool = registry.get("mcp_change_calendar")
    schema = tool.openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "mcp_change_calendar"
    result = await tool.run({}, ToolContext(user_id="u", session_id="s", trace_id="t"))
    assert result.success is True
    assert result.output["next_window"] == "本周六 02:00-06:00"
