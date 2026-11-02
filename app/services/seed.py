"""Demo data seeding for the IT service desk.

The world: an 800-person SaaS company on Feishu, 70% Windows / 30% macOS,
SSO + MFA, assets managed by Intune. ``u_demo`` is a product manager who has
one open ticket, one resolved ticket, one pending access approval and two
assigned devices.
"""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ApprovalKind,
    ApprovalStatus,
    AssetStatus,
    TicketPriority,
    TicketStatus,
)
from app.core.time import utcnow
from app.repositories.models import ApprovalRow, AssetRow, TicketEventRow, TicketRow


async def seed_demo_data(session: AsyncSession) -> None:
    """Insert missing demo rows without touching existing ones."""
    now = utcnow()

    assets = [
        AssetRow(
            asset_id="AST10001",
            asset_type="laptop",
            model="MacBook Pro 14 M3",
            serial_no="C02XK0ABCD",
            owner_user_id="u_demo",
            status=AssetStatus.IN_USE.value,
            purchased_at=now - timedelta(days=520),
            warranty_until=now + timedelta(days=210),
            location="上海总部",
        ),
        AssetRow(
            asset_id="AST10002",
            asset_type="monitor",
            model="Dell U2723QE 27寸",
            serial_no="CN0DELL1234",
            owner_user_id="u_demo",
            status=AssetStatus.IN_USE.value,
            purchased_at=now - timedelta(days=520),
            warranty_until=now + timedelta(days=575),
            location="上海总部",
        ),
        AssetRow(
            asset_id="AST10003",
            asset_type="laptop",
            model="ThinkPad T14 Gen4",
            serial_no="PF3ABCDE",
            owner_user_id=None,
            status=AssetStatus.IN_STOCK.value,
            purchased_at=now - timedelta(days=90),
            warranty_until=now + timedelta(days=1005),
            location="上海仓",
        ),
    ]
    for asset in assets:
        if await session.get(AssetRow, asset.asset_id) is None:
            session.add(asset)

    tickets = [
        TicketRow(
            ticket_id="TKT10001",
            user_id="u_demo",
            category="network",
            priority=TicketPriority.P2.value,
            status=TicketStatus.IN_PROGRESS.value,
            title="VPN 连不上，提示证书过期",
            description="出差前连接 VPN，GlobalProtect 报证书过期，已重启无效。",
            assignee_group="IT-网络组",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(hours=6),
            sla_due_at=now - timedelta(days=2) + timedelta(hours=4),
        ),
        TicketRow(
            ticket_id="TKT10002",
            user_id="u_demo",
            category="software",
            priority=TicketPriority.P3.value,
            status=TicketStatus.RESOLVED.value,
            title="申请安装 Figma 桌面版",
            description="需要 Figma 桌面版做原型评审，已提供 License 编号。",
            assignee_group="IT-应用支持组",
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=5),
            resolved_at=now - timedelta(days=5),
            sla_due_at=now - timedelta(days=6) + timedelta(hours=8),
        ),
        TicketRow(
            ticket_id="TKT10003",
            user_id="u_demo",
            category="account",
            priority=TicketPriority.P2.value,
            status=TicketStatus.PENDING_APPROVAL.value,
            title="申请 CRM 客户导出权限",
            description="季度客户回访需要导出客户列表，申请 30 天权限。",
            assignee_group="IT-账号权限组",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(hours=20),
            sla_due_at=now - timedelta(days=1) + timedelta(hours=4),
        ),
    ]
    new_ticket_ids: set[str] = set()
    for ticket in tickets:
        if await session.get(TicketRow, ticket.ticket_id) is None:
            session.add(ticket)
            new_ticket_ids.add(ticket.ticket_id)

    events = [
        TicketEventRow(
            ticket_id="TKT10001",
            event_type="created",
            actor_id="u_demo",
            content="VPN 连不上，提示证书过期",
            created_at=now - timedelta(days=2),
        ),
        TicketEventRow(
            ticket_id="TKT10001",
            event_type="assigned",
            actor_id="it.zhang",
            content="已分派至 IT-网络组，处理人张工",
            created_at=now - timedelta(days=1, hours=20),
        ),
        TicketEventRow(
            ticket_id="TKT10001",
            event_type="comment",
            actor_id="it.zhang",
            content="已远程排查，疑似 GlobalProtect 6.0 版本问题，请在客户端升级到 6.1。",
            created_at=now - timedelta(hours=6),
        ),
        TicketEventRow(
            ticket_id="TKT10002",
            event_type="created",
            actor_id="u_demo",
            content="申请安装 Figma 桌面版",
            created_at=now - timedelta(days=6),
        ),
        TicketEventRow(
            ticket_id="TKT10002",
            event_type="resolved",
            actor_id="it.li",
            content="已通过软件中心推送安装，License 绑定完成。",
            created_at=now - timedelta(days=5),
        ),
        TicketEventRow(
            ticket_id="TKT10003",
            event_type="created",
            actor_id="u_demo",
            content="申请 CRM 客户导出权限",
            created_at=now - timedelta(days=1),
        ),
        TicketEventRow(
            ticket_id="TKT10003",
            event_type="approval_requested",
            actor_id="system",
            content="已生成审批单 APR10001，等待直属主管审批。",
            created_at=now - timedelta(hours=20),
        ),
    ]
    for event in events:
        if event.ticket_id in new_ticket_ids:
            session.add(event)

    if await session.get(ApprovalRow, "APR10001") is None:
        session.add(
            ApprovalRow(
                approval_id="APR10001",
                ticket_id="TKT10003",
                requester_id="u_demo",
                kind=ApprovalKind.ACCESS.value,
                target="CRM 客户导出",
                payload='{"system":"CRM","scope":"customer_export","duration_days":30}',
                status=ApprovalStatus.PENDING.value,
                approver_role="manager",
                created_at=now - timedelta(hours=20),
                expires_at=now + timedelta(days=2),
            )
        )

    await session.flush()
