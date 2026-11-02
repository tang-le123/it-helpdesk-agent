"""Ticket tools: status lookup, listing and creation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import ToolRisk
from app.schemas.agent import ToolResult
from app.schemas.ticket import Ticket
from app.tools.base import NoArgsInput, Tool, ToolContext
from app.tools.deps import RepositoryBackedTool


class TicketIdInput(BaseModel):
    ticket_id: str = Field(
        min_length=5,
        max_length=32,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="工单号，如 TKT10001；不要填资产号 AST10001 或审批号 APR10001",
    )


class CreateTicketInput(BaseModel):
    category: str = Field(
        pattern=r"^(account|device|network|software|security|other)$",
        description="工单分类：account 账号权限、device 设备、network 网络、software 软件、security 安全、other 其他",
    )
    priority: str = Field(
        default="p3",
        pattern=r"^(p1|p2|p3)$",
        description="优先级：p1 影响多人或业务中断，p2 影响本人工作，p3 一般请求",
    )
    title: str = Field(
        min_length=4,
        max_length=80,
        description="一句话标题，如「外接显示器间歇性黑屏」；不要填整段描述",
    )
    description: str = Field(
        default="",
        max_length=500,
        description="现象、开始时间、已尝试的操作；不要填工单号",
    )


def _ticket_summary(ticket: Ticket) -> dict[str, Any]:
    latest = ticket.events[-1] if ticket.events else None
    return {
        "ticket_id": ticket.ticket_id,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "category": ticket.category,
        "title": ticket.title,
        "assignee_group": ticket.assignee_group,
        "created_at": ticket.created_at.isoformat(),
        "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "latest_event": (
            {
                "type": latest.event_type,
                "actor": latest.actor_id,
                "content": latest.content,
                "at": latest.created_at.isoformat(),
            }
            if latest
            else None
        ),
    }


class GetTicketTool(RepositoryBackedTool, Tool):
    name = "get_ticket"
    description = (
        "按工单号查询工单状态、优先级、处理组、SLA 截止时间和最近一条进展。只读。"
        "何时用：问「我的工单到哪了」「TKT10001 处理得怎么样」「什么时候能修好」。"
        "何时不用：查设备归属用 get_asset；查流程/政策用 search_knowledge；要新建工单用 create_ticket。"
        "参数 ticket_id：形如 TKT10001，不是资产号 AST10001，也不是审批号 APR10001。"
        "返回 ticket_id、status、priority、assignee_group、sla_due_at、latest_event；"
        "status 取值 open/in_progress/pending_approval/resolved/closed/cancelled。"
    )
    risk = ToolRisk.READ
    input_model = TicketIdInput

    async def execute(self, parsed: TicketIdInput, context: ToolContext) -> ToolResult:
        ticket = await self.repository.get_visible_ticket(parsed.ticket_id, context.user_id)
        return ToolResult(name=self.name, success=True, output=_ticket_summary(ticket))


class ListMyTicketsTool(RepositoryBackedTool, Tool):
    name = "list_my_tickets"
    description = (
        "列出当前用户名下最近的工单（默认 5 条），按创建时间倒序。只读。"
        "何时用：用户说「我有哪些工单」「最近提的问题处理得怎么样」但没给工单号。"
        "何时不用：已知工单号用 get_ticket；查资产用 list_my_assets。"
        "无需参数；返回 tickets[]，每条含 ticket_id、status、priority、title、created_at。"
    )
    risk = ToolRisk.READ
    input_model = NoArgsInput

    async def execute(self, parsed: NoArgsInput, context: ToolContext) -> ToolResult:
        tickets = await self.repository.list_tickets_for_user(context.user_id, limit=5)
        return ToolResult(
            name=self.name,
            success=True,
            output={
                "tickets": [
                    {
                        "ticket_id": ticket.ticket_id,
                        "status": ticket.status.value,
                        "priority": ticket.priority.value,
                        "title": ticket.title,
                        "created_at": ticket.created_at.isoformat(),
                    }
                    for ticket in tickets
                ]
            },
        )


class CreateTicketTool(RepositoryBackedTool, Tool):
    name = "create_ticket"
    description = (
        "创建 IT 工单（write，须用户确认后才真正建单）。"
        "何时用：用户报障（电脑坏了、连不上网、系统报错）且没有现成工单，或明确要求「帮我建单/提工单」。"
        "何时不用：只问流程或政策用 search_knowledge；已有工单查进度用 get_ticket；申请权限用 request_access。"
        "参数 category：account/device/network/software/security/other；"
        "priority：p1 影响多人或业务中断、p2 影响本人工作、p3 一般请求；"
        "title：一句话标题；description：现象、开始时间、已尝试操作。"
        "返回 ticket_id、priority、assignee_group、sla_due_at；告知工单号与预计响应时间，不要承诺具体修复时间。"
    )
    risk = ToolRisk.WRITE
    input_model = CreateTicketInput

    async def execute(self, parsed: CreateTicketInput, context: ToolContext) -> ToolResult:
        output = await self.repository.create_ticket(
            user_id=context.user_id,
            category=parsed.category,
            priority=parsed.priority,
            title=parsed.title,
            description=parsed.description,
            trace_id=context.trace_id,
        )
        return ToolResult(name=self.name, success=True, output=output, risk=self.risk)
