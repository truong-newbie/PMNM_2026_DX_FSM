# 01 · Kế hoạch chi tiết — BACKEND

> **Owner**: Backend Dev · **Subtree sở hữu**: `services/ticket-service/**`, `services/notification-service/**`, `core/postgres/**`, `core/apisix/**`, `core/n8n/**`, `docker-compose.yml`, `Makefile`
> **Hiện trạng đọc ngày 0**: 636 LOC Python, 0 endpoint có auth, `POST /tickets` trả về placeholder, `services/ticket_service.py` chỉ có 2 dòng license header, `auth.py` 501 NotImplemented, `users/technicians` trả về `[]` cứng, model `TicketAttachment.file_size` khai báo `PGUUID` nhưng SQL là `BIGINT`.

---

## 0. Cam kết cá nhân

- Mỗi PR có test (happy path + 1 edge case).
- API mới hoặc đổi contract → cập nhật `04-integration-checklist.md` **cùng lúc** với commit.
- Không push secret, không hardcode `changeme`. Mọi secret phải qua env.
- Cuối mỗi ngày có 1 commit `chore(backend): daily-progress ngày X` ghi 1 dòng vào `CHANGELOG.md`.

---

## 1. Sprint backlog (theo ngày, tổng 14 ngày × 6–8 giờ/ngày)

### Ngày 1 (Mon) — Phân tích + dọn hiện trạng
- [ ] **B1.1** Sửa `models/ticket.py:70`: `file_size = Column(PGUUID)` → `Column(BigInteger)`. Push fix.
- [ ] **B1.2** `config.py:7`: `database_url` thành required env, raise nếu thiếu. Không default `changeme`.
- [ ] **B1.3** Tạo `services/ticket-service/.env.example` từ biến trong `config.py`.
- [ ] **B1.4** `core/postgres/init.sql`: thêm `CREATE EXTENSION IF NOT EXISTS pgcrypto;` đầu file (cần cho `gen_random_uuid`).
- [ ] **B1.5** `docker-compose.yml`: sửa CORS trong env ticket-service: `CORS_ORIGINS=http://localhost:3000,http://localhost`. Sửa `localhost:9180` (dev) → khớp với prod nginx proxy.
- [ ] **B1.6** Bổ sung `.env.example` ở root, đầy đủ tất cả biến cho cả team.
- [ ] **B1.7** Chạy thử `docker compose up -d postgres keycloak`, verify init.sql chạy thành công, Keycloak import realm OK.
- [ ] **B1.8** Tạo issue list ngày 1 trên GitHub: copy từ `04-integration-checklist.md` mục "API phải có".
- [ ] **B1.9** Review + approve PR sửa README "Vue 3" → "React" của AI.
- ✅ **Kết quả ngày 1**: DB schema chạy được, env clean, fix model mismatch.

### Ngày 2 (Tue) — Auth + skeleton CRUD
- [ ] **B2.1** Tạo `services/ticket-service/app/core/security.py`: hàm `get_current_user(authorization: str = Header(...))` — fetch JWKS từ Keycloak, decode JWT, raise 401 nếu invalid.
- [ ] **B2.2** Tạo `services/ticket-service/app/core/deps.py`: `require_role(*roles)` dependency.
- [ ] **B2.3** Wire auth vào `routes/tickets.py` (chưa enforce role, chỉ yêu cầu đăng nhập). Test bằng curl với token Keycloak.
- [ ] **B2.4** Sửa `routes/auth.py`: bỏ `/token` (frontend dùng Keycloak trực tiếp), giữ `/verify` và implement thật bằng `python-jose`.
- [ ] **B2.5** Sửa `routes/users.py`:
  - `/me` → trả user từ JWT (keycloak_id, username, role từ token).
  - `/technicians` → query DB có filter `is_available=true`, sort theo `current_load ASC`.
- [ ] **B2.6** Sửa `models/ticket_service.py` (file rỗng 1 dòng) → viết skeleton: `class TicketService` với các method async (chưa implement, chỉ signature + docstring + NotImplementedError rõ ràng).
- ✅ **Kết quả ngày 2**: Auth hoạt động, `/me` trả user thật, `/technicians` trả data thật.

