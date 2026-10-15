# DX-FSM Architecture Document

## 1. Tổng quan

DX-FSM (Digital Transformation Field Service Management) là nền tảng quản lý dịch vụ thực địa được thiết kế theo mô hình Open-Core với 4 tầng nghiệp vụ.

## 2. Mô hình 4 tầng

### Tầng 1: Open-Core (Infrastructure)
Cung cấp các service nền tảng, không có UI người dùng.

- **Keycloak**: Identity Provider, SSO, Role-Based Access Control
- **APISIX**: API Gateway, authentication, rate limiting, routing
- **PostgreSQL**: Primary database, JSONB support
- **MinIO**: Object storage cho file đính kèm
- **n8n**: Workflow automation engine

### Tầng 2: H-P-D-I (Service Tier)
Các microservice xử lý nghiệp vụ chính.

```
ticket-service          → Core CRUD, business logic
  ├─ Ticket management (create, update, status transitions)
  ├─ Comments + Attachments (MinIO integration)
  ├─ Internal Notes (staff-only, A5)
  ├─ User/Tech management (Keycloak sync)
  ├─ SLA calculation (rules-based: 15min/1h/4h/24h)
  ├─ SLA monitor background loop (A7)
  ├─ Outbox dispatcher (n8n delivery, A8)
  ├─ Audit logging (ticket_history)
  └─ History API (A9)

ai-service             → AI-powered features
  ├─ Rule-based classification (keyword matching)
  ├─ Ollama LLM integration (optional, Sprint 4: cache + fallback)
  ├─ Technician recommendation
  └─ Priority detection

notification-service    → Multi-channel notifications
  └─ Future: Email, SMS, Push
```

### Tầng 3: User Interface
React SPA với TanStack Query, React Router, Zustand.

- **Dashboard**: KPI, thống kê real-time
- **Tickets**: CRUD interface với filter, search, pagination
- **Profile**: Thông tin user, settings

### Tầng 4: Intelligence
Các module AI/ML tùy chọn.

- Rule-based classifier (luôn bật)
- Ollama LLM integration (tùy chọn)
- RAG cho knowledge base (tương lai)

## 3. Data Model

```
┌─────────────┐     ┌─────────────┐
│   users     │────<│ technicians  │
│ (Keycloak) │     │ (extended)   │
└─────────────┘     └──────────────┘
       │
       │ creates
       ▼
┌─────────────────────────────────────┐
│             tickets                 │
│ (core entity)                      │
├─────────────────────────────────────┤
│ Comments │ Attachments │ History   │
└─────────────────────────────────────┘
```

## 4. Security

- **Authentication**: Keycloak OpenID Connect
- **Authorization**: Role-based (admin, manager, technician, customer)
- **API Security**: JWT validation tại APISIX gateway
- **Data**: TLS in transit, encrypted volumes at rest

## 5. Scalability

- **Stateless services**: Mỗi service có thể scale horizontal
- **Database**: PostgreSQL connection pooling
- **Caching**: APISIX proxy cache cho read-heavy endpoints
- **Object storage**: MinIO distributed mode cho production

## 6. Deployment

Single-node Docker Compose cho development và demo.
Multi-node Kubernetes cho production (tương lai).

## 7. Sprint 4 Patterns

### 7.1 Outbox Pattern (A8)

Đảm bảo event delivery tới n8n **exactly-once** ngay cả khi n8n down.

```
┌──────────────────┐    ┌──────────────┐    ┌────────┐
│ HTTP Request     │ →  │ outbox_events│ ←  │ Worker │
│ (tạo ticket,     │    │ status=      │    │ (30s   │
│  status change)  │    │  pending     │    │  loop) │
└──────────────────┘    │  attempts=N  │    └────┬───┘
                        └──────────────┘         │
                                                  ▼
                                         ┌─────────────────┐
                                         │ n8n webhook      │
                                         │ (workflow)       │
                                         └─────────────────┘
```

**Cơ chế:**
1. Tại commit time, INSERT row vào `outbox_events` cùng transaction với
   domain change → atomic.
2. Worker loop (30s) claim events pending (`UPDATE ... WHERE status='pending'
   RETURNING *`) — atomic claim, không có 2 worker cùng xử lý.
