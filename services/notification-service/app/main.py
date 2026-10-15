# SPDX-License-Identifier: Apache-2.0
# DX-FSM Notification Service

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="DX-FSM Notification Service", version="1.0.0")


class NotifyRequest(BaseModel):
    user_id: str
    title: str
    message: str
    type: str = "info"


@app.post("/notify")
async def send_notification(req: NotifyRequest):
    return {"status": "sent", "notification_id": "notif-placeholder"}


@app.get("/notifications")
async def list_notifications(
    user_id: Optional[str] = None,
    is_read: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
):
    """List notifications – stub, trả empty list."""
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
