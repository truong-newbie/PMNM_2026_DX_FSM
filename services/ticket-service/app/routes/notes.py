# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Internal Notes Routes
# Staff-only notes (technician/manager/admin).
# Customer KHÔNG bao giờ thấy notes, kể cả GET /tickets/{id}/notes trả 403.

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.ticket import Ticket, TicketHistory
from app.models.note import TicketNote
from app.models.user import User
from app.services.user_resolver import resolve_or_create_user

router = APIRouter(prefix="/tickets", tags=["Notes"])

# ─── Request/Response models ────────────────────────────────────────────


class NoteCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty or whitespace")
        return v


class NoteResponse(BaseModel):
    id: str
    ticket_id: str
    author_id: str
    author_name: Optional[str] = None
    body: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Helpers ────────────────────────────────────────────────────────────

# Roles được phép tạo/xem internal notes
STAFF_ROLES = {"technician", "manager", "admin"}


def _require_staff(user: TokenUser) -> None:
    """Raise 403 nếu user không phải staff."""
    if user.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Internal notes are staff-only (technician/manager/admin)",
        )


async def _resolve_author_name(db: AsyncSession, user: TokenUser) -> Optional[str]:
    """
    Tìm full_name theo user.id. Fallback về username nếu chưa có.
    """
    user_id = await resolve_or_create_user(db, user)
    if user_id is None:
        return user.username or user.preferred_username
    row = await db.get(User, user_id)
    return row.full_name if row and row.full_name else (user.username or user.preferred_username)


async def _ticket_exists(db: AsyncSession, ticket_id: UUID) -> bool:
    stmt = select(Ticket.id).where(Ticket.id == ticket_id)
    return (await db.execute(stmt)).first() is not None


# ─── POST /tickets/{id}/notes ───────────────────────────────────────────


@router.post("/{ticket_id}/notes", response_model=NoteResponse, status_code=201)
async def create_note(
    ticket_id: UUID,
    payload: NoteCreate,
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Tạo internal note. Staff only.

    - 403 nếu user là customer
    - 404 nếu ticket không tồn tại
    - 201 với note vừa tạo
    """
    _require_staff(user)

    if not await _ticket_exists(db, ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")

    author_id = await resolve_or_create_user(db, user)
    author_name = await _resolve_author_name(db, user)

    note = TicketNote(
        ticket_id=ticket_id,
        author_id=author_id,
        author_name=author_name,
        body=payload.body,
    )
    db.add(note)

    # History audit
    history = TicketHistory(
        ticket_id=ticket_id,
        user_id=author_id,
        action="note_added",
        new_value=f"Note added by {author_name or user.username}",
    )
    db.add(history)

    await db.commit()
    await db.refresh(note)

    return NoteResponse(
        id=str(note.id),
        ticket_id=str(note.ticket_id),
        author_id=str(note.author_id),
        author_name=note.author_name,
        body=note.body,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# ─── GET /tickets/{id}/notes ────────────────────────────────────────────


@router.get("/{ticket_id}/notes", response_model=List[NoteResponse])
async def list_notes(
    ticket_id: UUID,
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=200),
):
    """
    List internal notes. Staff only (customer always 403).

    Trả về notes sắp xếp theo created_at ASC (chronological).
    """
    _require_staff(user)

    if not await _ticket_exists(db, ticket_id):
        raise HTTPException(status_code=404, detail="Ticket not found")

    stmt = (
        select(TicketNote)
        .where(TicketNote.ticket_id == ticket_id)
        .order_by(TicketNote.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    notes = result.scalars().all()

    return [
        NoteResponse(
            id=str(n.id),
            ticket_id=str(n.ticket_id),
            author_id=str(n.author_id),
            author_name=n.author_name,
            body=n.body,
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in notes
    ]