3. POST tới n8n webhook; nếu 2xx → status `sent`; nếu fail → attempts++,
   set `next_retry_at` theo backoff.
4. Sau 5 attempts → status `failed`, không retry.

**Backoff schedule:** 5s → 25s → 125s → 625s → 3125s (5x progression).
Đảm bảo n8n downtime 1h+ không gây retry storm.

**Lợi ích so với direct HTTP call:**
- DB write + event delivery trong cùng transaction
- Retry persistent qua restart
- Dead-letter (`failed` status) để ops investigate
- Không block HTTP response (enqueue = 1 INSERT)

### 7.2 AI Classifier với Cache + Fallback (A6)

Hybrid strategy: AI service khi available, rule-based khi down.

```
Request → check cache (hash title+desc)
            ↓ miss
         call AI service (timeout 5s)
            ↓ 2xx
         cache + return (method='ai')
            ↓ 5xx / timeout
         rule-based (method='fallback')
         confidence 0-1
```

**Lợi ích:**
- Resilient: AI service down → vẫn classify được (rule-based)
- Performance: repeated ticket titles (vd. "Máy in lỗi") → cache hit
- Transparent: caller nhận `method` field để biết classification nguồn nào

**Confidence scale:**
- AI service: 0-100 (percentage)
- Rule-based: 0-1 (ratio)
- Caller normalize về 0-1 trước khi so sánh

### 7.3 SLA Monitor Background Loop (A7)

Reactive + scheduled:

```
Startup → spawn asyncio task
           ↓ every 5min
         SELECT tickets WHERE sla_deadline < NOW()
                          AND status IN (active states)
                          AND sla_met IS NULL
           ↓ for each overdue ticket
         UPDATE tickets SET sla_met=false
         INSERT outbox_event (ticket.sla_breached)
           ↓ n8n notifies customer + manager
```

**Tại sao background thay vì check mỗi request:**
- 1 lần query thay vì N lần
- Không block user request
- Idempotent: skip tickets đã mark breach

### 7.4 Internal Notes (A5) vs Comments

| Feature | Comments | Notes |
|---|---|---|
| Audience | Customer + staff | Staff only |
| `is_internal` flag | Yes (per-comment) | Always true |
| GET customer | Filtered (no internal) | **403 always** |
| Use case | Discussion với customer | Team-only context, escalation notes |
| Audit | `comment_added/removed` | `note_added` |

Cả 2 cùng write vào `ticket_history` để audit trail.

### 7.5 Data Model Updates (Sprint 4)

```
┌──────────────────┐
│      users       │
│  (keycloak_id)   │
└──────────────────┘
        │
        │ creates
        ▼
┌──────────────────────────────────────┐
│              tickets                 │
│  + sla_met (boolean, nullable)       │  ← Sprint 4
└──────────────────────────────────────┘
        │       │          │
        │       │          │
        ▼       ▼          ▼
  ┌─────────┐ ┌──────────┐ ┌──────────────┐
  │ comments│ │ attach-  │ │ ticket_notes │  ← Sprint 4
  │ (public/│ │ ments    │ │ (staff-only) │
  │ internal)│ │ (files) │ └──────────────┘
  └─────────┘ └──────────┘
        │       │          │
        └───────┴──────────┘
                │
                ▼
        ┌─────────────────┐
        │ ticket_history  │  ← A9: exposed via API
        │ (audit log)     │
        └─────────────────┘

┌──────────────────┐         ┌──────────────────┐
│  outbox_events   │  ←──→   │ n8n (external)   │
│  (A8)            │         │ workflow engine  │
└──────────────────┘         └──────────────────┘
```

### 7.6 User Provisioning

Keycloak là source of truth cho identity. Local `users` table cache để
foreign key references (ticket.customer_id, history.user_id, etc.).

```
First request from Keycloak user
  → resolve_or_create_user(db, token_user)
    → lookup by keycloak_id
      ↓ miss
    → lookup by username (legacy seed fallback)
      ↓ miss
    → INSERT new user với role từ JWT
```

Idempotent, an toàn race condition vì unique key `keycloak_id`.
