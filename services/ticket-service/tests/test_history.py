# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Ticket History API tests
# A9: permission + pagination

import pytest
from pydantic import ValidationError

from app.routes.history import HistoryResponse, HistoryActorResponse


# ─── Pydantic response validation ───────────────────────────────


class TestHistoryResponseShape:
    def test_valid_minimal(self):
        h = HistoryResponse(
            id="abc-123",
            action="created",
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert h.action == "created"
        assert h.actor is None
        assert h.old_value is None
        assert h.new_value is None
        assert h.metadata is None

    def test_valid_full(self):
        h = HistoryResponse(
            id="abc-123",
            action="status_changed",
            actor=HistoryActorResponse(
                id="user-1",
                username="admin",
                full_name="Quản trị viên",
            ),
            old_value="open",
            new_value="in_progress",
            metadata={"ip": "10.0.0.1", "user_agent": "Mozilla/5.0"},
            created_at="2026-01-01T12:00:00+00:00",
        )
        assert h.action == "status_changed"
        assert h.actor.username == "admin"
        assert h.metadata["ip"] == "10.0.0.1"

    def test_required_fields(self):
        with pytest.raises(ValidationError):
            HistoryResponse(id="abc", action="created")  # missing created_at


class TestHistoryActorResponse:
    def test_minimal(self):
        a = HistoryActorResponse(id="user-1")
        assert a.id == "user-1"
        assert a.username is None
        assert a.full_name is None

    def test_full(self):
        a = HistoryActorResponse(id="user-2", username="tech", full_name="Trần Văn Kỹ Thuật")
        assert a.username == "tech"
        assert a.full_name == "Trần Văn Kỹ Thuật"


# ─── Permission behavior (logic-only, không cần real DB) ──────────────


def customer_owns_ticket(role: str, user_id: str, ticket_customer_id: str) -> bool:
    """Pure logic: customer chỉ được xem ticket của mình."""
    if role != "customer":
        return True  # staff thấy tất cả
    return str(user_id) == str(ticket_customer_id)


class TestHistoryPermission:
    def test_admin_sees_all_tickets(self):
        assert customer_owns_ticket("admin", "user-1", "any-other") is True

    def test_manager_sees_all_tickets(self):
        assert customer_owns_ticket("manager", "user-1", "any-other") is True

    def test_technician_sees_all_tickets(self):
        assert customer_owns_ticket("technician", "user-1", "any-other") is True

    def test_customer_sees_own_ticket(self):
        assert customer_owns_ticket("customer", "user-1", "user-1") is True

    def test_customer_blocked_from_other_ticket(self):
        assert customer_owns_ticket("customer", "user-1", "user-99") is False


# ─── Pagination logic ───────────────────────────────────────────


def paginate(offset: int, limit: int, total: int):
    """Pure logic: clamp offset/limit, return valid range."""
    if limit <= 0 or limit > 500:
        limit = 100
    if offset < 0:
        offset = 0
    end = min(offset + limit, total)
    start = min(offset, end)
    return start, end, list(range(start, end))


class TestPagination:
    def test_basic(self):
        start, end, items = paginate(0, 10, 50)
        assert start == 0
        assert end == 10
        assert items == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    def test_offset_beyond_total(self):
        start, end, items = paginate(100, 10, 50)
        assert start == 50
        assert end == 50
        assert items == []

    def test_limit_clamped_to_max(self):
        start, end, items = paginate(0, 1000, 50)
        assert end == 50  # capped at total

    def test_negative_offset_clamped(self):
        start, end, items = paginate(-5, 10, 50)
        assert start == 0

    def test_zero_total(self):
        start, end, items = paginate(0, 10, 0)
        assert items == []
