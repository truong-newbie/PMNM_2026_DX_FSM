# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Ticket History Routes
# A9: Audit trail endpoint – xem lịch sử thay đổi của ticket.
# Permission:
#   - Customer: chỉ thấy action liên quan đến ticket của mình
#   - Staff (manager/admin/technician): thấy tất cả action

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.ticket import Ticket, TicketHistory
from app.models.user import User

router = APIRouter(prefix="/tickets", tags=["History"])


# ─── Response models ────────────────────────────────────────────


class HistoryActorResponse(BaseModel):
    id: str
    username: Optional[str] = None
    full_name: Optional[str] = None


class HistoryResponse(BaseModel):
    id: str
    action: str
    actor: Optional[HistoryActorResponse] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── GET /tickets/{id}/history ─────────────────────────────────────


@router.get("/{ticket_id}/history", response_model=List[HistoryResponse])
async def list_ticket_history(
    ticket_id: UUID,
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Lấy audit log của ticket.

    - Customer: thấy history của ticket mình sở hữu
    - Staff (technician/manager/admin): thấy tất cả
    - Sort: created_at ASC (chronological)
    - Pagination: limit (max 500), offset
    """
    # 1. Verify ticket exists
    ticket_row = await db.execute(
        select(Ticket.id, Ticket.customer_id).where(Ticket.id == ticket_id)
    )
    row = ticket_row.first()
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_id_found, ticket_customer_id = row

    # 2. Permission check: customer chỉ thấy ticket của mình
    if user.role == "customer":
        # Resolve current user's local id
        from app.services.user_resolver import resolve_or_create_user
        local_user_id = await resolve_or_create_user(db, user)
        if local_user_id is None or str(ticket_customer_id) != str(local_user_id):
            raise HTTPException(
                status_code=403,
                detail="You can only view history of your own tickets",
            )

    # 3. Query history rows
    stmt = (
        select(TicketHistory)
        .where(TicketHistory.ticket_id == ticket_id)
        .order_by(TicketHistory.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    history_rows = result.scalars().all()

    # 4. Batch lookup actors
    user_ids = {h.user_id for h in history_rows if h.user_id}
    actor_map: dict = {}
    if user_ids:
        rows = await db.execute(
            select(User.id, User.username, User.full_name).where(User.id.in_(user_ids))
        )
        for uid, username, full_name in rows.all():
            actor_map[uid] = HistoryActorResponse(
                id=str(uid),
                username=username,
                full_name=full_name,
            )

    # 5. Build response
    return [
        HistoryResponse(
            id=str(h.id),
            action=h.action,
            actor=actor_map.get(h.user_id),
            old_value=h.old_value,
            new_value=h.new_value,
            metadata=h.metadata_json,
            created_at=h.created_at,
        )
        for h in history_rows
    ]
