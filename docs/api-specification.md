# DX-FSM API Specification

> **Last updated:** Sprint 4 (2026-01-15) — adds notes, history, admin endpoints.

## Base URL

```
http://localhost:8001          # ticket-service
http://localhost:8002          # ai-service
http://localhost:8080          # keycloak
```

Gateway (nginx) exposes all services under:

```
http://localhost:9180/api/v1
```

## Authentication

Sử dụng JWT Bearer token từ Keycloak:

```
Authorization: Bearer <access_token>
```

Token có 4 roles: `customer`, `technician`, `manager`, `admin`.

## Endpoints

### Health

```
GET /health
Response: { "status": "healthy" }
```

### Tickets

```
GET    /tickets
GET    /tickets/:id
POST   /tickets
PATCH  /tickets/:id
DELETE /tickets/:id
```

#### List Tickets

```
GET /tickets?status=new&priority=high&limit=50&offset=0

Response 200:
[
  {
    "id": "uuid",
    "ticket_number": "TKT-2025-000001",
    "title": "Tiêu đề ticket",
    "description": "Mô tả...",
    "category": "hardware",
    "priority": "high",
    "status": "new",
    "customer_name": "Khách Hàng Demo",
    "technician_name": null,
    "created_at": "2025-01-15T10:30:00Z",
    "sla_deadline": "2025-01-16T10:30:00Z"
  }
]
```

#### Create Ticket

```
POST /tickets
Content-Type: application/json

{
  "title": "Máy in không hoạt động",
  "description": "Đèn báo nhấp nháy cam",
  "category": "hardware",
  "priority": "medium",
  "customer_name": "Nguyễn Văn A",
  "customer_email": "nv-a@company.vn",
  "customer_phone": "0901234567",
  "customer_location": "Tòa A, Tầng 3"
}

Response 201:
{
  "id": "uuid",
  "ticket_number": "TKT-2025-000051"
}
```

#### Patch Ticket (status transition)

```
PATCH /tickets/{id}
Content-Type: application/json

{
  "status": "in_progress",
  "technician_id": "uuid-of-technician"
}

Response 200: { "id": "uuid", "status": "in_progress", ... }
```

**Status flow:** `new → assigned → in_progress → resolved → closed`
(manager/admin có thể revert). `cancelled` chỉ từ `new`/`assigned`.

### Comments (A3)

```
POST   /tickets/{id}/comments
GET    /tickets/{id}/comments
DELETE /tickets/{id}/comments/{comment_id}
```

#### Create Comment

```
POST /tickets/{id}/comments
Content-Type: application/json

{
  "content": "Đã restart switch, chờ phản hồi",
  "is_internal": false
}

Response 201: { "id": "uuid", "content": "...", "is_internal": false, ... }
```

- `is_internal=true` → chỉ staff (manager/technician/admin) thấy khi GET
- `is_internal=false` → customer + staff thấy
- Customer POST với `is_internal=true` → 403

#### List Comments

```
GET /tickets/{id}/comments

Response 200: [ { "id": "uuid", "content": "...", "is_internal": false, ... } ]
```

Sort: `created_at` ASC (chronological).

#### Delete Comment

```
DELETE /tickets/{id}/comments/{comment_id}
Response 204 (no body)
```

Permission: comment author OR manager/admin.

### Attachments (A3.3)

```
POST   /tickets/{id}/attachments
GET    /tickets/{id}/attachments
DELETE /tickets/{id}/attachments/{attachment_id}
```

Upload multipart/form-data với field `file`. Customer/technician/manager/admin
đều upload được. Quota: 25MB/file.

### Internal Notes (A5)

> Staff-only — dùng cho note nội bộ giữa team. Customer **không bao giờ** thấy,
> kể cả qua GET.

```
POST /tickets/{id}/notes
GET  /tickets/{id}/notes
```

#### Create Note

```
POST /tickets/{id}/notes
Content-Type: application/json

{
  "body": "Đã liên hệ vendor, ETA 24h"
}

Response 201: {
  "id": "uuid",
  "ticket_id": "uuid",
  "author_id": "uuid",
  "author_name": "Trần Văn Kỹ Thuật",
  "body": "Đã liên hệ vendor, ETA 24h",
  "created_at": "2026-01-15T14:30:00Z"
}
```

Permission:
- `technician` / `manager` / `admin` → 201
- `customer` → **403** "Notes are staff-only"

Validation: `body` không được empty/whitespace, max 5000 chars (422 nếu sai).

#### List Notes

```
GET /tickets/{id}/notes?limit=50

Response 200: [ { "id": "uuid", "body": "...", "author_name": "...", ... } ]
```

Sort: `created_at` ASC. Default `limit=50`, max 500.

### Ticket History (A9)

> Audit trail — xem lịch sử thay đổi của ticket.

```
GET /tickets/{id}/history
```

