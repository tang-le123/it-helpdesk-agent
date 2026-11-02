"""Ticket, asset and approval schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import (
    ApprovalKind,
    ApprovalStatus,
    AssetStatus,
    TicketPriority,
    TicketStatus,
)


class TicketEvent(BaseModel):
    event_type: str
    actor_id: str
    content: str = ""
    created_at: datetime


class Ticket(BaseModel):
    ticket_id: str
    user_id: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    title: str
    description: str = ""
    assignee_group: str | None = None
    source: str = "chat"
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    sla_due_at: datetime | None = None
    events: list[TicketEvent] = Field(default_factory=list)


class Asset(BaseModel):
    asset_id: str
    asset_type: str
    model: str
    serial_no: str
    owner_user_id: str | None = None
    status: AssetStatus
    purchased_at: datetime | None = None
    warranty_until: datetime | None = None
    location: str = ""


class Approval(BaseModel):
    approval_id: str
    ticket_id: str | None = None
    requester_id: str
    kind: ApprovalKind
    target: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus
    approver_role: str
    approver_id: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    expires_at: datetime | None = None
    executed_at: datetime | None = None
