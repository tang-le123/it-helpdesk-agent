import pytest

from app.agents.nodes.planner import Planner, planner_node
from app.core.enums import ToolRisk
from app.core.exceptions import InvalidRequestError
from app.providers.fake import OfflineLLMProvider
from app.schemas.chat import ActionProposal, ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.tools.access_tools import RequestAccessTool
from app.tools.registry import ToolRegistry
from app.tools.ticket_tools import CreateTicketTool, GetTicketTool


def _action() -> ActionProposal:
    return ActionProposal(
        action_id="act_test",
        tool_name="create_ticket",
        arguments={
            "category": "network",
            "priority": "p2",
            "title": "VPN 连不上",
            "description": "出差前 VPN 提示证书过期",
        },
        risk=ToolRisk.WRITE,
        summary="确认后将创建 P2 工单「VPN 连不上」。",
    )


@pytest.mark.asyncio
async def test_ticket_creation_needs_explicit_request_and_confirmation() -> None:
    registry = ToolRegistry()
    registry.register(GetTicketTool())
    registry.register(CreateTicketTool())
    registry.register(RequestAccessTool())
    planner = Planner(OfflineLLMProvider(), registry)

    proposal = await planner_node({"user_query": "帮我报修，VPN 连不上"}, planner)
    assert proposal["pending_action"].tool_name == "create_ticket"
    assert "create_ticket" not in proposal["pending_action"].summary

    question = await planner_node({"user_query": "报修流程是什么？"}, planner)
    assert question["pending_action"] is None

    confirmed = await planner_node(
        {"user_query": "确认执行", "confirmed_action": _action()}, planner
    )
    assert len(confirmed["plan"].steps) == 1
    assert confirmed["plan"].steps[0].arguments["title"] == "VPN 连不上"


@pytest.mark.asyncio
async def test_access_request_is_staged_not_executed() -> None:
    registry = ToolRegistry()
    registry.register(RequestAccessTool())
    planner = Planner(OfflineLLMProvider(), registry)

    proposal = await planner_node({"user_query": "帮我申请 CRM 客户导出权限"}, planner)
    action = proposal["pending_action"]
    assert action is not None
    assert action.tool_name == "request_access"
    assert "approval" in action.summary or "审批" in action.summary


def test_confirmation_is_bound_to_session_and_user() -> None:
    service = ChatService.__new__(ChatService)
    service._pending_actions = {}
    request = ChatRequest(message="帮我报修，VPN 连不上", user_id="u_demo")
    response = ChatResponse(
        answer="请确认",
        session_id="sess_demo",
        trace_id="trace_demo",
        pending_action=_action(),
    )
    service._remember_pending(request, response)

    confirmed = ChatRequest(
        message="确认执行",
        user_id="u_demo",
        session_id="sess_demo",
        confirm_action_id="act_test",
    )
    assert service._resolve_confirmation(confirmed, "sess_demo") == _action()

    forged = confirmed.model_copy(update={"user_id": "someone_else"})
    with pytest.raises(InvalidRequestError):
        service._resolve_confirmation(forged, "sess_demo")
    with pytest.raises(InvalidRequestError):
        service._resolve_confirmation(confirmed, "another_session")
