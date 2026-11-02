"""Local and remote MCP backends behind the same call_tool contract."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.exceptions import ToolExecutionError

LOCAL_CATALOG: list[dict[str, str]] = [
    {
        "name": "mcp_service_hours",
        "description": (
            "查询 IT 服务台的人工服务时间与夜间受理规则。"
            "何时用：问「IT 几点上班」「晚上出故障有人管吗」「周末能不能处理」。"
            "何时不用：问单张工单进度用 get_ticket；问流程用 search_knowledge。"
            "无需必填参数，payload 可空。"
            "返回 weekday、oncall、weekend 与 night_p1_only（bool）；"
            "night_p1_only=true 表示夜间只受理 P1，不要承诺夜间处理 P2/P3。"
        ),
        "transport": "local",
    },
    {
        "name": "mcp_change_calendar",
        "description": (
            "查询系统变更窗口与变更冻结期。"
            "何时用：问「这周什么时候维护」「ERP 会不会停服」「月底能不能发版」。"
            "何时不用：问故障处理进度用 get_ticket；问变更流程用 search_knowledge。"
            "无需必填参数，payload 可空。"
            "返回 next_window、systems、freeze；freeze 期间不允许非紧急变更。"
        ),
        "transport": "local",
    },
]

_LOCAL_HANDLERS: dict[str, dict[str, Any]] = {
    "mcp_service_hours": {
        "weekday": "09:00-19:00",
        "oncall": "19:00-22:00",
        "weekend": "10:00-18:00",
        "night_p1_only": True,
        "source": "mcp_local",
    },
    "mcp_change_calendar": {
        "next_window": "本周六 02:00-06:00",
        "systems": ["ERP", "CRM", "GitLab"],
        "freeze": "每月最后两个工作日",
        "source": "mcp_local",
    },
}


async def call_mcp_tool(
    *,
    name: str,
    arguments: dict[str, Any],
    transport: str,
    endpoint: str = "",
) -> dict[str, Any]:
    if transport == "local":
        if name not in _LOCAL_HANDLERS:
            raise ToolExecutionError(f"unknown local MCP tool: {name}")
        return {**_LOCAL_HANDLERS[name], "arguments": arguments}
    if not endpoint:
        raise ToolExecutionError(f"remote MCP tool {name} has no endpoint")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                endpoint,
                json={"name": name, "arguments": arguments},
                headers={"content-type": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise ToolExecutionError(f"remote MCP transport error: {name}") from exc
    if response.status_code >= 400:
        raise ToolExecutionError(f"remote MCP HTTP {response.status_code}")
    body = response.json()
    if not isinstance(body, dict):
        raise ToolExecutionError("remote MCP returned non-object JSON")
    return body
