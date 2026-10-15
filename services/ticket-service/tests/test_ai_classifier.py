# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – AI Classifier tests
# A6: cache + rule-based + AI fallback logic

import pytest

from app.services.ai_classifier import (
    classify_ticket,
    rule_based_classify,
    _cache,
    _classify_category,
    _classify_priority,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Đảm bảo mỗi test có cache rỗng."""
    _cache._store.clear()
    yield
    _cache._store.clear()


# ─── Category classification ──────────────────────────────────────────


class TestCategoryClassifier:
    def test_network_vietnamese(self):
        cat, conf = _classify_category("Wifi mất kết nối", "Phòng A1 không vào được mạng")
        assert cat == "network"
        assert conf >= 0.5

    def test_network_english(self):
        cat, conf = _classify_category("Network switch down", "Core switch floor 3 chết")
        assert cat == "network"

    def test_hardware_vietnamese(self):
        cat, conf = _classify_category("Máy in không in", "HP printer báo offline")
        assert cat == "hardware"

    def test_hardware_english(self):
        cat, conf = _classify_category("Mouse broken", "USB mouse không hoạt động")
        assert cat == "hardware"

    def test_software_vietnamese(self):
        cat, conf = _classify_category("Excel bị crash", "File Excel 50MB crash liên tục")
        assert cat == "software"

    def test_electrical_vietnamese(self):
        cat, conf = _classify_category("Đèn phòng họp cháy", "Đèn tuýp cháy có mùi khét")
        assert cat == "electrical"

    def test_unknown_category_falls_back_to_other(self):
        cat, conf = _classify_category("Random title", "Random text không match gì")
        assert cat == "other"
        assert conf == 0.0


# ─── Priority classification ──────────────────────────────────────────


class TestPriorityClassifier:
    def test_critical_keyword_vietnamese(self):
        prio, conf = _classify_priority("Server sập khẩn cấp", "Production server down")
        assert prio == "critical"

    def test_critical_english(self):
        prio, conf = _classify_priority("Critical: server down", "Production emergency")
        assert prio == "critical"

    def test_high_keyword(self):
        prio, conf = _classify_priority("Ảnh hưởng nhiều người", "Cả team không làm việc được")
        assert prio == "high"

    def test_low_keyword(self):
        prio, conf = _classify_priority("Hỏi thông tin", "Phòng IT làm việc mấy giờ?")
        assert prio == "low"

    def test_default_is_medium(self):
        prio, conf = _classify_priority("Random title", "Normal text without urgency")
        assert prio == "medium"


# ─── Full classify with cache ──────────────────────────────────────────


class TestFullClassify:
    @pytest.mark.asyncio
    async def test_first_call_uses_ai_or_fallback(self):
        """First call: dùng AI service (nếu running) hoặc fallback (nếu down)."""
        result = await classify_ticket("Wifi mất kết nối", "không vào được mạng")
        assert result.category == "network"
        assert result.method in ("ai", "fallback")
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self):
        """Lần 2 với cùng input → method='cached'."""
        await classify_ticket("Wifi mất kết nối", "không vào được mạng")
        result = await classify_ticket("Wifi mất kết nối", "không vào được mạng")
        assert result.method == "cached"
        assert result.category == "network"

    @pytest.mark.asyncio
    async def test_different_input_not_cached(self):
        """Input khác → không cache hit, re-classify."""
        await classify_ticket("Wifi mất kết nối", "abc")
        result = await classify_ticket("Server down", "xyz")
        assert result.method in ("ai", "fallback")  # depends on service availability

    @pytest.mark.asyncio
    async def test_response_has_required_fields(self):
        result = await classify_ticket("Test", "test")
        assert result.category
        assert result.priority
        assert result.method in ("ai", "fallback", "cached")
        # Confidence range: 0-1 (rule-based) or 0-100 (AI service).
        # Accept either scale.
        assert 0.0 <= result.confidence <= 100.0
        assert result.recommendation