### Ngày 3 (Wed) — Ticket CRUD thật
- [ ] **B3.1** Implement `services/ticket_service.py:create_ticket()`:
  - Validate category/priority theo enum.
  - Generate `ticket_number` qua `SELECT generate_ticket_number()`.
  - Insert vào DB, commit.
  - Dispatch sang `n8n_webhook_url/ticket-created`.
  - Write `ticket_history` row.
  - Return `TicketResponse` đầy đủ.
- [ ] **B3.2** Sửa `POST /tickets` route: thay placeholder bằng gọi `TicketService.create_ticket`. Thêm `Depends(get_current_user)`.
- [ ] **B3.3** Implement `services/ticket_service.py:get_ticket_by_id(id)`, `list_tickets(...)` có filter `customer_id`, `technician_id`, search `title ILIKE`, pagination metadata `{total, limit, offset, items}`.
- [ ] **B3.4** Thêm `PATCH /tickets/{id}` cho status transition (new → assigned → in_progress → resolved → closed) với rule:
  - new → assigned: cần `technician_id`
  - resolved → closed: cần role manager/admin
- [ ] **B3.5** Test:
  - `tests/test_tickets.py::test_create_ticket_full_flow` (create → assign → start → resolve → close).
  - `tests/test_tickets.py::test_create_ticket_unauthorized_returns_401`.
  - `tests/test_tickets.py::test_list_tickets_pagination_metadata`.
- ✅ **Kết quả ngày 3**: Tạo ticket end-to-end có DB, lịch sử, gọi n8n, RBAC.

### Ngày 4 (Thu) — Comments, attachments, Open-Core links
- [ ] **B4.1** `POST /tickets/{id}/comments` — body `{content, is_internal}`. Insert + write history.
- [ ] **B4.2** `GET /tickets/{id}/comments` — list comments theo ticket.
- [ ] **B4.3** `POST /tickets/{id}/attachments` (multipart) — gọi `storage_service.upload_attachment`, lưu row `ticket_attachments`, return `{id, file_name, url}`.
- [ ] **B4.4** `GET /tickets/{id}/attachments` — list, kèm presigned URL nếu muốn (bỏ qua nếu hết giờ).
- [ ] **B4.5** Fix `services/storage_service.py:24` — đổi `client.put_object(...)` (sync) sang `client.put_object` chạy trong `asyncio.to_thread(...)` để không block event loop. Hoặc thay `minio` package sang `minio-async`/`pyminio`.
- [ ] **B4.6** `core/n8n/workflows/ticket-intake.json` — verify webhook target endpoint là `POST http://ticket-service:8001/tickets/ai-result` (đã có trong file, chỉ cần test).
- [ ] **B4.7** `core/n8n/workflows/sla-monitor.json` — verify target `GET http://ticket-service:8001/tickets/overdue`. Implement endpoint này:
  - `GET /tickets/overdue` → query `SELECT * FROM tickets WHERE sla_deadline < NOW() AND status NOT IN ('resolved', 'closed')`.
- [ ] **B4.8** `core/n8n/workflows/ticket-assign.json` — verify target `POST http://ticket-service:8001/tickets/assign`. Implement:
  - `POST /tickets/assign` body `{ticket_id, technician_id}` → atomic update `tickets.technician_id`, `status='assigned`, `assigned_at=NOW()`, write history, dispatch notification webhook.
- ✅ **Kết quả ngày 4**: Comments + attachments + 3 endpoints n8n cần đều có. MinIO không block.

### Ngày 5 (Fri) — Stats + Dashboard endpoints
- [ ] **B5.1** `GET /tickets/stats/summary` — query view `v_ticket_stats`, trả full 11 fields. Sửa endpoint hiện tại chỉ trả `total`.
- [ ] **B5.2** `GET /tickets/stats/by-category` — query `v_tickets_by_category`.
- [ ] **B5.3** `GET /tickets/stats/technician-load` — query `v_technician_load`.
- [ ] **B5.4** `GET /tickets?technician_id=X&mine=true` — cho technician xem ticket của mình.
- [ ] **B5.5** Pagination response: trả `{items: [...], total, limit, offset, next}`.
- [ ] **B5.6** Add index `ix_tickets_technician_id_status` nếu chưa có trong init.sql.
- ✅ **Kết quả ngày 5**: Frontend có thể render dashboard thật, technician có view "My queue".

