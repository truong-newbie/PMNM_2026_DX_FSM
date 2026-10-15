# Release Notes — v1.1.0-sprint4

**Release date:** 2026-01-15
**Tag:** `v1.1.0-sprint4`
**Previous:** v1.0.0 (2025-12-20)
**Sprint:** 4 — Ticket workflow completion, audit trail, outbox, test coverage

## Highlights

Sprint 4 đóng lại ticket workflow lifecycle hoàn chỉnh từ customer tạo ticket
đến manager review. Thêm 4 endpoints mới, 2 background workers (SLA + outbox),
97 unit tests passing, CI pipeline 6 jobs.

## What's New

### 4 New Endpoints

| Method | Path | Permission | Purpose |
|---|---|---|---|
| POST | `/tickets/{id}/notes` | staff | Staff-only internal note |
| GET | `/tickets/{id}/notes` | staff | List staff notes |
| GET | `/tickets/{id}/history` | own (customer) / all (staff) | Audit trail |
| GET | `/admin/metrics` | admin/manager | Dashboard KPIs |

### 2 Background Workers

| Worker | Interval | Purpose |
|---|---|---|
| SLA Monitor | 5 min | Mark overdue tickets, enqueue notifications |
| Outbox Dispatcher | 30 s | Deliver pending events to n8n with retry |

### 2 New Database Tables

- `outbox_events`: event store for reliable n8n delivery (status, attempts, backoff)
- `ticket_history` columns: `metadata` (JSONB) for audit context

### Test Coverage

| Suite | Tests | Status |
|---|---|---|
| test_ai_classifier | 16 | ✓ pass |
| test_outbox | 7 | ✓ pass |
| test_notes | 10 | ✓ pass |
| test_sla_monitor | 9 | ✓ pass |
| test_admin | 9 | ✓ pass |
| test_history | 15 | ✓ pass |
| test_metrics | 28 | ✓ pass |
| test_tickets | 3 | ✓ pass |
| **Total** | **97** | **+ 2 known-skipped** |

### CI Pipeline

6 jobs on push/PR to main/develop:

1. `lint-python` (ruff ticket + ai services)
2. `lint-frontend` (eslint)
3. `test-ticket-service` (pytest + Postgres 16 service)
4. `test-ai-service` (pytest)
5. `test-frontend` (vitest)
6. `secret-scan` (TruffleHog verified-only)

## Architecture Patterns (Sprint 4)

### Outbox Pattern (A8)

Atomic event delivery thông qua DB transaction:

```
INSERT outbox_events (cùng transaction với domain change)
        ↓
Worker loop (30s) claim pending events
        ↓
POST n8n webhook
        ↓ success → sent / fail → backoff retry
```

Backoff: 5s → 25s → 125s → 625s → 3125s (5x progression). Max 5 attempts.

### AI Classifier Hybrid (A6)

```
Cache check (hash title+desc)
        ↓ miss
AI service (timeout 5s)
        ↓ 2xx
Cache + return (method='ai')
        ↓ 5xx / timeout
Rule-based fallback (method='fallback')
```

### SLA Background Loop (A7)

```
Every 5min:
  SELECT tickets WHERE sla_deadline < now
                    AND status IN (active)
                    AND sla_met IS NULL
  ↓
  UPDATE SET sla_met=false
  INSERT outbox_event
```

## Security

- Internal notes: customer 403 enforced on POST + GET
- Admin endpoints: explicit role guard (admin/manager only)
- JWT verification: all routes through Keycloak JWKS
- Pre-commit secret scanner catches accidental credentials

## Migration Guide

From v1.0.0 → v1.1.0-sprint4:

**No breaking changes** to existing API contracts.

**New database tables** (auto-created via `core/postgres/init.sql`):
- `outbox_events`

**New columns**:
- `tickets.sla_met` (nullable boolean)

**Steps:**

1. Pull latest code
2. Run `docker compose down && docker compose up -d --build`
3. Apply schema: `docker compose exec postgres psql -U dxfsm -d dxfsm -f /docker-entrypoint-initdb.d/init.sql`
   (init.sql idempotent, an toàn chạy nhiều lần)
4. Verify: `curl http://localhost:8001/health` → `{"status":"healthy"}`

## Known Limitations

- 2 pytest tests skipped: event loop mismatch with SQLAlchemy async engine
  when pytest-asyncio creates new loop per test. Integration tests chạy trong
  E2E pipeline thay vì pytest thuần.
- Outbox retries forever-failed events không notify ops (silent). Cần alerting
  (Sprint 5: PagerDuty/email).

## Contributors

- @truong-newbie — author of all Sprint 4 commits
- Pre-commit secret scanner installed
- CI pipeline configured

## Links

- API spec: [docs/api-specification.md](docs/api-specification.md)
- Architecture: [docs/architecture.md](docs/architecture.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Sprint 4 issues: A5, A6, A7, A8, A9, A10
