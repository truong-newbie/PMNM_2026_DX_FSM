# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Outbox Dispatcher tests
# A8: backoff + retry logic (DB tests skip để tránh loop mismatch)

import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import pytest

from app.services.outbox_dispatcher import (
    _compute_next_retry,
    BACKOFF_SECONDS,
    call_n8n,
    process_one_event,
)


# ─── Backoff scheduling (pure logic) ───────────────────────────────


class TestBackoffSchedule:
    def test_first_attempt_5s(self):
        next_retry = _compute_next_retry(1)
        delta = (next_retry - datetime.now(timezone.utc)).total_seconds()
        assert 4 <= delta <= 6

    def test_second_attempt_25s(self):
        next_retry = _compute_next_retry(2)
        delta = (next_retry - datetime.now(timezone.utc)).total_seconds()
        assert 24 <= delta <= 26

    def test_third_attempt_125s(self):
        next_retry = _compute_next_retry(3)
        delta = (next_retry - datetime.now(timezone.utc)).total_seconds()
        assert 124 <= delta <= 126

    def test_max_backoff_index_safe(self):
        # attempts=99 → capped, không IndexError
        next_retry = _compute_next_retry(99)
        delta = (next_retry - datetime.now(timezone.utc)).total_seconds()
        assert delta > 0

    def test_backoff_array_well_defined(self):
        """Verify backoff progression: 5, 25, 125, 625, 3125."""
        assert BACKOFF_SECONDS == [5, 25, 125, 625, 3125]
        # Each step is 5x the previous
        for i in range(1, len(BACKOFF_SECONDS)):
            assert BACKOFF_SECONDS[i] == BACKOFF_SECONDS[i - 1] * 5


# ─── call_n8n (mocked httpx) ────────────────────────────────────────


class TestCallN8n:
    @pytest.mark.asyncio
    async def test_call_n8n_success(self):
        """Mock httpx 2xx response → (True, None)."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("app.services.outbox_dispatcher.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post.return_value = mock_response
            MockClient.return_value = mock_client_instance

            ok, error = await call_n8n(_make_fake_event())
            assert ok is True
            assert error is None

    @pytest.mark.asyncio
    async def test_call_n8n_500_returns_error(self):
        """5xx → (False, error_msg)."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("app.services.outbox_dispatcher.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post.return_value = mock_response
            MockClient.return_value = mock_client_instance

            ok, error = await call_n8n(_make_fake_event())
            assert ok is False
            assert "500" in error

    @pytest.mark.asyncio
    async def test_call_n8n_connect_error(self):
        """ConnectError → (False, 'ConnectError...')."""
        with patch("app.services.outbox_dispatcher.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__.return_value.post.side_effect = Exception("Connection refused")
            MockClient.return_value = mock_client_instance

            ok, error = await call_n8n(_make_fake_event())
            assert ok is False
            assert error is not None


# ─── Helper ────────────────────────────────────────────────────────


def _make_fake_event():
    """Tạo event giả (không cần DB)."""
    from app.models.outbox import OutboxEvent
    ev = OutboxEvent(
        id=uuid.uuid4(),
        event_type="ticket-created",
        payload={"test": True},
        status="pending",
        attempts=0,
    )
    return ev
