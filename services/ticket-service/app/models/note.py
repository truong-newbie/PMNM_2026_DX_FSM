# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Internal Note Model
# Notes chỉ dành cho staff (technician/manager/admin).
# Customer KHÔNG thấy notes, kể cả khi GET.

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class TicketNote(Base):
    """
    Internal note trên ticket — chỉ staff thấy.

    Khác với TicketComment:
      - Comment có thể internal hoặc public
      - Note luôn internal (customer không bao giờ thấy)
    """

    __tablename__ = "ticket_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    author_name = Column(String(255), nullable=True)  # denormalized for performance
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_notes_ticket_id_created_at", "ticket_id", "created_at"),
    )
