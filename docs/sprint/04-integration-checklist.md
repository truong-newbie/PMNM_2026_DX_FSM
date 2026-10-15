# 04 · Hợp đồng tích hợp (API Contract) & Checklist chung

> **Mục đích**: file này là **nguồn sự thật duy nhất** cho mọi giao tiếp giữa 3 service. Khi một bên đổi API, cập nhật file này **cùng commit**. Mọi PR thay đổi API phải reference issue `api-change-request`.
>
> **Cập nhật lần cuối**: Ngày 0 (cần review ngày 1)

---

## 1. Topology

```
┌─────────────────┐
│   Browser       │  (Frontend - React)
│   :3000         │
└────────┬────────┘
         │ HTTPS (prod) / HTTP (dev)
         ▼
┌─────────────────┐
│   APISIX        │  Gateway
│   :80 (prod)    │  /api/v1/* → upstream
│   :9180 (admin) │
└────────┬────────┘
         │ http://service:port
    ┌────┼─────────┬──────────┐
    ▼    ▼         ▼          ▼
┌─────┐ ┌─────┐ ┌─────┐  ┌──────────┐
│Keycloak│ticket│  AI  │  │notification│
│ :8080│ :8001│ :8002│  │   :8003    │
└─────┘ └──┬──┘ └─────┘  └──────────┘
           │                ▲
           └────────────────┘
           (ticket-service gọi notification)
```

**Trong dev (chạy trực tiếp không qua Docker)**:
- Frontend gọi `http://localhost:9180/api/v1/...` (APISIX admin) — *nhưng đây là admin port, nên thực tế nên dùng `:80` (proxy) hoặc frontend gọi trực tiếp service để debug*.
- Trong docker compose, frontend gọi qua nginx proxy `/api/ → apisix:8080/api/`.

---

## 2. Authentication Contract

### 2.1. Token format
- Type: **JWT** (Keycloak RS256)
- Header: `Authorization: Bearer <access_token>`
- Token chứa: `sub` (keycloak_id), `preferred_username`, `email`, `realm_access.roles`
- TTL: 5 phút (default Keycloak). Refresh qua `keycloak.updateToken(30)`.

### 2.2. Service-to-service
- Dùng client credentials grant (Keycloak confidential client `dx-fsm-api`).
- Lưu token trong memory (không localStorage), refresh qua timer.

### 2.3. Frontend ↔ Keycloak
- Public client `dx-fsm-frontend`, PKCE S256.
- `silent-check-sso.html` phải tồn tại ở `app/public/`.

---

## 3. API Endpoints — Ticket Service (Backend sở hữu)

Base URL: `http://ticket-service:8001` (internal) hoặc `http://localhost:8001` (dev)

### 3.1. Tickets

#### `GET /tickets` — List tickets
**Auth**: required
**Query params**:
- `status` (optional): new | assigned | in_progress | pending | resolved | closed | cancelled
- `priority` (optional): low | medium | high | critical
- `category` (optional): hardware | software | network | electrical | other
- `technician_id` (optional, UUID)
- `customer_id` (optional, UUID)
- `q` (optional, search title)
- `mine` (optional, bool): nếu true → chỉ ticket của current user
- `limit` (default 20, max 100)
- `offset` (default 0)
- `sort_by` (optional): created_at | priority | sla_deadline
- `sort_dir` (optional): asc | desc

**Response 200**:
```json
{
  "items": [Ticket, ...],
  "total": 150,
  "limit": 20,
  "offset": 0,
  "next": "/tickets?offset=20&limit=20"
}
```

**Response Ticket**:
```json
{
  "id": "uuid",
  "ticket_number": "TKT-2026-00001",
  "title": "string",
  "description": "string",
  "status": "new",
  "priority": "high",
  "category": "network",
  "customer_id": "uuid",
  "customer_name": "string",
  "customer_email": "string",
  "technician_id": "uuid or null",
  "technician_name": "string or null",
  "ai_category": "network",
  "ai_priority": "high",
  "ai_confidence": 0.85,
  "ai_recommendation": "string",
  "sla_deadline": "2026-01-15T10:00:00Z",
  "sla_met": null,
  "created_at": "2026-01-15T09:00:00Z",
  "updated_at": "2026-01-15T09:00:00Z",
  "assigned_at": null,
  "resolved_at": null,
  "closed_at": null
}
```

#### `GET /tickets/{id}` — Get one
**Response 200**: Ticket
**Response 404**: `{"detail": "Ticket not found"}`

