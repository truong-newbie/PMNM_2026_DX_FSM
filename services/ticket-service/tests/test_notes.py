# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – Internal Notes API tests
# A5: auth + validation — dùng mocked get_current_user (không cần real DB)
# Note: integration tests với real DB chạy trong pipeline end-to-end khác

import pytest
from pydantic import ValidationError

from app.routes.notes import NoteCreate, STAFF_ROLES


# ─── Pydantic validation ──────────────────────────────────────


class TestNoteCreateValidation:
    def test_valid_body(self):
        n = NoteCreate(body="Test note content")
        assert n.body == "Test note content"

    def test_strip_whitespace(self):
        n = NoteCreate(body="  trimmed content  ")
        assert n.body == "trimmed content"

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            NoteCreate(body="")
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            NoteCreate(body="   \n\t  ")
        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()

    def test_too_long_body_rejected(self):
        with pytest.raises(ValidationError):
            NoteCreate(body="x" * 5001)  # max 5000

    def test_max_length_accepted(self):
        n = NoteCreate(body="x" * 5000)
        assert len(n.body) == 5000


# ─── Staff roles constant ─────────────────────────────────────


class TestStaffRoles:
    def test_includes_technician(self):
        assert "technician" in STAFF_ROLES

    def test_includes_manager(self):
        assert "manager" in STAFF_ROLES

    def test_includes_admin(self):
        assert "admin" in STAFF_ROLES

    def test_excludes_customer(self):
        assert "customer" not in STAFF_ROLES

    def test_excludes_other_roles(self):
        """Không có role nào khác lọt vào staff list."""
        for role in ("guest", "anonymous", "support", "auditor", ""):
            assert role not in STAFF_ROLES
