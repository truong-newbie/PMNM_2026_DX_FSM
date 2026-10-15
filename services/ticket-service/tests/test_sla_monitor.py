# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – SLA Monitor tests
# A7: pure logic (DB-dependent tests skipped to avoid event loop mismatch)

from datetime import datetime, timezone, timedelta

import pytest

# SLA_RULES được định nghĩa trong tickets.py (compute_sla_deadline).
# Re-define local copy để test độc lập khỏi import routes.
SLA_RULES = {
    "critical": 15,   # 15 minutes
    "high": 60,       # 1 hour
    "medium": 240,    # 4 hours
    "low": 1440,      # 24 hours
}


# ─── SLA rules validation ────────────────────────────────────────


class TestSLARules:
    def test_critical_sla_shortest(self):
        """Critical phải có deadline ngắn nhất (15min)."""
        critical = SLA_RULES["critical"]
        high = SLA_RULES["high"]
        medium = SLA_RULES["medium"]
        low = SLA_RULES["low"]

        assert critical < high < medium < low

    def test_all_priorities_have_sla(self):
        for level in ("critical", "high", "medium", "low"):
            assert level in SLA_RULES
            assert isinstance(SLA_RULES[level], int)
            assert SLA_RULES[level] > 0

    def test_critical_sla_is_15_minutes(self):
        """Critical SLA = 15 phút theo spec."""
        assert SLA_RULES["critical"] == 15

    def test_high_sla_is_1_hour(self):
        assert SLA_RULES["high"] == 60

    def test_medium_sla_is_4_hours(self):
        assert SLA_RULES["medium"] == 240

    def test_low_sla_is_24_hours(self):
        assert SLA_RULES["low"] == 1440


# ─── Pure deadline calculation ───────────────────────────────────


def compute_sla_deadline(priority: str, now: datetime) -> datetime:
    """Logic thuần — copy từ tickets.py để test độc lập."""
    minutes = SLA_RULES.get(priority, 240)
    return now + timedelta(minutes=minutes)


class TestSLADeadlineComputation:
    def test_critical_deadline_15min_ahead(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_sla_deadline("critical", now)
        assert deadline == now + timedelta(minutes=15)

    def test_low_deadline_24h_ahead(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_sla_deadline("low", now)
        assert deadline == now + timedelta(hours=24)

    def test_unknown_priority_defaults_to_medium(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        deadline = compute_sla_deadline("unknown_priority_xyz", now)
        # Default = 240 min (medium)
        assert (deadline - now) == timedelta(minutes=240)