#### `POST /tickets` — Create
**Auth**: required
**Body**:
```json
{
  "title": "string (min 5)",
  "description": "string (min 10)",
  "category": "hardware | software | network | electrical | other",
  "priority": "low | medium | high | critical (default medium)",
  "customer_location": "string (optional)"
}
```
(customer_id/name/email lấy từ JWT)

**Response 201**: Ticket
**Side effects**:
- Gọi `POST /classify` (ai-service) → set ai_* fields.
- Dispatch n8n webhook `ticket-created`.
- Write history row.

#### `PATCH /tickets/{id}` — Update (status, assignment, etc.)
**Auth**: required (manager/technician)
**Body** (mọi field optional):
```json
{
  "status": "new | assigned | in_progress | pending | resolved | closed | cancelled",
  "technician_id": "uuid or null",
  "priority": "low | medium | high | critical",
  "category": "..."
}
```

**Response 200**: Ticket
**Errors**:
- 403: không đủ role
- 409: status transition không hợp lệ (vd: closed → new)
- 404: not found

#### `GET /tickets/stats/summary`
**Response 200**:
```json
{
  "total": 200,
  "by_status": {"new": 15, "in_progress": 8, ...},
  "by_priority": {"low": 50, "medium": 100, "high": 40, "critical": 10},
  "open": 23,
  "resolved_today": 5,
  "sla_compliance_pct": 87.5
}
```

#### `GET /tickets/stats/by-category`
**Response 200**:
```json
{
  "items": [
    {"category": "hardware", "count": 60, "avg_resolution_hours": 4.2},
    ...
  ]
}
```

#### `GET /tickets/stats/technician-load`
**Auth**: required (manager)
**Response 200**:
```json
{
  "items": [
    {"technician_id": "uuid", "name": "...", "current_load": 3, "max_concurrent": 5, "utilization_pct": 60},
    ...
  ]
}
```

#### `GET /tickets/overdue`
**Response 200**:
```json
{
  "items": [Ticket, ...],
  "count": 5
}
```

#### `POST /tickets/{id}/comments`
**Auth**: required
**Body**:
```json
{
  "content": "string",
  "is_internal": false
}
```

#### `GET /tickets/{id}/comments`
**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "username": "string",
      "content": "string",
      "is_internal": false,
      "created_at": "ISO"
    }
  ]
}
```

#### `POST /tickets/{id}/attachments` (multipart)
**Auth**: required
**Form**: `file: binary`
**Response 201**:
```json
{
  "id": "uuid",
  "file_name": "string",
  "file_size": 1024,
  "url": "http://minio:9000/attachments/...",
  "created_at": "ISO"
}
```

#### `GET /tickets/{id}/attachments`
**Response 200**: `{"items": [Attachment, ...]}`

#### `GET /tickets/{id}/history`
**Response 200**: `{"items": [HistoryRow, ...]}`

#### `POST /tickets/ai-result` (internal, gọi từ n8n/AI)
**Auth**: service-to-service
**Body**:
```json
{
  "ticket_id": "uuid",
  "ai_category": "network",
  "ai_priority": "high",
  "ai_confidence": 0.85,
  "ai_recommendation": "..."
}
```

#### `POST /tickets/assign` (internal, gọi từ n8n)
**Auth**: service-to-service
**Body**:
```json
{
  "ticket_id": "uuid",
  "technician_id": "uuid"
}
```

---

## 4. API Endpoints — AI Service (AI sở hữu)

Base URL: `http://ai-service:8002`

### 4.1. `POST /classify`
**Auth**: required
**Body**:
```json
{
  "title": "string",
  "description": "string (optional)"
}
```

**Response 200**:
```json
{
  "category": "network",
  "priority": "high",
  "confidence": 0.85,
  "recommendation": "string",
  "method": "rule | llm | hybrid",
  "reasoning": "string"
}
```

**Errors**:
- 422: validation
- 503: ai-service down + fallback fail (lạ, vì rule-based lúc nào cũng chạy được)

### 4.2. `GET /recommend`
**Auth**: required
**Query**:
- `ticket_id` (uuid)
- `category` (string)
- `priority` (string)

**Response 200**:
```json
{
  "items": [
    {
      "technician_id": "uuid",
      "technician_name": "string",
      "employee_code": "TECH001",
      "specialty": ["hardware", "electrical"],
      "current_load": 2,
      "max_concurrent": 5,
      "score": 0.87,
      "reason": "KTV có chuyên môn về network, hiện đang rảnh (load 2/5)"
    }
  ]
}
```

### 4.3. `POST /solution`
**Auth**: required
**Body**:
```json
{
  "title": "string",
  "description": "string",
  "category": "string (optional)"
}
```

