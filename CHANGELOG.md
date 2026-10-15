# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v1.1.0-sprint4] – 2026-01-15

Sprint 4 — ticket workflow completion, audit trail, outbox pattern, test coverage.

### Added

- **Internal Notes (A5)** — staff-only note API for ticket
  - `POST /tickets/{id}/notes` — create note (technician/manager/admin only)
  - `GET /tickets/{id}/notes` — list notes (staff only, customer 403)
  - Validation: empty/whitespace/5000 chars (422)
  - Body strip whitespace, audit logged to ticket_history
  - Author auto-provisioned from Keycloak sub (user_resolver)

- **SLA Monitor (A7)** — background loop + admin trigger
  - `POST /admin/sla/check` — manual trigger (admin/manager)
  - SLA rules: critical=15min, high=1h, medium=4h, low=24h
  - Idempotent: skip tickets already marked `sla_met=false`
  - Logs scanned/breached/dispatched summary
  - Background loop runs every 5min (configurable via `SCAN_INTERVAL_SEC`)

- **Outbox Pattern (A8)** — n8n webhook delivery with retry/backoff
  - Outbox table: event_type, payload, status, attempts, next_retry_at
  - Backoff schedule: 5s → 25s → 125s → 625s → 3125s (5x per attempt)
  - Max 5 attempts → status `failed`
  - Atomic claim via `UPDATE ... WHERE status='pending'`
  - `POST /admin/outbox/run` — manual trigger
  - `GET /admin/outbox?status=pending` — list events
  - Integrated with ticket status changes (auto-enqueue)

- **Ticket History (A9)** — audit trail endpoint
  - `GET /tickets/{id}/history?limit&offset` — chronological audit log
  - Customer: own tickets only (403 for others)
  - Staff: all tickets
  - Batch actor lookup (1 query, no N+1)
  - Pagination: limit max 500, default 100

- **AI Classifier (A6)** — cache + rule-based + AI fallback
  - In-memory cache: key = hash(title+description)
  - Cache hit returns `method='cached'`
  - Rule-based fallback when AI service down
  - Hybrid: tries AI first (5s timeout), falls back to rule-based
  - Confidence: 0-100 (AI scale) or 0-1 (rule-based scale)

- **Test Coverage** — 69 unit tests (54 → 69)
  - test_ai_classifier.py (16): category, priority, cache, fallback
  - test_outbox.py (7): backoff schedule, call_n8n with mocked httpx
  - test_notes.py (10): Pydantic validation, STAFF_ROLES constant
  - test_sla_monitor.py (9): SLA rules, deadline computation
  - test_admin.py (9): auth/role checks on admin endpoints
  - test_history.py (15): response shape, permission matrix, pagination
  - test_tickets.py (3): health, list, create with role
  - conftest.py: AsyncClient + ASGITransport, mock get_current_user

- **CI Pipeline** — full GitHub Actions workflow
  - 6 jobs: lint-python, lint-frontend, test-ticket-service (with Postgres
    service), test-ai-service, test-frontend, secret-scan (TruffleHog)
  - Concurrency: cancel in-progress on same branch
  - Triggers: push + PR to main/develop
  - YAML validated against GitHub Actions schema

### Changed

- **comments.py + attachments.py** — dedup user-resolver logic
  - Inline keycloak_id lookup + legacy fallback + auto-provision moved to
    `app/services/user_resolver.py` (resolve_or_create_user)
  - Net -87 dòng duplicate code, +10 dòng helper call

- **TicketHistory model** — column rename
  - `extra_data` (Python attr) → `metadata_json` mapped to DB column "metadata"
  - DB schema already used "metadata"; Python attr was misnamed

### Fixed

- **init.sql** — ticket_history column mismatch
  - DB had column "metadata" but model declared "extra_data"
  - Caused 500 on any history query

- **pre-commit hook** — secret scanner
  - Catches accidental API keys, tokens, passwords before commit
  - Allowlist in `.secrets.allowlist` for test fixtures

### Security

- Internal notes: customer cannot list, view, or create (403 enforced)
- Admin endpoints: explicit role guard (admin/manager only, customer 403)
- JWT verification: all routes through Keycloak JWKS
- Tracemalloc warnings cleaned up (test runtime)

### Documentation

- `docs/api-specification.md` — full Sprint 4 coverage
  - New endpoints documented (notes, history, admin)
  - Role matrix: 13 endpoints × 4 roles
  - Error responses + 422 added
- `docs/SECURITY.md` — secret scanner rationale, incident response
- `CHANGELOG.md` (this file) — Sprint 4 deliverables

### Known Limitations

- 2 tests skipped in pytest (event loop mismatch with SQLAlchemy async engine
  when pytest-asyncio creates new loop per test). Workaround: explicit
  try/except + comment; integration tests run in E2E pipeline.
- Outbox retries forever-failed events don't notify (silent — needs ops alerting)

### Migration

From v1.0.0 → v1.1.0-sprint4:
- No breaking API changes
- New tables: `outbox_events` (auto-created via init.sql)
- New columns: `tickets.sla_met` (nullable boolean)
- Run `core/postgres/init.sql` if fresh DB

---

## [v1.0.0] – 2025-12-20

### Added

- Initial release
- DX-OS Open-Core architecture (3-tier)
  - Keycloak for Identity/SSO
  - Apache APISIX for API Gateway
  - PostgreSQL for structured data
  - MinIO for file storage
  - n8n for workflow automation
- Ticket Service API (FastAPI)
  - CRUD operations for tickets
  - User management integration
  - File upload via MinIO
- AI Service
  - Ticket classification (Ollama/Llama 3.2)
  - Technician recommendation
  - Rule-based fallback
- Vue 3 Frontend Application
  - Customer portal (create/track tickets)
  - Technician portal (process tickets)
  - Manager dashboard (KPI/analytics)
- H-P-D-I implementation
  - H: User profiles and authentication
  - P: Complete ticket workflow
  - D: Real-time dashboard and reports
  - I: AI-powered classification and recommendations
- Docker Compose orchestration
- Documentation (Docusaurus)
- GitHub Actions CI/CD pipeline
- Open-source compliance (Apache-2.0)

### Features

- [x] SSO authentication via Keycloak
- [x] Role-based access control (customer/technician/manager/admin)
- [x] Ticket lifecycle management
- [x] Automatic ticket classification using AI
- [x] Technician recommendation engine
- [x] File attachment upload
- [x] Real-time dashboard
- [x] SLA monitoring
- [x] Notification system
- [x] Fallback for AI service unavailability

---

## [v0.0.1] – 2025-11-15

### Added

- Project scaffolding
- Initial repository structure
- Development environment setup
