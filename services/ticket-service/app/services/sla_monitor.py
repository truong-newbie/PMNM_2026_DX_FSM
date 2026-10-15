# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – SLA Monitor
# Background task: scan tickets quá deadline, set sla_met=false, dispatch n8n.

import asyncio
import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.ticket import Ticket
from app.services.n8n_dispatcher import dispatch_sla_breach

logger = logging.getLogger(__name__)

# TICKETS ở các status này KHÔNG bị tính là SLA breach
TERMINAL_STATUSES = ("resolved", "closed", "cancelled")

# Scan interval (giây) – production 300, dev có thể set 30
SCAN_INTERVAL_SEC = 300


async def find_overdue_tickets(db: AsyncSession) -> list[Ticket]:
    """
    Return list of tickets where:
      - sla_deadline < NOW()
      - status NOT IN (resolved, closed, cancelled)
      - sla_met IS NULL  (chưa đánh dấu lần nào)
    """
    stmt = select(Ticket).where(
        Ticket.sla_deadline.isnot(None),
        Ticket.sla_deadline < __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        Ticket.status.notin_(TERMINAL_STATUSES),
        Ticket.sla_met.is_(None),
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_sla_breached(db: AsyncSession, ticket_ids: list) -> int:
    """
    Set sla_met=false cho danh sách ticket_id.
    Returns số row đã update.
    """
    if not ticket_ids:
        return 0
    stmt = (
        update(Ticket)
        .where(Ticket.id.in_(ticket_ids))
        .values(sla_met=False)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def run_sla_check_once() -> dict:
    """
    Một lần scan toàn bộ. Trả về dict {scanned, breached, dispatched, errors}.
    Dùng cho cả background loop và endpoint POST /admin/sla/check.
    """
    summary = {"scanned": 0, "breached": 0, "dispatched": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        try:
            overdue = await find_overdue_tickets(db)
        except Exception as e:
            logger.error(f"SLA scan failed: {e}", exc_info=True)
            summary["errors"] += 1
            return summary

        summary["scanned"] = len(overdue)

        if not overdue:
            return summary

        # Mark + commit trong cùng transaction
        try:
            ticket_ids = [t.id for t in overdue]
            updated = await mark_sla_breached(db, ticket_ids)
            summary["breached"] = updated
        except Exception as e:
            logger.error(f"SLA update failed: {e}", exc_info=True)
            summary["errors"] += 1
            return summary

        # Enqueue n8n event vào outbox (atomic với mark_sla_breached)
        for t in overdue:
            try:
                await dispatch_sla_breach(
                    db=db,
                    ticket_id=str(t.id),
                    ticket_number=t.ticket_number,
                    title=t.title,
                    priority=str(t.priority.value if hasattr(t.priority, "value") else t.priority),
                    sla_deadline=t.sla_deadline.isoformat() if t.sla_deadline else None,
                )
                summary["dispatched"] += 1
            except Exception as e:
                logger.warning(f"outbox enqueue failed for {t.ticket_number}: {e}")
                summary["errors"] += 1

        # Commit enqueues
        await db.commit()

    return summary


async def sla_monitor_loop(stop_event: asyncio.Event, interval_sec: int = SCAN_INTERVAL_SEC):
    """
    Long-running background task. Chạy scan mỗi interval_sec giây
    cho đến khi stop_event được set.
    """
    logger.info(f"SLA monitor started (interval={interval_sec}s)")
    while not stop_event.is_set():
        try:
            summary = await run_sla_check_once()
            if summary["scanned"] > 0:
                logger.info(
                    f"SLA scan: scanned={summary['scanned']}, "
                    f"breached={summary['breached']}, "
                    f"dispatched={summary['dispatched']}"
                )
        except Exception as e:
            logger.error(f"SLA loop error: {e}", exc_info=True)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
        except asyncio.TimeoutError:
            pass  # tiếp tục loop

    logger.info("SLA monitor stopped")