**Response 200**:
```json
{
  "solution": "string (≤ 200 từ tiếng Việt)",
  "sources": [
    {"file": "kb/wifi-troubleshoot.md", "score": 0.82, "snippet": "..."}
  ],
  "confidence": 0.8,
  "method": "rag | fallback | none"
}
```

### 4.4. `POST /duplicate`
**Auth**: required
**Body**: giống `/classify`
**Response 200**:
```json
{
  "items": [
    {
      "ticket_id": "uuid",
      "ticket_number": "TKT-2026-00012",
      "title": "...",
      "similarity_score": 0.91
    }
  ]
}
```

### 4.5. `POST /duplicate/index` (internal)
**Auth**: service-to-service
**Body**:
```json
{
  "ticket_id": "uuid",
  "title": "string",
  "description": "string"
}
```

### 4.6. `POST /summary`
**Auth**: required
**Body**:
```json
{
  "ticket_id": "uuid or content"
}
```

**Response 200**:
```json
{
  "summary": "string (≤ 50 từ)",
  "word_count": 45,
  "method": "llm | rule"
}
```

### 4.7. `GET /health`
**Response 200**:
```json
{
  "status": "healthy",
  "ollama_reachable": true,
  "qdrant_doc_count": 15,
  "qdrant_ticket_count": 50,
  "model": "llama3.2:3b"
}
```

---

## 5. API Endpoints — Notification Service (Backend sở hữu)

Base URL: `http://notification-service:8003`

### 5.1. `POST /notify` (internal)
**Auth**: service-to-service
**Body**:
```json
{
  "user_id": "uuid",
  "title": "string",
  "body": "string",
  "channel": "inapp | email | both",
  "link": "string (optional, vd: /tickets/123)"
}
```

### 5.2. `GET /notifications/me`
**Auth**: required
**Query**: `unread_only` (bool), `limit`, `offset`
**Response**: `{"items": [Notification, ...], "unread_count": 3}`

### 5.3. `POST /notifications/{id}/read`
**Auth**: required

---

## 6. API Endpoints — Keycloak (qua frontend)

Frontend KHÔNG gọi trực tiếp Keycloak admin API. Chỉ dùng:
- Login redirect (qua keycloak-js).
- Token refresh (qua keycloak-js updateToken).
- User info (keycloak.loadUserInfo).

---

## 7. CORS & Security Headers

| Header | Value | Ai set |
|---|---|---|
| `Access-Control-Allow-Origin` | `http://localhost:3000` (dev), `https://demo.dxfsm.vn` (prod) | Backend |
| `Access-Control-Allow-Credentials` | `true` | Backend |
| `Access-Control-Allow-Headers` | `Authorization, Content-Type` | Backend |
| `Strict-Transport-Security` | `max-age=31536000` (prod) | nginx |
| `X-Content-Type-Options` | `nosniff` | nginx |
| `X-Frame-Options` | `DENY` | nginx |

---

## 8. Environment Variables (một lần duy nhất)

### 8.1. `services/ticket-service/.env`
```bash
DATABASE_URL=postgresql://dxfsm:CHANGEME@postgres:5432/dxfsm
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=dx-fsm
KEYCLOAK_CLIENT_ID=dx-fsm-api
KEYCLOAK_CLIENT_SECRET=CHANGEME
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=CHANGEME
MINIO_SECRET_KEY=CHANGEME
MINIO_BUCKET=attachments
AI_SERVICE_URL=http://ai-service:8002
NOTIFICATION_SERVICE_URL=http://notification-service:8003
N8N_WEBHOOK_URL=http://n8n:5678/webhook
CORS_ORIGINS=["http://localhost:3000","http://localhost"]
LOG_LEVEL=INFO
```

### 8.2. `services/ai-service/.env`
```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.2:3b
ENABLE_AI=true
QDRANT_URL=http://qdrant:6333
REQUEST_TIMEOUT=60
LOG_LEVEL=INFO
```

### 8.3. `services/notification-service/.env`
```bash
DATABASE_URL=postgresql://dxfsm:CHANGEME@postgres:5432/dxfsm
SMTP_HOST=CHANGEME (optional)
LOG_LEVEL=INFO
```

### 8.4. `app/.env` (cho Vite)
```bash
VITE_API_BASE_URL=/api/v1
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=dx-fsm
VITE_KEYCLOAK_CLIENT_ID=dx-fsm-frontend
```

### 8.5. `docker-compose.yml` root
```bash
APISIX_ADMIN_KEY=CHANGEME
POSTGRES_PASSWORD=CHANGEME
KEYCLOAK_ADMIN_PASSWORD=CHANGEME
MINIO_ROOT_PASSWORD=CHANGEME
N8N_BASIC_AUTH_PASSWORD=CHANGEME
```

