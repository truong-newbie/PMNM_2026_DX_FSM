# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Outbox Event Model
# Lưu trữ các webhook event cần dispatch đến n8n.
# Background worker scan và gọi n8n, retry khi fail.

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.database import Base


class OutboxEvent(Base):
    """
    Outbox event table — đảm bảo webhook delivery reliable.

    Lifecycle:
      INSERT (status='pending', attempts=0)
         ↓
      Worker pick up (status='sending' optimistic)
         ↓
      n8n returns 2xx → status='sent', sent_at=NOW()
      n8n fails/timeout → attempts++, last_error set
         ↓
      attempts >= max_attempts → status='failed' (no more retry)
    """

    __tablename__ = "outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(64), nullable=False)  # "ticket.created", "sla.breached", ...
    payload = Column(JSONB, nullable=False)

    status = Column(String(16), nullable=False, default="pending")
    # pending | sending | sent | failed
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    sent_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_outbox_status_next_retry", "status", "next_retry_at"),
    )
