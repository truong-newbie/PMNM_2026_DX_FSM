# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Admin Routes
# Endpoints chỉ dành cho manager/admin (SLA check, monitoring).

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.security import get_current_user, TokenUser
from app.services.sla_monitor import run_sla_check_once

router = APIRouter()


class SLACheckResponse(BaseModel):
    scanned: int
    breached: int
    dispatched: int
    errors: int


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
