# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – pytest fixtures
# Reusable: test client, JWT tokens giả lập, in-memory DB (optional).

import os
import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Set test env vars BEFORE app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dxfsm:dxfsm_password@localhost:5432/dxfsm")
os.environ.setdefault("KEYCLOAK_URL", "http://localhost:8080")
os.environ.setdefault("KEYCLOAK_REALM", "dx-fsm")
os.environ.setdefault("KEYCLOAK_AUDIENCE", "dx-fsm-api")
os.environ.setdefault("N8N_WEBHOOK_URL", "http://n8n:5678/webhook")
os.environ.setdefault("AI_SERVICE_URL", "http://ai-service:8002")

from app.main import app  # noqa: E402


# ─── Test client fixture ────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """Async HTTP client chạy trực tiếp trên FastAPI app (không qua network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Auth bypass fixture ────────────────────────────────────────────────
# Mock get_current_user để tránh gọi Keycloak trong test

from app.core.security import get_current_user, TokenUser  # noqa: E402


def _make_token_user(role: str, username: str = "test-user") -> TokenUser:
    """Tạo TokenUser object giả cho test."""
    import time
    return TokenUser(
        sub=f"test-sub-{username}",
        preferred_username=username,
        email=f"{username}@test.local",
        full_name=username.title(),
        role=role,
        exp=int(time.time()) + 3600,  # 1h ahead
        iss="http://localhost:8080/realms/dx-fsm",
    )


@pytest.fixture
def admin_user():
    return _make_token_user("admin", "admin")


@pytest.fixture
def manager_user():
    return _make_token_user("manager", "manager")


@pytest.fixture
def technician_user():
    return _make_token_user("technician", "technician")


@pytest.fixture
def customer_user():
    return _make_token_user("customer", "customer")


@pytest.fixture(autouse=True)
def _mock_current_user(request):
    """
    Auto-mock get_current_user cho tất cả test trong module này.
    Mỗi test có thể override bằng cách inject fixture role cụ thể.
    """
    # Default: admin nếu test không chỉ định role
    role = "admin"
    for name in ("admin_user", "manager_user", "technician_user", "customer_user"):
        if name in request.fixturenames:
            role = name.replace("_user", "")
            break

    def _override():
        return _make_token_user(role, role)

    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ─── DB session shared với app event loop ──────────────────────────────
# Fix: tránh "Task got Future attached to a different loop"
# Khi test gọi app.dependency_overrides[get_db] qua ASGITransport,
# request handler dùng get_db() → AsyncSessionLocal() → engine bound
# to the loop running ASGI. Nếu test tạo AsyncSessionLocal() riêng,
# engine sẽ bound to test's loop → mismatch.
# Cách: dùng get_db override để share session, hoặc tạo session qua
# FastAPI Depends(get_db) thay vì AsyncSessionLocal() trực tiếp.


@pytest_asyncio.fixture
async def db_session():
    """
    Yield một session qua get_db() — chạy trong cùng loop với app.
    Test nào cần DB thật mới dùng fixture này; tests khác skip nếu
    cần integration thì dùng API client (vì client đã chạy trong app loop).
    """
    from app.db.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

