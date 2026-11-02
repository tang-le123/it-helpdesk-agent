"""Ticket, asset and approval persistence.

Every read that returns a user-owned row goes through a ``get_visible_*``
method: another employee's ticket or asset must look like a 404, never like a
permission error, otherwise the API leaks which ids exist.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
    ApprovalKind,
    ApprovalStatus,
    AssetStatus,
    TicketPriority,
    TicketStatus,
)
from app.core.exceptions import DatabaseError, InvalidRequestError
from app.core.ids import new_id
from app.core.time import utcnow
from app.repositories.models import (
    ApprovalRow,
    AssetRow,
    AuditLogRow,
    TicketEventRow,
    TicketRow,
)
from app.schemas.ticket import Approval, Asset, Ticket, TicketEvent

#: First-response target per priority, used to stamp ``sla_due_at`` on create.
SLA_HOURS: dict[str, float] = {"p1": 0.5, "p2": 4.0, "p3": 8.0}

DEFAULT_ASSIGNEE_GROUP = {
    "account": "IT-账号权限组",
    "device": "IT-桌面支持组",
    "network": "IT-网络组",
    "software": "IT-应用支持组",
    "security": "信息安全组",
}


def escape_like(term: str) -> str:
    """Escape LIKE wildcards so user input cannot broaden a search."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _new_ticket_id() -> str:
    return new_id("TKT")[:12].upper()


def _new_approval_id() -> str:
    return new_id("APR")[:12].upper()


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ reads

    async def get_ticket(self, ticket_id: str) -> Ticket | None:
        try:
            result = await self._session.execute(
                select(TicketRow)
                .options(selectinload(TicketRow.events))
                .where(TicketRow.ticket_id == ticket_id)
            )
            row = result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError("failed to load ticket") from exc
        return None if row is None else _to_ticket(row)

    async def get_visible_ticket(self, ticket_id: str, user_id: str) -> Ticket:
        """Return only a ticket filed by the caller; hide others as not-found."""
        ticket = await self.get_ticket(ticket_id)
        if ticket is None or ticket.user_id != user_id:
            raise InvalidRequestError(f"ticket not found: {ticket_id}")
        return ticket

    async def list_tickets_for_user(self, user_id: str, *, limit: int = 10) -> list[Ticket]:
        result = await self._session.execute(
            select(TicketRow)
            .options(selectinload(TicketRow.events))
            .where(TicketRow.user_id == user_id)
            .order_by(TicketRow.created_at.desc())
            .limit(limit)
        )
        return [_to_ticket(row) for row in result.scalars().all()]

    async def get_asset(self, asset_id: str) -> Asset | None:
        row = await self._session.get(AssetRow, asset_id)
        return None if row is None else _to_asset(row)

    async def get_visible_asset(self, asset_id: str, user_id: str) -> Asset:
        asset = await self.get_asset(asset_id)
        if asset is None or asset.owner_user_id != user_id:
            raise InvalidRequestError(f"asset not found: {asset_id}")
        return asset

    async def list_assets_for_user(self, user_id: str, *, limit: int = 10) -> list[Asset]:
        result = await self._session.execute(
            select(AssetRow)
            .where(AssetRow.owner_user_id == user_id)
            .order_by(AssetRow.asset_id)
            .limit(limit)
        )
        return [_to_asset(row) for row in result.scalars().all()]

    async def get_approval(self, approval_id: str) -> Approval | None:
        row = await self._session.get(ApprovalRow, approval_id)
        return None if row is None else _to_approval(row)

    async def get_visible_approval(self, approval_id: str, user_id: str) -> Approval:
        approval = await self.get_approval(approval_id)
        if approval is None or approval.requester_id != user_id:
            raise InvalidRequestError(f"approval not found: {approval_id}")
        return approval

    async def list_approvals_for_user(
        self, user_id: str, *, status: ApprovalStatus | None = None, limit: int = 10
    ) -> list[Approval]:
        statement = select(ApprovalRow).where(ApprovalRow.requester_id == user_id)
        if status is not None:
            statement = statement.where(ApprovalRow.status == status.value)
        result = await self._session.execute(
            statement.order_by(ApprovalRow.created_at.desc()).limit(limit)
        )
        return [_to_approval(row) for row in result.scalars().all()]

    # ----------------------------------------------------------------- writes

    async def create_ticket(
        self,
        *,
        user_id: str,
        category: str,
        priority: str,
        title: str,
        description: str = "",
        trace_id: str,
        assignee_group: str | None = None,
    ) -> dict[str, Any]:
        """Open a ticket and its first timeline event in the same unit of work."""
        ticket_id = _new_ticket_id()
        now = utcnow()
        payload_priority = TicketPriority(priority).value
        group = assignee_group or DEFAULT_ASSIGNEE_GROUP.get(category)
        row = TicketRow(
            ticket_id=ticket_id,
            user_id=user_id,
            category=category,
            priority=payload_priority,
            status=TicketStatus.OPEN.value,
            title=title,
            description=description,
            assignee_group=group,
            created_at=now,
            updated_at=now,
            sla_due_at=now + timedelta(hours=SLA_HOURS.get(payload_priority, 8.0)),
        )
        try:
            self._session.add(row)
            self._session.add(
                TicketEventRow(
                    ticket_id=ticket_id,
                    event_type="created",
                    actor_id=user_id,
                    content=title,
                    created_at=now,
                )
            )
            await self.write_audit(
                trace_id,
                "create_ticket",
                {"ticket_id": ticket_id, "priority": payload_priority, "category": category},
            )
            await self._session.flush()
        except Exception as exc:
            raise DatabaseError("failed to create ticket") from exc
        return {
            "ticket_id": ticket_id,
            "status": row.status,
            "priority": row.priority,
            "assignee_group": row.assignee_group,
            "sla_due_at": row.sla_due_at.isoformat() if row.sla_due_at else None,
        }

    async def create_approval(
        self,
        *,
        requester_id: str,
        kind: ApprovalKind | str,
        target: str,
        payload: dict[str, Any] | None = None,
        ticket_id: str | None = None,
        approver_role: str = "manager",
        ttl_hours: int = 72,
        trace_id: str,
    ) -> dict[str, Any]:
        """Stage a write action. Nothing is executed until the approval is consumed."""
        approval_id = _new_approval_id()
        now = utcnow()
        row = ApprovalRow(
            approval_id=approval_id,
            ticket_id=ticket_id,
            requester_id=requester_id,
            kind=ApprovalKind(kind).value if not isinstance(kind, ApprovalKind) else kind.value,
            target=target,
            payload=json.dumps(payload or {}, ensure_ascii=False),
            status=ApprovalStatus.PENDING.value,
            approver_role=approver_role,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        try:
            self._session.add(row)
            await self.write_audit(
                trace_id,
                "create_approval",
                {"approval_id": approval_id, "target": target, "kind": row.kind},
            )
            await self._session.flush()
        except Exception as exc:
            raise DatabaseError("failed to create approval") from exc
        return {
            "approval_id": approval_id,
            "status": row.status,
            "target": target,
            "approver_role": approver_role,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }

    async def mark_approval(
        self,
        approval_id: str,
        *,
        status: ApprovalStatus,
        approver_id: str | None = None,
    ) -> None:
        row = await self._session.get(ApprovalRow, approval_id)
        if row is None:
            raise InvalidRequestError(f"approval not found: {approval_id}")
        row.status = status.value
        row.decided_at = utcnow()
        if approver_id is not None:
            row.approver_id = approver_id
        await self._session.flush()

    async def mark_approval_executed(self, approval_id: str) -> None:
        row = await self._session.get(ApprovalRow, approval_id)
        if row is None:
            raise InvalidRequestError(f"approval not found: {approval_id}")
        row.status = ApprovalStatus.EXECUTED.value
        row.executed_at = utcnow()
        await self._session.flush()

    async def update_ticket_status(self, ticket_id: str, status: TicketStatus) -> None:
        row = await self._session.get(TicketRow, ticket_id)
        if row is None:
            return
        row.status = status.value
        if status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            row.resolved_at = utcnow()

    async def add_event(
        self, ticket_id: str, *, event_type: str, actor_id: str, content: str = ""
    ) -> None:
        self._session.add(
            TicketEventRow(
                ticket_id=ticket_id,
                event_type=event_type,
                actor_id=actor_id,
                content=content,
            )
        )
        await self._session.flush()

    async def write_audit(self, trace_id: str, action: str, payload: str | dict[str, Any]) -> None:
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)
        self._session.add(AuditLogRow(trace_id=trace_id, action=action, payload=payload))