### Ngày 6 (Sat) — Notification + observability
- [ ] **B6.1** `services/notification-service/app/main.py` hiện rất sơ khai. Implement:
  - `POST /notify` body `{user_id, title, body, channel: 'inapp'|'email'}`.
  - In-memory queue hoặc table `notifications` (nếu có trong init.sql). Verify có không.
- [ ] **B6.2** Wire notification vào ticket create/assign flow: ticket-service POST sang notification-service (qua APISIX hoặc trực tiếp trong docker network).
- [ ] **B6.3** Add `structlog` vào ticket-service. Log mỗi request với `request_id`, `user_id`, `path`, `latency_ms`.
- [ ] **B6.4** Thêm middleware `request_id` (generate UUID nếu header thiếu, propagate sang downstream).
- [ ] **B6.5** Thêm `/metrics` endpoint với `prometheus-fastapi-instrumentator` (nếu thời gian cho phép).
- ✅ **Kết quả ngày 6**: Notification hoạt động, log có cấu trúc, request_id end-to-end.

### Ngày 7 (Sun) — Hardening, seed mở rộng
- [ ] **B7.1** Review + refactor: `services/ticket_service.py` đã có logic → tách thành `crud.py`, `workflows.py`, `search.py`.
- [ ] **B7.2** Mở rộng `core/postgres/init.sql` seed: tăng 50 → 200 tickets đa dạng status, thêm 100 history rows, thêm 50 comments.
- [ ] **B7.3** Thêm 1 ticket có `sla_deadline` trong quá khứ để demo `/tickets/overdue`.
- [ ] **B7.4** Thêm 1 ticket mỗi priority + category để demo AI classify.
- [ ] **B7.5** Add `tests/test_tickets_e2e.py` chạy với testcontainers + PostgreSQL thật (nếu đủ thời gian), hoặc mock DB đủ tốt với pytest-asyncio + httpx.
- [ ] **B7.6** Test coverage report: `pytest --cov=services/ticket-service/app` đạt ≥ 60% (lines).
- ✅ **Kết quả ngày 7**: Ticket-service ổn định, có test, có data demo phong phú.

### Ngày 8 (Mon) — APISIX polish, n8n test
- [ ] **B8.1** `core/apisix/routes.yaml` — kiểm tra từng route:
  - `/api/v1/tickets*` → upstream `ticket-service:8001` ✅ đã có.
  - `/api/v1/ai/*` → upstream `ai-service:8002` ✅.
  - Thêm `proxy-rewrite` plugin để strip `/api/v1` prefix.
- [ ] **B8.2** Thêm `keycloak-auth` plugin hoặc `jwt-auth` cho sensitive endpoints.
- [ ] **B8.3** Test toàn bộ routes bằng curl với token Keycloak admin.
- [ ] **B8.4** Test 3 workflow n8n bằng tay (qua UI n8n tại `:5678`):
  - Trigger `ticket-intake` bằng cách tạo 1 ticket qua API.
  - Verify AI classify xong, AI fields trong DB.
  - Trigger `ticket-assign` thủ công, verify gợi ý KTV.
  - Đợi cron `*/15 * * * *` chạy `sla-monitor` hoặc trigger thủ công.
- [ ] **B8.5** N8n workflow: thêm Slack/email node (mock endpoint, log ra stdout thay vì gửi thật).
- ✅ **Kết quả ngày 8**: Toàn bộ Open-Core routing + workflow chạy đúng.

### Ngày 9 (Tue) — Tích hợp AI ↔ Backend
- [ ] **B9.1** Verify `ai-service` đang chạy và trả 200.
- [ ] **B9.2** Test gọi `POST http://ai-service:8002/classify` từ ticket-service, lưu kết quả vào `tickets.ai_category`/`ai_priority`/`ai_confidence`.
- [ ] **B9.3** Test gọi `GET http://ai-service:8002/recommend?category=...&priority=...` từ ticket-service, lưu vào `ai_recommendation`.
- [ ] **B9.4** Bổ sung test integration: tạo ticket → assert AI fields được set trong 3 giây.
- [ ] **B9.5** Sửa `services/ticket-service/app/config.py:18` (`ai_service_url`) để dùng `http://ai-service:8002` (đúng nội bộ docker network).
- ✅ **Kết quả ngày 9**: AI ↔ Backend nối thẳng, ticket có AI fields.

