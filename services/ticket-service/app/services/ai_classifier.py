# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – AI Classifier
# Gọi ai-service (Ollama) để classify ticket.
# Fallback: rule-based keyword matching.
# Cache: in-memory LRU theo hash(title+description).

import hashlib
import logging
import re
import time
from collections import OrderedDict
from typing import Optional

import httpx
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AIClassifyResponse(BaseModel):
    category: str
    priority: str
    confidence: float
    recommendation: str
    method: str  # "ai", "fallback", "cached"


# ─── Cache ────────────────────────────────────────────────────────────────

class LRUCache:
    """LRU cache đơn giản. Max 256 entries, TTL 1 giờ."""
    MAX_SIZE = 256
    TTL_SEC = 3600

    def __init__(self):
        self._store: OrderedDict = OrderedDict()

    def get(self, key: str) -> Optional[AIClassifyResponse]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["ts"] > self.TTL_SEC:
            del self._store[key]
            return None
        # Move to end (LRU)
        self._store.move_to_end(key)
        return entry["value"]

    def set(self, key: str, value: AIClassifyResponse):
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = {"value": value, "ts": time.time()}
        if len(self._store) > self.MAX_SIZE:
            self._store.popitem(last=False)


_cache = LRUCache()


def _cache_key(title: str, description: str) -> str:
    raw = f"{title.strip().lower()}|{description.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── Rule-based fallback ──────────────────────────────────────────────────

# Category keyword patterns (Vietnamese + English)
CATEGORY_KEYWORDS = {
    "network": [
        r"\b(wifi|wi-fi|mạng|internet|lan|wan|vpn|router|switch|modem|ethernet|ping)\b",
        r"(mất|kẹt|chậm|rớt|disconnect|timeout).*(mạng|wifi|internet)",
        r"(wifi|mạng|network).*(mất|chết|không|kẹt|chậm)",
    ],
    "hardware": [
        r"\b(máy in|printer|chuột|mouse|bàn phím|keyboard|màn hình|monitor|ram|ssd|ổ cứng|hdd|cpu|fan|nguồn|psu|cable|dây|usb)\b",
        r"(hỏng|cháy|chết|broken|dead).*(máy|thiết bị|device|hardware)",
        r"(máy tính|laptop|pc).*(không bật|không lên|bập bùng|treo|đơ)",
    ],
    "software": [
        r"\b(app|application|phần mềm|software|crash|bug|error|exception|lỗi|update|upgrade|cài đặt|install|license)\b",
        r"\b(windows|office|excel|word|outlook|teams|zoom|chrome|firefox)\b",
        r"(treo|đơ|crash|bug|exception).*(app|ứng dụng|phần mềm)",
    ],
    "electrical": [
        r"\b(điện|đèn|ổ cắm|cb|aptomat|cầu chì|cháy|sét|chập|đứt dây|ngắn mạch)\b",
        r"(mất|cúp|tắt).*(điện|electricity|power)",
        r"(đèn|quạt|điều hòa|máy lạnh).*(cháy|chết|hỏng|không chạy)",
    ],
}

# Priority patterns — return numeric score (higher = more urgent)
PRIORITY_PATTERNS = {
    "critical": [
        r"\b(khẩn|khẩn cấp|urgent|emergency|critical|ngay lập tức|ASAP|sập|down|cháy|nguy hiểm)\b",
        r"\b(sản xuất|server|sản phẩm).*(dừng|stop|chết|cháy|down)\b",
        r"\b(electrocution|risk|hazard|nguy hiểm)\b",
    ],
    "high": [
        r"\b(gấp|important|high|ảnh hưởng|nhiều người|cả team|toàn bộ)\b",
        r"(không thể|cannot|can't|unable).*(làm việc|work|sử dụng|truy cập)",
        r"\b(block|chặn).*(production|prod|business|sản xuất)\b",
    ],
    "low": [
        r"\b(thông tin|hỏi|question|info|tư vấn|nhỏ|minor|when possible|không gấp)\b",
    ],
}


