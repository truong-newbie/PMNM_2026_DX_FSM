# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Dashboard Metrics Routes
# A10: Manager/Admin metrics endpoint cho KPI dashboard.
# Cung cấp counts, distributions, SLA stats, recent activity.

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.outbox import OutboxEvent
from app.models.ticket import (
    Ticket,
    TicketCategoryEnum,
    TicketPriorityEnum,
    TicketStatusEnum,
)
from app.services.user_resolver import resolve_or_create_user

router = APIRouter(prefix="/admin/metrics", tags=["Metrics"])


# ─── Response models ───────────────────────────────────────────


class StatusCount(BaseModel):
    status: str
    count: int


class PriorityCount(BaseModel):
    priority: str
    count: int


class CategoryCount(BaseModel):
    category: str
    count: int


class SLAStats(BaseModel):
    total_active: int = 0
    on_time: int = 0          # active tickets còn trong deadline
    breached: int = 0         # active tickets quá deadline
    met: int = 0              # closed/resolved với sla_met=true
    not_met: int = 0          # closed/resolved với sla_met=false
    breach_rate: float = 0.0  # breached / (breached + on_time + met + not_met)


class RecentActivity(BaseModel):
    last_24h_created: int
    last_24h_resolved: int
    last_24h_breached: int


class OutboxHealth(BaseModel):
    pending: int
    sending: int
    sent: int
    failed: int
    oldest_pending_age_sec: Optional[int] = None  # seconds since oldest pending was created