### Ngày 10 (Wed) — End-to-end smoke
- [ ] **B10.1** Viết script `scripts/e2e_smoke.sh`: 
  1. Login Keycloak lấy token.
  2. Create user qua `/users` (nếu chưa có).
  3. POST /tickets.
  4. Đợi 2s, GET /tickets/{id} → verify có ai_category.
  5. PATCH /tickets/{id} status=assigned + technician_id.
  6. POST /tickets/{id}/comments.
  7. GET /tickets/stats/summary → verify counts tăng.
- [ ] **B10.2** Chạy smoke, fix bug phát sinh.
- [ ] **B10.3** Verify `GET /tickets?mine=true` với token user → chỉ trả ticket của user.
- [ ] **B10.4** Test concurrent assign: 2 request assign cùng ticket → chỉ 1 thành công (dùng `SELECT ... FOR UPDATE` trong transaction).
- ✅ **Kết quả ngày 10**: Backend ổn định cho tích hợp frontend.

### Ngày 11 (Thu) — Tích hợp full team
- [ ] **B11.1** Code freeze backend. Chỉ fix bug do frontend/AI báo.
- [ ] **B11.2** Pair với Frontend: debug API call nào fail → fix backend hoặc guide frontend.
- [ ] **B11.3** Pair với AI: verify AI endpoint trả đúng shape, fix nếu khác.
- [ ] **B11.4** Verify CORS: từ frontend gọi đến backend qua APISIX không bị block.
- [ ] **B11.5** Verify auth: token hết hạn → frontend redirect /login đúng.
- ✅ **Kết quả ngày 11**: 3 service tích hợp xong.

### Ngày 12 (Fri) — PoF hardening
- [ ] **B12.1** Quét toàn bộ file Python xem có SPDX header `Apache-2.0` chưa. Thêm nếu thiếu.
- [ ] **B12.2** Quét secret: `grep -rE "changeme|password.*=.*[a-z0-9]{6,}" services/ core/` → sửa hết, đưa vào `.env.example`.
- [ ] **B12.3** `git log --all --diff-filter=A -- services/ | grep -i secret` kiểm tra lịch sử commit không có secret.
- [ ] **B12.4** Tạo `DEPENDENCIES.md` liệt kê tất cả dep + license (pip-licenses --format=markdown).
- [ ] **B12.5** Bổ sung `.github/workflows/ci.yml` job `lint` (ruff), job `test` (pytest), job `secret-scan` (gitleaks).
- [ ] **B12.6** `Makefile` thêm target `make demo` = build + up + chờ healthy + in URL các service.
- [ ] **B12.7** `README.md` cập nhật: architecture diagram (đã sửa từ Vue → React), quick start 1 lệnh, tài khoản demo, link báo cáo + slide.
- ✅ **Kết quả ngày 12**: PoF đạt ≥ 40/50.

### Ngày 13 (Sat) — Release
- [ ] **B13.1** Fix tất cả bug từ ngày 12 test.
- [ ] **B13.2** `git tag -a v0.1.0 -m "DX-FSM v0.1.0 - DX-Lab prototype"`.
- [ ] **B13.3** `git push origin v0.1.0`.
- [ ] **B13.4** Tạo GitHub Release với notes copy từ `CHANGELOG.md`.
- [ ] **B13.5** Test build from source trên máy sạch (nếu có máy ảo, hoặc wipe Docker cache rồi `docker compose up -d --build`).
- [ ] **B13.6** Verify `docker compose down -v && docker compose up -d` chạy từ zero.
- ✅ **Kết quả ngày 13**: Có release v0.1.0 public.

### Ngày 14 (Sun) — Demo prep
- [ ] **B14.1** Rehearsal 3 lần demo 10 phút.
- [ ] **B14.2** Slide 1–3 (kiến trúc 3 tầng + Open-Core) do backend viết.
- [ ] **B14.3** Quay video demo 3–5 phút (tool: OBS hoặc ffmpeg).
- [ ] **B14.4** Hoàn thiện báo cáo kỹ thuật (8–10 trang) phần backend.
- [ ] **B14.5** Backup: snapshot DB trước demo để reset nhanh nếu cần.
- ✅ **Kết quả ngày 14**: Sẵn sàng demo.

