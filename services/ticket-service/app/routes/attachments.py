# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Attachments Routes
# Upload file lên MinIO (hoặc local fallback) và link với ticket.

import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, TokenUser
from app.db.database import get_db
from app.models.ticket import Ticket, TicketAttachment, TicketHistory
from app.models.user import User
from app.services.storage_service import upload_attachment
from app.services.user_resolver import resolve_or_create_user

router = APIRouter()


# ─── Pydantic models ────────────────────────────────────────────────────────


class AttachmentResponse(BaseModel):
    id: str
    ticket_id: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    url: str  # minio URL hoặc local path
    created_at: Optional[str] = None


def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ─── Limits ──────────────────────────────────────────────────────────────────

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg", "image/png", "image/gif", "image/webp",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Text
    "text/plain", "text/csv",
    # Archives
    "application/zip", "application/x-7z-compressed",
    # JSON (logs, exports)
    "application/json",
}


# ─── Helper: lookup/provision user from JWT ──────────────────────────────────


async def _resolve_actor_id(db: AsyncSession, user: TokenUser) -> Optional[UUID]:
    """Wrapper gọi user_resolver. Giữ signature để không sửa call sites."""
    return await resolve_or_create_user(db, user)


# ─── POST /tickets/{id}/attachments ────────────────────────────────────────


@router.post(
    "/tickets/{ticket_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
)
async def upload_ticket_attachment(
    ticket_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """
    Upload a file attachment for a ticket.

    - Multipart/form-data, field name: file
    - Max 10 MB
    - Allowed mime types: images, PDF, Office, text, archives
    - All authenticated roles allowed
    - Storage: MinIO (preferred) hoặc local filesystem fallback
    """
    # 1. Verify ticket exists
    result = await db.execute(select(Ticket.id).where(Ticket.id == ticket_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 2. Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{content_type}' not allowed",
        )

    # 3. Read with size limit
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    # 4. Upload to storage
    safe_name = os.path.basename(file.filename or "attachment")
    try:
        url, size = await upload_attachment(
            file_data=data,
            file_name=safe_name,
            content_type=content_type,
        )
    except Exception as e:
        # Local fallback cũng fail → 500
        raise HTTPException(
            status_code=500,
            detail=f"Storage upload failed: {e}",
        )

    # 5. Resolve actor
    actor_id = await _resolve_actor_id(db, user)

    # 6. Save attachment record
    attachment = TicketAttachment(
        ticket_id=ticket_id,
        user_id=actor_id,
        file_name=safe_name,
        file_path=url,
        file_size=size,
        mime_type=content_type,
    )
    db.add(attachment)

    # 7. Write history
    history = TicketHistory(
        ticket_id=ticket_id,
        user_id=actor_id,
        action="attachment_added",
        new_value=f"{safe_name} ({size} bytes)",
    )
    db.add(history)

    await db.commit()
    await db.refresh(attachment)

    return AttachmentResponse(
        id=str(attachment.id),
        ticket_id=str(attachment.ticket_id),
        user_id=str(actor_id) if actor_id else None,
        user_name=user.preferred_username,
        file_name=attachment.file_name,
        file_size=attachment.file_size,
        mime_type=attachment.mime_type,
        url=attachment.file_path,
        created_at=_dt_to_str(attachment.created_at),
    )


# ─── GET /tickets/{id}/attachments ─────────────────────────────────────────


@router.get(
    "/tickets/{ticket_id}/attachments",
    response_model=list[AttachmentResponse],
)
async def list_ticket_attachments(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """List all attachments for a ticket."""
    # 1. Verify ticket exists
    result = await db.execute(select(Ticket.id).where(Ticket.id == ticket_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Ticket not found")

    # 2. Fetch attachments
    rows = await db.execute(
        select(TicketAttachment, User.username, User.full_name)
        .outerjoin(User, TicketAttachment.user_id == User.id)
        .where(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.created_at.asc())
    )

    return [
        AttachmentResponse(
            id=str(att.id),
            ticket_id=str(att.ticket_id),
            user_id=str(att.user_id) if att.user_id else None,
            user_name=full_name or username,
            file_name=att.file_name,
            file_size=att.file_size,
            mime_type=att.mime_type,
            url=att.file_path,
            created_at=_dt_to_str(att.created_at),
        )
        for att, username, full_name in rows.all()
    ]


# ─── DELETE /tickets/{ticket_id}/attachments/{att_id} ───────────────────────


@router.delete(
    "/tickets/{ticket_id}/attachments/{att_id}",
    status_code=204,
)
async def delete_attachment(
    ticket_id: UUID,
    att_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: TokenUser = Depends(get_current_user),
):
    """
    Delete an attachment.
    - Owner (uploader) OR
    - Manager/admin
    - Chỉ xóa DB record, không xóa file trên MinIO (audit trail)
    """
    result = await db.execute(
        select(TicketAttachment).where(
            TicketAttachment.id == att_id,
            TicketAttachment.ticket_id == ticket_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Permission: uploader himself OR staff (manager/admin/technician)
    actor_id = await _resolve_actor_id(db, user)
    is_owner = actor_id is not None and attachment.user_id == actor_id
    is_staff = user.role in ("admin", "manager", "technician")

    if not (is_owner or is_staff):
        raise HTTPException(
            status_code=403,
            detail="Only uploader or staff can delete this attachment",
        )

    # Write history
    history = TicketHistory(
        ticket_id=ticket_id,
        user_id=actor_id,
        action="attachment_removed",
        old_value=attachment.file_name,
    )
    db.add(history)

    await db.delete(attachment)
    await db.commit()

    return None
