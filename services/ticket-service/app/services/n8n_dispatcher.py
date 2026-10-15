# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – n8n Webhook Dispatcher (outbox-backed)
# Mọi event đều ghi vào outbox table trước (cùng transaction với business
# logic), background worker sẽ retry delivery với exponential backoff.

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.outbox_dispatcher import enqueue_event

logger = logging.getLogger(__name__)


async def dispatch_ticket_created(
    db: AsyncSession,
    ticket_id: str,
    ticket_number: str,
) -> None:
    """
    Ghi event 'ticket.created' vào outbox.
    Phải gọi trong cùng transaction với ticket insert để đảm bảo
    atomic (cùng success hoặc cùng rollback).
    """
    try:
        await enqueue_event(
            db,
            event_type="ticket-created",
            payload={
                "event": "ticket.created",
                "ticket_id": ticket_id,
                "ticket_number": ticket_number,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to enqueue ticket.created: {e}")
        raise


async def dispatch_sla_breach(
    db: AsyncSession,
    ticket_id: str,
    ticket_number: str,
    title: str,
    priority: str,
    sla_deadline: Optional[str],
) -> None:
    """
    Ghi event 'sla.breached' vào outbox.
    """
    try:
        await enqueue_event(
            db,
            event_type="sla-breached",
            payload={
                "event": "sla.breached",
                "ticket_id": ticket_id,
                "ticket_number": ticket_number,
                "title": title,
                "priority": priority,
                "sla_deadline": sla_deadline,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to enqueue sla.breached: {e}")
        raise
