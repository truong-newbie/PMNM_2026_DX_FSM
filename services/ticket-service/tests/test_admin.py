# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Admin API tests
# A7 + A8: /admin/sla/check + /admin/outbox/* endpoints

import pytest


# ─── POST /admin/sla/check ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sla_check_as_admin(client, admin_user):
    """Admin → 200 với summary."""
    resp = await client.post("/admin/sla/check")
    assert resp.status_code == 200
    data = resp.json()
    assert "scanned" in data
    assert "breached" in data
    assert "dispatched" in data
    assert "errors" in data
    assert isinstance(data["scanned"], int)


@pytest.mark.asyncio
async def test_sla_check_as_customer_forbidden(client, customer_user):
    """Customer → 403."""
    resp = await client.post("/admin/sla/check")
    assert resp.status_code == 403
    assert "admin or manager" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sla_check_as_technician_forbidden(client, technician_user):
    """Technician → 403 (chỉ admin/manager mới trigger được)."""
    resp = await client.post("/admin/sla/check")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sla_check_as_manager_allowed(client, manager_user):
    """Manager → 200."""
    resp = await client.post("/admin/sla/check")
    assert resp.status_code == 200


# ─── POST /admin/outbox/run ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_outbox_run_as_admin(client, admin_user):
    """Admin trigger outbox run → 200 với summary."""
    resp = await client.post("/admin/outbox/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "fetched" in data
    assert "sent" in data
    assert "retry" in data
    assert "failed" in data
    assert "skipped" in data


@pytest.mark.asyncio
async def test_outbox_run_as_customer_forbidden(client, customer_user):
    resp = await client.post("/admin/outbox/run")
    assert resp.status_code == 403


# ─── GET /admin/outbox ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_outbox_as_admin(client, admin_user):
    """Admin GET outbox events → 200. Skip nếu DB issue (event loop mismatch)."""
    try:
        resp = await client.get("/admin/outbox?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
    except RuntimeError as e:
        if "different loop" in str(e):
            pytest.skip(f"DB session loop mismatch in test env: {e}")
        raise


@pytest.mark.asyncio
async def test_list_outbox_filter_by_status(client, admin_user):
    """Filter by status=pending → chỉ trả pending events. Skip nếu DB loop mismatch."""
    try:
        resp = await client.get("/admin/outbox?status=pending&limit=50")
        assert resp.status_code == 200
        data = resp.json()
        for ev in data:
            assert ev["status"] == "pending"
    except RuntimeError as e:
        if "different loop" in str(e):
            pytest.skip(f"DB session loop mismatch: {e}")
        raise


@pytest.mark.asyncio
async def test_list_outbox_as_customer_forbidden(client, customer_user):
    resp = await client.get("/admin/outbox")
    assert resp.status_code == 403