def _classify_category(title: str, description: str) -> tuple[str, float]:
    """Return (category, confidence)."""
    text = f"{title} {description}".lower()
    best_cat = "other"
    best_score = 0.0
    for cat, patterns in CATEGORY_KEYWORDS.items():
        score = 0.0
        for p in patterns:
            matches = re.findall(p, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                # Weight: 1 match = 0.5, 2+ = 0.8
                score = max(score, 0.5 if len(matches) == 1 else 0.8)
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat, best_score


def _classify_priority(title: str, description: str) -> tuple[str, float]:
    """Return (priority, confidence)."""
    text = f"{title} {description}".lower()
    # Check từ critical → high → low (first match wins)
    for level in ("critical", "high", "low"):
        for p in PRIORITY_PATTERNS[level]:
            if re.search(p, text, re.IGNORECASE | re.MULTILINE):
                return level, 0.6
    return "medium", 0.4


def _recommend(category: str, priority: str) -> str:
    recs = {
        ("network", "critical"): "Mất kết nối mạng nghiêm trọng. Kiểm tra router/switch ngay. Cân nhắc failover.",
        ("network", "high"): "Ảnh hưởng nhiều người dùng. Kiểm tra DNS, gateway, cable.",
        ("network", "medium"): "Cá nhân một số user. Check IP, Wi-Fi signal, driver.",
        ("hardware", "critical"): "Thiết bị hỏng ảnh hưởng production. Cần thay thế trong 4h.",
        ("hardware", "high"): "Có workaround. Lên kế hoạch thay thế trong 24h.",
        ("hardware", "medium"): "Linh kiện nhỏ. Đặt hàng nếu chưa có sẵn.",
        ("software", "critical"): "App crash ảnh hưởng công việc. Rollback version hoặc restart service.",
        ("software", "high"): "Restart app hoặc clear cache trước khi escalate.",
        ("electrical", "critical"): "NGUY HIỂM. Cắt điện khu vực và gọi thợ chuyên môn.",
        ("electrical", "high"): "Kiểm tra CB, ổ cắm. Dùng thiết bị backup nếu có.",
    }
    key = (category, priority)
    if key in recs:
        return recs[key]
    return f"Phân loại {category}/{priority}. Xem xét và phân công technician phù hợp."


def rule_based_classify(title: str, description: str) -> AIClassifyResponse:
    """Rule-based classifier dùng keyword matching (Vietnamese + English)."""
    category, cat_conf = _classify_category(title, description)
    priority, prio_conf = _classify_priority(title, description)
    # Combined confidence: weighted average
    confidence = round(0.5 * cat_conf + 0.5 * prio_conf, 2)
    recommendation = _recommend(category, priority)
    return AIClassifyResponse(
        category=category,
        priority=priority,
        confidence=confidence,
        recommendation=recommendation,
        method="fallback",
    )


# ─── AI service client (Ollama) ───────────────────────────────────────────


async def call_ai_service(title: str, description: str) -> Optional[AIClassifyResponse]:
    """
    Gọi ai-service POST /classify. Trả về None nếu fail (timeout, 5xx, network).
    """
    url = f"{settings.ai_service_url}/classify"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                json={"title": title, "description": description or ""},
            )
            if resp.status_code == 200:
                data = resp.json()
                # Force method=ai
                data["method"] = "ai"
                return AIClassifyResponse(**data)
            logger.debug(f"ai-service returned {resp.status_code}: {resp.text[:200]}")
            return None
    except httpx.ConnectError:
        logger.debug("ai-service unavailable (ConnectError)")
        return None
    except httpx.TimeoutException:
        logger.debug("ai-service timeout")
        return None
    except Exception as e:
        logger.warning(f"ai-service unexpected error: {e}")
        return None


# ─── Public API ───────────────────────────────────────────────────────────


async def classify_ticket(title: str, description: str) -> AIClassifyResponse:
    """
    Main entrypoint. Trả về classification với cache + AI + fallback.
    """
    # 1. Check cache
    key = _cache_key(title, description)
    cached = _cache.get(key)
    if cached is not None:
        # Mark as cached
        return AIClassifyResponse(
            category=cached.category,
            priority=cached.priority,
            confidence=cached.confidence,
            recommendation=cached.recommendation,
            method="cached",
        )

    # 2. Try AI service
    result = await call_ai_service(title, description)

    # 3. Fallback to rule-based
    if result is None:
        result = rule_based_classify(title, description)

    # 4. Cache result (excluding "cached" markers)
    _cache.set(key, result)
    return result
