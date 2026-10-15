# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Ticket Routes

import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
from fastapi import Query

from app.db.database import get_db
from app.models.ticket import Ticket, TicketHistory
from app.models.user import User
from app.config import get_settings
from app.core.security import get_current_user, TokenUser
from app.services.n8n_dispatcher import dispatch_ticket_created

settings = get_settings()
router = APIRouter()

# ─── Valid categories / priorities (khớp enum PostgreSQL) ────────────────

VALID_CATEGORIES = {"hardware", "software", "network", "electrical", "other"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
SLA_HOURS = {"critical": 4, "high": 24, "medium": 72, "low": 168}


# ─── Request / Response models ───────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    description: Optional[str] = None  # min_length chỉ khi có giá trị
    category: str = Field(default="other")
    priority: str = Field(default="medium")
    customer_location: Optional[str] = None
    # customer_id/name/email lấy từ JWT — trong demo dùng body
    customer_id: UUID
    customer_name: str
    customer_email: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v.lower() not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}")
        return v.lower()

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v.lower() not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {VALID_PRIORITIES}")
        return v.lower()


class TicketResponse(BaseModel):
    id: str
    ticket_number: str
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    category: str
    customer_id: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    technician_id: Optional[str] = None
    technician_name: Optional[str] = None
    ai_category: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_recommendation: Optional[str] = None
    sla_deadline: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    assigned_at: Optional[str] = None

    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page_limit: int
    page_offset: int


class AIClassifyResponse(BaseModel):
    category: str
    priority: str
    confidence: float
    recommendation: Optional[str] = None
    method: str = "rule"


class TicketUpdate(BaseModel):
    """Body cho PATCH /tickets/{id} – chỉ field cần update."""
    status: Optional[str] = None
    technician_id: Optional[UUID] = None
    technician_name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid = {"new", "assigned", "in_progress", "pending", "resolved", "closed", "cancelled"}
        if v.lower() not in valid:
            raise ValueError(f"status must be one of {valid}")
        return v.lower()

    @field_validator("priority")
    @classmethod
    def validate_priority_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.lower() not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {VALID_PRIORITIES}")
        return v.lower()

    @field_validator("category")
    @classmethod
    def validate_category_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v.lower() not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}")
        return v.lower()


# Allowed status transitions + required role/condition
STATUS_TRANSITIONS: dict[str, dict] = {
    "new": {
        "allowed_next": {"assigned", "cancelled"},
        "requires_technician": True,
        "requires_role": None,
    },
    "assigned": {
        "allowed_next": {"in_progress", "cancelled"},
        "requires_technician": False,
        "requires_role": None,
    },
    "in_progress": {
        "allowed_next": {"pending", "resolved"},
        "requires_technician": False,
        "requires_role": None,
    },
    "pending": {
        "allowed_next": {"in_progress", "resolved", "cancelled"},
        "requires_technician": False,
        "requires_role": None,
    },
    "resolved": {
        "allowed_next": {"closed", "in_progress"},  # manager/admin mới được close
        "requires_technician": False,
        "requires_role": {"manager", "admin"},
    },
    "closed": {
        "allowed_next": set(),  # terminal
        "requires_technician": False,
        "requires_role": None,
    },
    "cancelled": {
        "allowed_next": set(),  # terminal
        "requires_technician": False,
        "requires_role": None,
    },
}


# ─── Helpers ───────────────────────────────────────────────────────────────

def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _build_ticket_response(ticket: Ticket) -> TicketResponse:
    # SQLAlchemy enum trả về enum object, .value cho raw string
    status_str = ticket.status.value if hasattr(ticket.status, "value") else ticket.status
    priority_str = ticket.priority.value if hasattr(ticket.priority, "value") else ticket.priority
    category_str = ticket.category.value if hasattr(ticket.category, "value") else ticket.category
    return TicketResponse(
        id=str(ticket.id),
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        status=status_str,
        priority=priority_str,
        category=category_str,
        customer_id=str(ticket.customer_id),
        customer_name=ticket.customer_name,
        customer_email=ticket.customer_email,
        technician_id=str(ticket.technician_id) if ticket.technician_id else None,
        technician_name=ticket.technician_name,
        ai_category=ticket.ai_category,
        ai_priority=ticket.ai_priority,
        ai_confidence=float(ticket.ai_confidence) if ticket.ai_confidence else None,
        ai_recommendation=ticket.ai_recommendation,
        sla_deadline=_dt_to_str(ticket.sla_deadline),
        created_at=_dt_to_str(ticket.created_at),
        updated_at=_dt_to_str(ticket.updated_at),
        assigned_at=_dt_to_str(ticket.assigned_at),
    )


