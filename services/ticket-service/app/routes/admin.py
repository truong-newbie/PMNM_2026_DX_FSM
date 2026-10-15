# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Admin Routes
# Endpoints chỉ dành cho manager/admin (SLA check, outbox inspection).

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.outbox import OutboxEvent
from app.services.sla_monitor import run_sla_check_once
from app.services.outbox_dispatcher import run_outbox_worker_once

router = APIRouter()


class SLACheckResponse(BaseModel):
    scanned: int
    breached: int
    dispatched: int
    errors: int


class OutboxEventResponse(BaseModel):
    id: str
    event_type: str
    status: str
    attempts: int
    max_attempts: int
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    payload: dict

    class Config:
        from_attributes = True


# ─── POST /admin/sla/check ────────────────────────────────────────────────


@router.post("/admin/sla/check", response_model=SLACheckResponse)
async def trigger_sla_check(user: TokenUser = Depends(get_current_user)):
    """
    Chạy SLA check thủ công. Manager/admin only.

    Returns: {scanned, breached, dispatched, errors}
    """
    if user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="Only admin or manager can trigger SLA check",
        )

    summary = await run_sla_check_once()
    return SLACheckResponse(**summary)


# ─── POST /admin/outbox/run ───────────────────────────────────────────────


@router.post("/admin/outbox/run")
async def trigger_outbox_run(user: TokenUser = Depends(get_current_user)):
    """
    Chạy outbox worker thủ công. Manager/admin only.
    Returns: {fetched, sent, retry, failed, skipped}
    """
    if user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="Only admin or manager can trigger outbox run",
        )

    summary = await run_outbox_worker_once()
    return summary


# ─── GET /admin/outbox ────────────────────────────────────────────────────


@router.get("/admin/outbox", response_model=list[OutboxEventResponse])
async def list_outbox_events(
    user: TokenUser = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    List outbox events để inspect. Manager/admin only.

    Query params:
      - status: pending | sending | sent | failed
      - limit: max 200, default 50
    """
    if user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=403,
            detail="Only admin or manager can view outbox",
        )

    stmt = select(OutboxEvent).order_by(OutboxEvent.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(OutboxEvent.status == status_filter)

    result = await db.execute(stmt)
    events = result.scalars().all()
    return [
        OutboxEventResponse(
            id=str(e.id),
            event_type=e.event_type,
            status=e.status,
            attempts=e.attempts,
            max_attempts=e.max_attempts,
            last_error=e.last_error,
            next_retry_at=e.next_retry_at,
            created_at=e.created_at,
            sent_at=e.sent_at,
            payload=e.payload,
        )
        for e in events
    ]