def _to_ticket(row: TicketRow) -> Ticket:
    return Ticket(
        ticket_id=row.ticket_id,
        user_id=row.user_id,
        category=row.category,
        priority=TicketPriority(row.priority),
        status=TicketStatus(row.status),
        title=row.title,
        description=row.description,
        assignee_group=row.assignee_group,
        source=row.source,
        created_at=row.created_at,
        updated_at=row.updated_at,
        resolved_at=row.resolved_at,
        sla_due_at=row.sla_due_at,
        events=[
            TicketEvent(
                event_type=event.event_type,
                actor_id=event.actor_id,
                content=event.content,
                created_at=event.created_at,
            )
            for event in sorted(row.events, key=lambda item: item.created_at)
        ],
    )


def _to_asset(row: AssetRow) -> Asset:
    return Asset(
        asset_id=row.asset_id,
        asset_type=row.asset_type,
        model=row.model,
        serial_no=row.serial_no,
        owner_user_id=row.owner_user_id,
        status=AssetStatus(row.status),
        purchased_at=row.purchased_at,
        warranty_until=row.warranty_until,
        location=row.location,
    )


def _to_approval(row: ApprovalRow) -> Approval:
    try:
        payload = json.loads(row.payload or "{}")
    except json.JSONDecodeError:
        payload = {}
    return Approval(
        approval_id=row.approval_id,
        ticket_id=row.ticket_id,
        requester_id=row.requester_id,
        kind=ApprovalKind(row.kind),
        target=row.target,
        payload=payload,
        status=ApprovalStatus(row.status),
        approver_role=row.approver_role,
        approver_id=row.approver_id,
        created_at=row.created_at,
        decided_at=row.decided_at,
        expires_at=row.expires_at,
        executed_at=row.executed_at,
    )
