# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – n8n webhook dispatcher
# Best-effort HTTP call đến n8n. Fail silently (không block business flow).

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def _post_event(event_type: str, payload: dict) -> bool:
    """
    Gọi n8n webhook. Trả về True nếu 2xx, False nếu fail.
    Fail silently — n8n down không nên block API request.
    """
    url = f"{settings.n8n_webhook_url}/{event_type}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 200 and resp.status_code < 300:
                logger.debug(f"n8n {event_type} OK: {resp.status_code}")
                return True
            logger.warning(
                f"n8n {event_type} returned {resp.status_code}: {resp.text[:200]}"
            )
            return False
    except httpx.ConnectError:
        # n8n container chưa chạy — bình thường trong dev
        logger.debug(f"n8n {event_type} skipped (n8n unavailable)")
        return False
    except Exception as e:
        logger.warning(f"n8n {event_type} failed: {e}")
        return False


async def dispatch_ticket_created(ticket_id: str, ticket_number: str) -> bool:
    """Gọi n8n khi ticket mới được tạo."""
    return await _post_event(
        "ticket-created",
        {"ticket_id": ticket_id, "ticket_number": ticket_number},
    )


async def dispatch_sla_breach(
    ticket_id: str,
    ticket_number: str,
    title: str,
    priority: str,
    sla_deadline: Optional[str],
) -> bool:
    """Gọi n8n khi ticket vi phạm SLA."""
    return await _post_event(
        "sla-breached",
        {
            "ticket_id": ticket_id,
            "ticket_number": ticket_number,
            "title": title,
            "priority": priority,
            "sla_deadline": sla_deadline,
            "event": "sla.breached",
        },
    )
