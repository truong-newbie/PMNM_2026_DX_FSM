# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – FastAPI Application
# Tầng 2: H-P-D-I – Service Tier

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import init_db
from app.routes import tickets, users, auth, health, comments, attachments, admin
from app.services.sla_monitor import sla_monitor_loop, SCAN_INTERVAL_SEC

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý startup/shutdown: init DB + start SLA background monitor."""
    await init_db()

    # Start SLA monitor background task
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        sla_monitor_loop(stop_event, interval_sec=SCAN_INTERVAL_SEC)
    )
    app.state.sla_stop = stop_event
    app.state.sla_task = task
    logger.info(f"SLA monitor scheduled (interval={SCAN_INTERVAL_SEC}s)")

    try:
        yield
    finally:
        # Graceful shutdown
        stop_event.set()
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            task.cancel()
            logger.warning("SLA monitor task force-cancelled")
        logger.info("SLA monitor stopped")


app = FastAPI(
    title="DX-FSM Ticket Service",
    description="Core API for Field Service Management Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
app.include_router(comments.router, tags=["Comments"])
app.include_router(attachments.router, tags=["Attachments"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(admin.router, tags=["Admin"])


@app.get("/")
async def root():
    return {
        "service": "DX-FSM Ticket Service",
        "version": "1.0.0",
        "status": "running",
    }