---

## 2. Tiêu chí kỹ thuật bắt buộc

| Mục | Yêu cầu | Verify |
|---|---|---|
| Tất cả endpoint `/tickets/*`, `/users/*` | Có `Depends(get_current_user)` | `grep -L "Depends(get_current_user)" routes/*.py` trả empty |
| Mỗi model insert | Trong transaction | `async with session.begin():` |
| Mỗi external call (AI, n8n, MinIO) | Có timeout + retry 1 lần | `httpx.AsyncClient(timeout=10.0)` |
| Mỗi route | Có docstring + response model | OpenAPI `/docs` đầy đủ |
| Mỗi commit | Không có secret | CI fail nếu có |
| Mỗi file | SPDX header | `head -1 file.py` = `# SPDX-License-Identifier: Apache-2.0` |
| Mỗi route | Log request_id | `structlog` |

---

## 3. Cấu trúc code đề xuất (ngày 1)

```
services/ticket-service/app/
├── __init__.py
├── main.py
├── config.py
├── core/
│   ├── __init__.py
│   ├── security.py       # JWT verify, get_current_user
│   ├── deps.py           # require_role, pagination
│   ├── logging.py        # structlog config
│   └── middleware.py     # request_id
├── db/
│   ├── __init__.py
│   └── database.py
├── models/
│   ├── __init__.py
│   ├── enums.py
│   ├── ticket.py
│   └── user.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── health.py
│   ├── tickets.py
│   ├── comments.py       # mới
│   ├── attachments.py    # mới
│   ├── stats.py          # mới
│   └── users.py
├── services/
│   ├── __init__.py
│   ├── ticket_service.py # business logic
│   ├── notification.py   # gọi notification-service
│   ├── ai_client.py      # gọi ai-service
│   └── storage_service.py
└── schemas/              # mới: pydantic models
    ├── __init__.py
    ├── ticket.py
    ├── comment.py
    ├── attachment.py
    └── user.py
```

---

## 4. Endpoints tôi sẽ tạo (cross-check với 04)

| Method | Path | Role | Status ban đầu |
|---|---|---|---|
| GET | /health | public | ✅ |
| GET | /tickets | auth | ✅ stub |
| GET | /tickets/{id} | auth | ✅ |
| GET | /tickets/stats/summary | auth | ❌ stub |
| GET | /tickets/stats/by-category | auth | ❌ |
| GET | /tickets/stats/technician-load | manager | ❌ |
| GET | /tickets/overdue | auth | ❌ |
| POST | /tickets | auth | ❌ stub |
| PATCH | /tickets/{id} | auth (manager/tech) | ❌ |
| POST | /tickets/{id}/comments | auth | ❌ |
| GET | /tickets/{id}/comments | auth | ❌ |
| POST | /tickets/{id}/attachments | auth | ❌ |
| GET | /tickets/{id}/attachments | auth | ❌ |
| POST | /tickets/ai-result | service-to-service | ❌ |
| POST | /tickets/assign | service-to-service | ❌ |
| GET | /users/me | auth | ❌ stub |
| GET | /users/technicians | auth | ❌ stub |
| POST | /auth/verify | service-to-service | ❌ stub |

`❌` = cần implement trong 14 ngày.

---

## 5. Công cụ tôi dùng

- `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx` (test API)
- `testcontainers[postgresql]` (test với DB thật, nếu đủ time)
- `pip-licenses` (audit license)
- `ruff` (lint)
- `structlog` (logging)
- `prometheus-fastapi-instrumentator` (metrics, optional)
- `gitleaks` (CI secret scan)

---

## 6. Tôi sẽ review chéo

- Review mọi PR của Frontend liên quan `app/src/lib/api.ts` và `app/src/lib/store.ts` (vì contract API ở đây).
- Review mọi PR của AI liên quan `services/ai-service/app/routes/*` (vì gọi qua HTTP).

---

## 7. Khi nào tôi báo blocker

- Nếu AI service không trả shape như contract → báo trong issue `cross-team` với `ai` label trong 1 giờ.
- Nếu Frontend cần endpoint mới → estimate xong mở issue trong 4 giờ.
- Nếu DB schema cần đổi → tạo PR migration, ping cả team trong 4 giờ.