```
GET /tickets/{id}/history?limit=100&offset=0

Response 200: [
  {
    "id": "uuid",
    "action": "note_added",        // status_changed, comment_added, note_added, ...
    "actor": {
      "id": "uuid",
      "username": "tech-tran",
      "full_name": "Trần Văn Kỹ Thuật"
    },
    "old_value": "open",            // optional
    "new_value": "Note added by Trần Văn Kỹ Thuật",  // optional
    "metadata": { ... },            // optional, JSONB
    "created_at": "2026-01-15T14:30:00Z"
  }
]
```

Permission:
- Customer: chỉ thấy history của ticket mình sở hữu (403 nếu khác)
- Staff (technician/manager/admin): thấy tất cả

Sort: `created_at` ASC. Pagination: `limit` (max 500), `offset`.

### Admin: SLA & Outbox (A7, A8)

```
POST /admin/sla/check
POST /admin/outbox/run
GET  /admin/outbox
```

Permission: **admin/manager only**. Customer/technician → 403.

#### Trigger SLA Scan

```
POST /admin/sla/check

Response 200: {
  "scanned": 142,     // tickets quét
  "breached": 8,      // tickets vừa mark breach
  "dispatched": 8,    // outbox events dispatched
  "errors": 0
}
```

Quét tất cả ticket active có `sla_deadline < NOW()` và `sla_met IS NULL`,
set `sla_met=false`, enqueue outbox event để notify.

#### Trigger Outbox Run

```
POST /admin/outbox/run

Response 200: {
  "fetched": 15,    // events claimed
  "sent": 13,       // sent to n8n OK
  "retry": 2,       // failed → scheduled retry
  "failed": 0,      // exhausted retries
  "skipped": 0      // already locked
}
```

Worker chạy ngay 1 lần; loop vẫn chạy nền (default 30s interval).

#### List Outbox Events

```
GET /admin/outbox?status=pending&limit=50&offset=0

Response 200: [
  {
    "id": "uuid",
    "event_type": "ticket-created",
    "payload": { ... },
    "status": "pending",   // pending | sending | sent | failed
    "attempts": 0,
    "max_attempts": 5,
    "last_error": null,
    "next_retry_at": "2026-01-15T14:35:00Z",
    "created_at": "2026-01-15T14:30:00Z",
    "sent_at": null
  }
]
```

Filter: `status=pending|sending|sent|failed`.

### Users

```
GET /users/me
GET /users/technicians
```

### AI Classification

```
POST /classify
Content-Type: application/json

{
  "title": "Máy tính không bật được",
  "description": "Đã thử cắm nguồn nhiều lần"
}

Response 200: {
  "category": "hardware",
  "priority": "high",
  "confidence": 92.5,
  "recommendation": "Gửi đến bộ phận hardware"
}
```

Confidence scale: 0–100 (AI service) hoặc 0–1 (rule-based fallback). Caller
nên chấp nhận cả 2 scale.

## Error Responses

```json
{
  "error": "Error code",
  "message": "Human-readable message",
  "details": {}
}
```

| Status | Meaning |
|---|---|
| 400 | Bad Request – validation error |
| 401 | Unauthorized – missing/invalid token |
| 403 | Forbidden – insufficient permissions |
| 404 | Not Found |
| 422 | Unprocessable Entity – empty body, whitespace, etc. |
| 429 | Too Many Requests – rate limit exceeded |
| 500 | Internal Server Error |

## Auth + Role Matrix (Sprint 4)

| Endpoint | Customer | Technician | Manager | Admin |
|---|---|---|---|---|
| GET `/tickets` | ✓ own | ✓ | ✓ | ✓ |
| POST `/tickets` | ✓ | ✓ | ✓ | ✓ |
| PATCH `/tickets/{id}` (status) | ✗ | ✓ (limited) | ✓ | ✓ |
| POST `/tickets/{id}/comments` (public) | ✓ | ✓ | ✓ | ✓ |
| POST `/tickets/{id}/comments` (internal) | ✗ 403 | ✓ | ✓ | ✓ |
| DELETE `/tickets/{id}/comments/{id}` | owner only | owner only | ✓ | ✓ |
| POST `/tickets/{id}/attachments` | ✓ | ✓ | ✓ | ✓ |
| POST `/tickets/{id}/notes` | ✗ 403 | ✓ | ✓ | ✓ |
| GET `/tickets/{id}/notes` | ✗ 403 | ✓ | ✓ | ✓ |
| GET `/tickets/{id}/history` | own only | ✓ | ✓ | ✓ |
| POST `/admin/sla/check` | ✗ 403 | ✗ 403 | ✓ | ✓ |
| POST `/admin/outbox/run` | ✗ 403 | ✗ 403 | ✓ | ✓ |
| GET `/admin/outbox` | ✗ 403 | ✗ 403 | ✓ | ✓ |

## Notes

- All timestamps are ISO 8601 UTC.
- IDs are UUID v4.
- PATCH `/tickets/{id}` chỉ update status/assignee (không update title/desc sau khi tạo).
- Background workers (SLA monitor, outbox dispatcher) chạy song song với HTTP server.