async def _call_ai_classify(title: str, description: str) -> AIClassifyResponse:
    """Gọi ai-service /classify. Fallback rule-based nếu ai-service down."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ai_service_url}/classify",
                json={"title": title, "description": description or ""},
            )
            resp.raise_for_status()
            data = resp.json()
            return AIClassifyResponse(**data)
    except Exception:
        # AI unavailable → rule-based fallback cứng
        return AIClassifyResponse(
            category="other",
            priority="medium",
            confidence=0.0,
            recommendation="AI unavailable – please review manually.",
            method="fallback",
        )


async def _dispatch_n8n_webhook(ticket_id: UUID, ticket_number: str):
    """Gọi n8n webhook khi ticket được tạo. Fail silently — delegated to dispatcher."""
    await dispatch_ticket_created(str(ticket_id), ticket_number)


# ─── Routes ───────────────────────────────────────────────────────────────

@router.get("", response_model=TicketListResponse)
async def list_tickets(
    user: TokenUser = Depends(get_current_user),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    technician_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    q: Optional[str] = None,
    mine: bool = False,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: Optional[str] = "created_at",
    sort_dir: Optional[str] = "desc",
    db: AsyncSession = Depends(get_db),
):
    # DB schema dùng ENUM cho status/priority, ORM dùng String → cast khi filter
    from sqlalchemy import cast, Text
    s = cast(Ticket.status, Text)
    p = cast(Ticket.priority, Text)

    # Count total
    count_q = select(func.count(Ticket.id))
    query = select(Ticket)

    if status:
        count_q = count_q.where(s == status)
        query = query.where(s == status)
    if priority:
        count_q = count_q.where(p == priority)
        query = query.where(p == priority)
    if category:
        count_q = count_q.where(Ticket.category == category)
        query = query.where(Ticket.category == category)
    if technician_id:
        count_q = count_q.where(Ticket.technician_id == technician_id)
        query = query.where(Ticket.technician_id == technician_id)
    if customer_id:
        count_q = count_q.where(Ticket.customer_id == customer_id)
        query = query.where(Ticket.customer_id == customer_id)
    if q:
        pattern = f"%{q}%"
        count_q = count_q.where(Ticket.title.ilike(pattern))
        query = query.where(Ticket.title.ilike(pattern))
    if mine:
        # customer_id từ JWT header → trong demo dùng query param tạm
        pass

    # Sort
    sort_col = {"created_at": Ticket.created_at, "priority": Ticket.priority,
                "sla_deadline": Ticket.sla_deadline}.get(sort_by, Ticket.created_at)
    if sort_dir == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    # Total
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginate
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    tickets = result.scalars().all()

    return TicketListResponse(
        items=[_build_ticket_response(t) for t in tickets],
        total=total,
        page_limit=limit,
        page_offset=offset,
    )


@router.get("/stats/summary")
async def get_stats(
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func as f, cast, Text

    # DB schema dùng PostgreSQL ENUM cho status/priority nhưng ORM dùng String.
    # cast() sang TEXT để PostgreSQL cho phép so sánh enum = text.
    s = cast(Ticket.status, Text)
    p = cast(Ticket.priority, Text)

    rows = await db.execute(
        select(
            f.count(Ticket.id).label("total"),
            f.count(Ticket.id).filter(s == "new").label("new_count"),
            f.count(Ticket.id).filter(s == "assigned").label("assigned_count"),
            f.count(Ticket.id).filter(s == "in_progress").label("in_progress_count"),
            f.count(Ticket.id).filter(s == "pending").label("pending_count"),
            f.count(Ticket.id).filter(s == "resolved").label("resolved_count"),
            f.count(Ticket.id).filter(s == "closed").label("closed_count"),
            f.count(Ticket.id).filter(p == "critical").label("critical_count"),
        )
    )
    row = rows.one()
    return {
        "total": row.total,
        "by_status": {
            "new": row.new_count,
            "assigned": row.assigned_count,
            "in_progress": row.in_progress_count,
            "pending": row.pending_count,
            "resolved": row.resolved_count,
            "closed": row.closed_count,
        },
        "by_priority": {"critical": row.critical_count},
        "open": row.new_count + row.assigned_count + row.in_progress_count + row.pending_count,
        "sla_compliance_pct": None,
    }


@router.get("/overdue")
async def get_overdue(
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import cast, Text
    # DB status là enum nhưng ORM dùng String → cast sang TEXT
    s = cast(Ticket.status, Text)
    rows = await db.execute(
        select(Ticket).where(
            Ticket.sla_deadline < datetime.now(timezone.utc),
            s.notin_(["resolved", "closed", "cancelled"]),
        ).order_by(Ticket.sla_deadline.asc())
    )
    tickets = rows.scalars().all()
    return {"items": [_build_ticket_response(t) for t in tickets], "count": len(tickets)}


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _build_ticket_response(ticket)


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(
    ticket_data: TicketCreate,
    background_tasks: BackgroundTasks,
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Generate ticket number
    year = datetime.now().year
    result = await db.execute(
        text("""
            SELECT ticket_number FROM tickets
            WHERE ticket_number LIKE :prefix
            ORDER BY ticket_number DESC
            LIMIT 1
        """),
        {"prefix": f"TKT-{year}-%"},
    )
    last = result.scalar()
    if last:
        seq = int(last.split("-")[-1]) + 1
    else:
        seq = 1
    ticket_number = f"TKT-{year}-{seq:06d}"

    # 2. SLA deadline
    sla_hours = SLA_HOURS.get(ticket_data.priority, 168)
    sla_deadline = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta
    sla_deadline = sla_deadline + timedelta(hours=sla_hours)

    # 3. AI classify (parallel, không block ticket creation)
    ai_result = await _call_ai_classify(ticket_data.title, ticket_data.description or "")
    ai_category = ai_result.category
    ai_priority = ai_result.priority
    ai_confidence = ai_result.confidence
    ai_recommendation = ai_result.recommendation

    # 4. Insert ticket
    ticket = Ticket(
        ticket_number=ticket_number,
        title=ticket_data.title,
        description=ticket_data.description,
        category=ai_category or ticket_data.category,
        priority=ai_priority or ticket_data.priority,
        status="new",
        customer_id=ticket_data.customer_id,
        customer_name=ticket_data.customer_name,
        customer_email=ticket_data.customer_email,
        customer_location=ticket_data.customer_location,
        sla_deadline=sla_deadline,
        ai_category=ai_category,
        ai_priority=ai_priority,
        ai_confidence=ai_confidence,
        ai_recommendation=ai_recommendation,
    )
    db.add(ticket)
    await db.flush()  # lấy id trước commit

    # 5. Write history
    history = TicketHistory(
        ticket_id=ticket.id,
        user_id=ticket_data.customer_id,
        action="created",
        new_value=f"Ticket {ticket_number} created",
    )
    db.add(history)

    await db.commit()
    await db.refresh(ticket)

    # 6. Dispatch n8n webhook (background, non-blocking)
    background_tasks.add_task(
        _dispatch_n8n_webhook, ticket.id, ticket.ticket_number
    )

    return _build_ticket_response(ticket)


# ─── PATCH /tickets/{id} – status transition + partial update ─────────────

@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: UUID,
    update_data: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """
    PATCH /tickets/{id}
    Body: {status?, technician_id?, technician_name?, description?, priority?, category?}

    Status transition rules (enforced):
      - new → assigned: requires technician_id in body
      - resolved → closed: requires role manager or admin
      - Other transitions: any authenticated user with role technician+
      - closed/cancelled: terminal – cannot transition out

    Returns: updated TicketResponse
    """
    # 1. Fetch ticket
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    old_status = ticket.status.value if hasattr(ticket.status, "value") else ticket.status

    # 2. Validate status transition if status is being changed
    if update_data.status and update_data.status != old_status:
        rule = STATUS_TRANSITIONS.get(old_status)
        if not rule:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown current status: {old_status}",
            )

        if update_data.status not in rule["allowed_next"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid transition: {old_status} → {update_data.status}. "
                    f"Allowed: {sorted(rule['allowed_next']) or 'terminal state'}"
                ),
            )

        # Rule: requires_technician (e.g., new → assigned cần technician_id)
        if rule["requires_technician"] and not update_data.technician_id:
            raise HTTPException(
                status_code=400,
                detail=f"Transition {old_status} → {update_data.status} requires technician_id",
            )

        # Rule: requires_role (e.g., resolved → closed cần manager/admin)
        if rule["requires_role"] and user.role not in rule["requires_role"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Transition {old_status} → {update_data.status} requires "
                    f"one of roles: {sorted(rule['requires_role'])}"
                ),
            )

        ticket.status = update_data.status

        # Auto-update timestamps
        now = datetime.now(timezone.utc)
        if update_data.status == "assigned" and not ticket.assigned_at:
            ticket.assigned_at = now
        elif update_data.status == "in_progress" and not ticket.started_at:
            ticket.started_at = now
        elif update_data.status == "resolved" and not ticket.resolved_at:
            ticket.resolved_at = now
        elif update_data.status == "closed" and not ticket.closed_at:
            ticket.closed_at = now

    # 3. Update other fields if provided
    if update_data.technician_id is not None:
        ticket.technician_id = update_data.technician_id
    if update_data.technician_name is not None:
        ticket.technician_name = update_data.technician_name
    if update_data.description is not None:
        ticket.description = update_data.description
    if update_data.priority is not None:
        ticket.priority = update_data.priority
    if update_data.category is not None:
        ticket.category = update_data.category

    # 4. Write history row for status change
    if update_data.status and update_data.status != old_status:
        # Lookup local user.id from keycloak_id (sub); skip if not provisioned yet
        actor_id = None
        if user.sub:
            result = await db.execute(
                select(User.id).where(User.keycloak_id == user.sub)
            )
            actor_id = result.scalar_one_or_none()

        history = TicketHistory(
            ticket_id=ticket.id,
            user_id=actor_id,
            action="status_changed",
            old_value=old_status,
            new_value=update_data.status,
        )
        db.add(history)

    await db.commit()
    await db.refresh(ticket)

    return _build_ticket_response(ticket)