**Không commit `.env` thật. Chỉ commit `.env.example`.**

---

## 9. Database schema (chốt cuối cùng, không đổi)

Xem `core/postgres/init.sql`. Mọi thay đổi cần PR riêng với label `db-migration`.

Cảnh báo đã biết:
- `models/ticket.py:70` `TicketAttachment.file_size` khai báo PGUUID (BUG), phải là BigInteger. **Backend fix ngày 1.**

---

## 10. Checklist tích hợp (dùng cho ngày 11)

### 10.1. End-to-end scenarios

#### Scenario A: Customer tạo ticket
- [ ] Frontend: Login SSO thành công (token có)
- [ ] Frontend: POST /tickets
- [ ] Backend: validate, insert DB, generate ticket_number
- [ ] Backend: gọi ai-service /classify
- [ ] AI: return category/priority, backend lưu vào ai_* fields
- [ ] Backend: dispatch n8n webhook
- [ ] Backend: return Ticket với ai_* fields
- [ ] Frontend: redirect tới /tickets/{id}
- [ ] Frontend: hiển thị ticket + AI suggestion

#### Scenario B: Manager phân công
- [ ] Frontend: GET /users/technicians → list
- [ ] Frontend: mở AssignModal, click "Gợi ý AI"
- [ ] Frontend: GET /recommend?category=... → top 3 KTV
- [ ] Frontend: hiển thị với score + reason
- [ ] Manager: chọn 1 KTV → PATCH /tickets/{id}
- [ ] Backend: update technician_id, status=assigned, history row
- [ ] Backend: gọi notification-service
- [ ] Frontend: refresh, thấy assigned

#### Scenario C: Technician xem ticket và resolve
- [ ] Frontend: GET /tickets?mine=true → chỉ ticket assigned cho mình
- [ ] Frontend: click ticket → detail
- [ ] Frontend: click "Bắt đầu" → PATCH status=in_progress
- [ ] Frontend: click "Upload ảnh" → POST /tickets/{id}/attachments (multipart)
- [ ] Frontend: click "Đã giải quyết" → PATCH status=resolved
- [ ] Frontend: click "AI gợi ý giải pháp" → POST /solution → hiển thị solution + sources

#### Scenario D: SLA monitor
- [ ] n8n cron mỗi 15 phút trigger
- [ ] n8n: GET /tickets/overdue
- [ ] n8n: nếu count > 0, POST /notify user role=manager
- [ ] Manager login thấy notification bell có badge

### 10.2. Failure scenarios

- [ ] Ollama offline: AI trả `method: "rule"`, ticket vẫn classify được.
- [ ] Qdrant offline: AI /solution trả `method: "none"`, sources rỗng.
- [ ] Backend offline: frontend toast lỗi, không crash.
- [ ] Token hết hạn giữa session: frontend refresh tự động, không redirect /login.
- [ ] Network chậm: frontend skeleton, không flash "không có data".
- [ ] DB chưa seed: backend trả 0 ticket, frontend empty state OK.

---

## 11. Test scripts (chạy được, ai cũng dùng được)

### 11.1. `scripts/smoke.sh`
```bash
#!/bin/bash
# Smoke test toàn stack
set -e

echo "1. Check services up..."
for svc in postgres keycloak apisix ticket-service ai-service; do
  docker compose ps $svc | grep -q "Up" || { echo "FAIL: $svc not up"; exit 1; }
done

echo "2. Get token from Keycloak..."
TOKEN=$(curl -s -X POST http://localhost:8080/realms/dx-fsm/protocol/openid-connect/token \
  -d "grant_type=password" -d "client_id=dx-fsm-frontend" \
  -d "username=manager@haui.vn" -d "password=${MANAGER_PASSWORD:?set in .env}" \
  | jq -r .access_token)

echo "3. List tickets..."
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8001/tickets | jq

echo "4. AI classify..."
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Wifi mất","description":"phòng A1"}' \
  http://localhost:8002/classify | jq

echo "✅ Smoke OK"
```

### 11.2. `scripts/seed.sh`
```bash
# Chạy lại seed DB, Qdrant
docker compose exec postgres psql -U dxfsm -d dxfsm -c "TRUNCATE tickets CASCADE; INSERT INTO tickets (...) SELECT * FROM (...)"
docker compose exec ai-service python -m scripts.seed_vectors
```

---

## 12. Lịch sử thay đổi contract

| Ngày | Bởi | Thay đổi |
|---|---|---|
| 0 | (init) | Phiên bản đầu tiên |

(Cập nhật mỗi lần đổi API. Khi đổi, ping cả 3 role trong daily sync.)
