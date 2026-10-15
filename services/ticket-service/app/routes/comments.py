# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Comments Routes

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, cast, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.ticket import Ticket, TicketComment, TicketHistory
from app.models.user import User

router = APIRouter()


# ─── Pydantic models ────────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    """Body for POST /tickets/{id}/comments."""
    content: str = Field(..., min_length=1, max_length=5000)
    is_internal: bool = False  # True = chỉ staff (manager/tech) thấy


class CommentResponse(BaseModel):
    id: str
    ticket_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    content: str
    is_internal: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _build_comment_response(c: TicketComment, user_name: Optional[str] = None) -> CommentResponse:
    return CommentResponse(
        id=str(c.id),
        ticket_id=str(c.ticket_id),
        user_id=str(c.user_id) if c.user_id else None,
        user_name=user_name,
        content=c.content,
        is_internal=c.is_internal,
        created_at=_dt_to_str(c.created_at),
        updated_at=_dt_to_str(c.updated_at),
    )


# ─── POST /tickets/{id}/comments ───────────────────────────────────────────


@router.post("/tickets/{ticket_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    ticket_id: UUID,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """
    Add a comment to a ticket.

    - is_internal=True: chỉ manager/admin/technician thấy
    - is_internal=False: mọi người liên quan thấy
    - Customer chỉ được comment is_internal=False
    """
    # 1. Verify ticket exists
    result = await db.execute(select(Ticket.id).where(Ticket.id == ticket_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 2. Internal comments: chỉ staff (manager/admin/technician)
    if payload.is_internal and user.role == "customer":
        raise HTTPException(
            status_code=403,
            detail="Internal comments are restricted to staff",
        )

    # 3. Lookup or provision local user from keycloak_id (sub)
    actor_id: Optional[UUID] = None
    if user.sub:
        result = await db.execute(
            select(User.id).where(User.keycloak_id == user.sub)
        )
        actor_id = result.scalar_one_or_none()

        if actor_id is None:
            # Try to match by username as a fallback (legacy seed data)
            result = await db.execute(
                select(User.id).where(User.username == user.preferred_username)
            )
            legacy = result.scalar_one_or_none()
            if legacy:
                # Update legacy row to use real Keycloak sub
                from sqlalchemy import update
                await db.execute(
                    update(User)
                    .where(User.id == legacy)
                    .values(keycloak_id=user.sub)
                )
                actor_id = legacy
            else:
                # Brand new user: auto-provision
                role = user.role if user.role in ("admin", "manager", "technician", "customer") else "customer"
                new_user = User(
                    keycloak_id=user.sub,
                    username=user.preferred_username or user.sub[:8],
                    email=user.email,
                    full_name=user.full_name,
                    role=role,
                )
                db.add(new_user)
                await db.flush()
                actor_id = new_user.id

    # 4. Create comment
    comment = TicketComment(
        ticket_id=ticket_id,
        user_id=actor_id,
        content=payload.content,
        is_internal=payload.is_internal,
    )
    db.add(comment)

    # 5. Write history row
    history = TicketHistory(
        ticket_id=ticket_id,
        user_id=actor_id,
        action="comment_added",
        new_value=(
            f"Internal comment ({len(payload.content)} chars)"
            if payload.is_internal
            else f"Comment ({len(payload.content)} chars)"
        ),
    )
    db.add(history)

    await db.commit()
    await db.refresh(comment)

    return _build_comment_response(comment, user_name=user.preferred_username)


# ─── GET /tickets/{id}/comments ────────────────────────────────────────────


@router.get("/tickets/{ticket_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """
    List all comments for a ticket.

    - Customer: chỉ thấy is_internal=False
    - Staff (manager/admin/technician): thấy tất cả
    - Sort: created_at ASC (oldest first)
    """
    # 1. Verify ticket exists
    result = await db.execute(select(Ticket.id).where(Ticket.id == ticket_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 2. Fetch comments
    query = select(TicketComment).where(TicketComment.ticket_id == ticket_id)
    if user.role == "customer":
        # Customer chỉ thấy public comments
        query = query.where(TicketComment.is_internal == False)  # noqa: E712
    query = query.order_by(TicketComment.created_at.asc())

    result = await db.execute(query)
    comments = result.scalars().all()

    # 3. Batch lookup user names
    user_ids = {c.user_id for c in comments if c.user_id}
    name_map: dict = {}
    if user_ids:
        rows = await db.execute(
            select(User.id, User.username, User.full_name).where(User.id.in_(user_ids))
        )
        for uid, username, full_name in rows.all():
            name_map[uid] = full_name or username

    return [
        _build_comment_response(c, user_name=name_map.get(c.user_id))
        for c in comments
    ]


# ─── DELETE /tickets/{id}/comments/{comment_id} ────────────────────────────


@router.delete(
    "/tickets/{ticket_id}/comments/{comment_id}",
    status_code=204,
)
async def delete_comment(
    ticket_id: UUID,
    comment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """
    Delete a comment (soft semantics: xóa row nhưng vẫn ghi history).

    Permission:
    - Owner (người viết) OR
    - Manager/admin
    - Technician không phải owner → 403
    - Customer không phải owner → 403
    """
    # 1. Fetch comment
    result = await db.execute(
        select(TicketComment).where(
            TicketComment.id == comment_id,
            TicketComment.ticket_id == ticket_id,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # 2. Resolve actor
    actor_id: Optional[UUID] = None
    if user.sub:
        result = await db.execute(
            select(User.id).where(User.keycloak_id == user.sub)
        )
        actor_id = result.scalar_one_or_none()
        if actor_id is None:
            result = await db.execute(
                select(User.id).where(User.username == user.preferred_username)
            )
            actor_id = result.scalar_one_or_none()

    # 3. Permission check
    is_owner = actor_id is not None and comment.user_id == actor_id
    is_admin_or_manager = user.role in ("admin", "manager")
    if not (is_owner or is_admin_or_manager):
        raise HTTPException(
            status_code=403,
            detail="Only comment author or manager/admin can delete",
        )

    # 4. Write history
    history = TicketHistory(
        ticket_id=ticket_id,
        user_id=actor_id,
        action="comment_removed",
        old_value=(
            f"Internal comment ({len(comment.content)} chars)"
            if comment.is_internal
            else f"Comment ({len(comment.content)} chars)"
        ),
    )
    db.add(history)

    # 5. Delete
    await db.delete(comment)
    await db.commit()

    return None