class TopAssignee(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    active_tickets: int
    resolved_tickets: int


class MetricsResponse(BaseModel):
    generated_at: datetime
    window_days: int

    # Ticket counts
    total_tickets: int
    by_status: List[StatusCount]
    by_priority: List[PriorityCount]
    by_category: List[CategoryCount]

    # SLA
    sla: SLAStats

    # Throughput
    activity: RecentActivity

    # Outbox worker health
    outbox: OutboxHealth

    # Top performers (top 5)
    top_assignees: List[TopAssignee]


# ─── GET /admin/metrics ──────────────────────────────────────


@router.get("", response_model=MetricsResponse)
async def get_dashboard_metrics(
    window_days: int = 30,
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard metrics cho manager/admin.

    Permission: admin/manager only. Customer/technician → 403.

    Args:
        window_days: cửa sổ thời gian cho "recent activity" (default 30).

    Returns:
        Counts theo status/priority/category, SLA stats, outbox health,
        top assignees (active + resolved counts).
    """
    # ─── 1. Permission ─────────────────────────────────────
    if user.role not in ("admin", "manager"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Dashboard metrics are restricted to admin/manager",
        )

    # Clamp window
    if window_days < 1:
        window_days = 1
    if window_days > 365:
        window_days = 365

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)
    last_24h = now - timedelta(hours=24)

    # ─── 2. Total tickets ─────────────────────────────────
    total = await db.execute(select(func.count(Ticket.id)))
    total_tickets = total.scalar() or 0

    # ─── 3. By status ─────────────────────────────────────
    by_status_rows = await db.execute(
        select(Ticket.status, func.count(Ticket.id))
        .group_by(Ticket.status)
    )
    by_status = [
        StatusCount(status=str(row[0].value if hasattr(row[0], "value") else row[0]), count=row[1])
        for row in by_status_rows.all()
    ]

    # ─── 4. By priority ───────────────────────────────────
    by_priority_rows = await db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .group_by(Ticket.priority)
    )
    by_priority = [
        PriorityCount(priority=str(row[0].value if hasattr(row[0], "value") else row[0]), count=row[1])
        for row in by_priority_rows.all()
    ]

    # ─── 5. By category ───────────────────────────────────
    by_category_rows = await db.execute(
        select(Ticket.category, func.count(Ticket.id))
        .group_by(Ticket.category)
    )
    by_category = [
        CategoryCount(category=str(row[0].value if hasattr(row[0], "value") else row[0]), count=row[1])
        for row in by_category_rows.all()
    ]

    # ─── 6. SLA stats ─────────────────────────────────────
    # Active states = not in (resolved, closed, cancelled)
    active_states = [
        TicketStatusEnum.new,
        TicketStatusEnum.assigned,
        TicketStatusEnum.in_progress,
        TicketStatusEnum.pending,
    ]

    # Total active
    total_active_q = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.status.in_(active_states))
    )
    total_active = total_active_q.scalar() or 0

    # On time: active AND sla_deadline > now
    on_time_q = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.status.in_(active_states))
        .where(Ticket.sla_deadline > now)
    )
    on_time = on_time_q.scalar() or 0

    # Breached: active AND sla_deadline <= now AND sla_met != true
    breached_q = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.status.in_(active_states))
        .where(Ticket.sla_deadline <= now)
        .where((Ticket.sla_met != True) | (Ticket.sla_met.is_(None)))  # noqa: E712
    )
    breached = breached_q.scalar() or 0

    # Met: closed/resolved AND sla_met=true
    finished_states = [TicketStatusEnum.resolved, TicketStatusEnum.closed]
    met_q = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.status.in_(finished_states))
        .where(Ticket.sla_met == True)  # noqa: E712
    )
    met = met_q.scalar() or 0

    # Not met: closed/resolved AND sla_met=false
    not_met_q = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.status.in_(finished_states))
        .where(Ticket.sla_met == False)  # noqa: E712
    )
    not_met = not_met_q.scalar() or 0

    total_sla_scored = breached + on_time + met + not_met
    breach_rate = (breached + not_met) / total_sla_scored if total_sla_scored > 0 else 0.0

    sla_stats = SLAStats(
        total_active=total_active,
        on_time=on_time,
        breached=breached,
        met=met,
        not_met=not_met,
        breach_rate=round(breach_rate, 4),
    )

    # ─── 7. Recent activity (last 24h) ────────────────────
    created_24h_q = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.created_at >= last_24h)
    )
    last_24h_created = created_24h_q.scalar() or 0

    resolved_24h_q = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.status.in_(finished_states))
        .where(Ticket.updated_at >= last_24h)
    )
    last_24h_resolved = resolved_24h_q.scalar() or 0

    # Breached in last 24h: tickets có sla_met=false và updated_at gần đây
    breached_24h_q = await db.execute(
        select(func.count(Ticket.id))
        .where(Ticket.sla_met == False)  # noqa: E712
        .where(Ticket.updated_at >= last_24h)
    )
    last_24h_breached = breached_24h_q.scalar() or 0

    activity = RecentActivity(
        last_24h_created=last_24h_created,
        last_24h_resolved=last_24h_resolved,
        last_24h_breached=last_24h_breached,
    )

    # ─── 8. Outbox health ─────────────────────────────────
    outbox_counts = await db.execute(
        select(OutboxEvent.status, func.count(OutboxEvent.id))
        .group_by(OutboxEvent.status)
    )
    status_map = {row[0]: row[1] for row in outbox_counts.all()}

    # Oldest pending age
    oldest_pending = await db.execute(
        select(OutboxEvent.created_at)
        .where(OutboxEvent.status == "pending")
        .order_by(OutboxEvent.created_at.asc())
        .limit(1)
    )
    oldest_row = oldest_pending.first()
    oldest_age_sec = None
    if oldest_row:
        delta = (now - oldest_row[0]).total_seconds()
        oldest_age_sec = int(delta)

    outbox_health = OutboxHealth(
        pending=status_map.get("pending", 0),
        sending=status_map.get("sending", 0),
        sent=status_map.get("sent", 0),
        failed=status_map.get("failed", 0),
        oldest_pending_age_sec=oldest_age_sec,
    )

    # ─── 9. Top assignees (top 5 by active tickets) ───────
    # Use raw SQL grouping on technician_id
    top_q = await db.execute(
        select(
            Ticket.technician_id,
            func.count(Ticket.id).filter(Ticket.status.in_(active_states)).label("active"),
            func.count(Ticket.id).filter(Ticket.status.in_(finished_states)).label("resolved"),
        )
        .where(Ticket.technician_id.isnot(None))
        .group_by(Ticket.technician_id)
        .order_by(func.count(Ticket.id).filter(Ticket.status.in_(active_states)).desc())
        .limit(5)
    )
    top_rows = top_q.all()

    # Batch lookup user names
    from app.models.user import User
    user_ids = [row[0] for row in top_rows if row[0]]
    name_map: Dict = {}
    if user_ids:
        name_q = await db.execute(
            select(User.id, User.username, User.full_name).where(User.id.in_(user_ids))
        )
        for uid, username, full_name in name_q.all():
            name_map[uid] = (username, full_name)

    top_assignees = [
        TopAssignee(
            user_id=str(row[0]),
            username=name_map.get(row[0], (None, None))[0],
            full_name=name_map.get(row[0], (None, None))[1],
            active_tickets=row[1],
            resolved_tickets=row[2],
        )
        for row in top_rows
    ]

    return MetricsResponse(
        generated_at=now,
        window_days=window_days,
        total_tickets=total_tickets,
        by_status=by_status,
        by_priority=by_priority,
        by_category=by_category,
        sla=sla_stats,
        activity=activity,
        outbox=outbox_health,
        top_assignees=top_assignees,
    )
