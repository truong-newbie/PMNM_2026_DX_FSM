# 00 · Quy ước chung & Cách 3 role phối hợp

> **Mục tiêu**: 3 thành viên (Backend / Frontend / AI) làm việc song song trên cùng repo DX-FSM, không đè file nhau, không chờ nhau quá 1 ngày, tích hợp cuối ngày 11.

---

## 1. Cấu trúc 3 bản kế hoạch

| File | Chủ sở hữu | Phạm vi |
|---|---|---|
| `docs/sprint/01-backend.md` | **Backend Dev** | `services/ticket-service/`, `core/postgres/`, `core/apisix/`, `core/n8n/`, `services/notification-service/` |
| `docs/sprint/02-frontend.md` | **Frontend Dev** | `app/` (React SPA), Dockerfile, nginx.conf |
| `docs/sprint/03-ai.md` | **AI Dev** | `services/ai-service/`, dataset, eval, Ollama integration |
| `docs/sprint/04-integration-checklist.md` | **Cả 3** | Hợp đồng API, test tích hợp, demo |

---

## 2. Nguyên tắc vàng — đọc kỹ trước khi bắt đầu

### 2.1. Mỗi người sở một subtree, KHÔNG đụng cây người khác

| Subtree | Owner | Quyền |
|---|---|---|
| `services/ticket-service/**` | Backend | toàn quyền |
| `services/notification-service/**` | Backend | toàn quyền |
| `core/postgres/**` | Backend | schema + seed |
| `core/apisix/**` | Backend | routes + plugins |
| `core/n8n/**` | Backend | workflow JSON (có thể ủy thác cho AI) |
| `app/**` | Frontend | toàn quyền |
| `services/ai-service/**` | AI | toàn quyền |
| `docker-compose.yml`, `Makefile` | **Backend** sở hữu, muốn đổi phải báo trước 1 ngày | |
| `docs/**`, `README.md`, `CLAUDE.md` | **AI** sở hữu tài liệu, **Cả 3** review trước khi commit | |
| `CHANGELOG.md` | mỗi người tự thêm dòng `[role] ngày X: ...` | |

**Ngoại lệ cần PR review**: bất kỳ thay đổi nào ở:
- `docker-compose.yml`
- `core/keycloak/realm-export.json`
- `core/postgres/init.sql`
- file mới ở `app/src/lib/` (shared module)

→ Tạo Pull Request, gắn label `cross-team`, chờ 1 reviewer từ team khác approve trong 4 giờ làm việc.

### 2.2. Hợp đồng API là bất di bất dịch

`docs/sprint/04-integration-checklist.md` chứa **API contract** — endpoint, request/response shape. Hai bên chỉ được đổi contract khi:
1. Mở issue `api-change-request` trước ít nhất 1 ngày.
2. Cả 3 đồng ý (1 thumbs-up trong issue).

Nếu không theo → coi như bug, người đổi phải sửa lại.

### 2.3. Quy ước commit message

```
[role] module: hành động ngắn gọn

Ví dụ:
[backend] tickets: thêm PATCH /tickets/{id}/assign
[frontend] tickets: trang CreateTicket với react-hook-form
[ai] classify: thêm Ollama fallback khi rule-based confidence < 0.6
[shared] docs: cập nhật API contract thêm trường sla_deadline
```

Mỗi commit phải build được (CI chạy `docker compose build`). Commit lỗi = chặn cả team.

### 2.4. Daily sync 15 phút — 9:00 sáng mỗi ngày

Format: mỗi người nói 2 phút:
- **Hôm qua làm gì** (1 dòng)
- **Hôm nay làm gì** (1 dòng)
- **Cản trở/blocker** (1 dòng, nếu có)

Output: cập nhật vào `docs/sprint/05-daily-log.md` (file chung, ai cũng có thể ghi).

---

## 3. Lộ trình 14 ngày (master plan)

| Ngày | Mốc chung | Backend | Frontend | AI |
|---|---|---|---|---|
| 1–2 | Phân tích + kiến trúc | Đọc code, fix `init.sql` (TicketAttachment.file_size), ký contract API | Đọc code, vẽ wireframe 4 trang, thống nhất với backend về API | Đọc code, chọn I-feature chính, viết eval set 20 case |
| 3–4 | Open-Core foundation | FastAPI auth (JWT), role guard, pgbouncer nếu cần | Fix auth token flow, login redirect, silent-check-sso.html | Scaffolding ai-service mới (recommend nâng cấp) |
| 5–7 | H-P-D-I core | CRUD tickets, comments, attachments, attachment MinIO, n8n fix endpoints | Trang list + detail + create + assign | RAG cho KB đơn vị đào tạo, semantic search |
| 8–10 | I + App + end-to-end | Stats endpoint, /overdue, /assign callback | Dashboard charts, layout Polish, i18n vi | Embed KB, integrate vào ticket detail |
| 11 | Tích hợp | Test E2E với frontend + AI, fix bug | Test E2E với backend + AI | Test E2E |
| 12 | Hardening PoF | License header, secret audit, README | License header, README screenshots | License header, model card |
| 13 | Release | Tag v0.1.0, fix bug release | Test prod build, fix UI bug | Eval report, model card |
| 14 | Demo | Rehearsal, slide, video | Slide deck, video | Slide deck (I section), video |

---

## 4. Definition of Done cho từng task

Một task được coi là xong khi **TẤT CẢ** điều kiện sau đúng:

- [ ] Code đã push lên branch `main` (hoặc feature branch đã merge).
- [ ] CI pass: `docker compose build` thành công, không có secret trong diff.
- [ ] Có test (nếu là logic) hoặc manual test screenshot (nếu là UI).
- [ ] Có dòng trong `CHANGELOG.md` theo format `[role] ngày X: ...`.
- [ ] Có entry trong `docs/sprint/05-daily-log.md` ngày hôm đó.
- [ ] Nếu đổi API → `docs/sprint/04-integration-checklist.md` đã cập nhật.

---

## 5. Công cụ cần dùng chung

| Mục đích | Công cụ | Ai sở hữu |
|---|---|---|
| Task tracking | GitHub Issues (label: `role:backend` / `role:frontend` / `role:ai` / `cross-team`) | Cả 3 |
| Realtime chat | GitHub Discussions hoặc Zalo/Mattermost tùy đội | — |
| Code review | GitHub PR (1 reviewer khác team nếu `cross-team`) | Cả 3 |
| CI | `.github/workflows/ci.yml` đã có, bổ sung thêm job lint | Backend |
| Demo build | `make demo` (cần bổ sung vào Makefile) | Backend |

---

## 6. Những mâu thuẫn hiện tại cần fix ngay ngày 1

| Mâu thuẫn | Ai fix | Deadline |
|---|---|---|
| README nói "Vue 3" nhưng code là React | Backend (sửa README.md) | Ngày 1 |
| CLAUDE.md nói 4 tầng, đề HaUI yêu cầu 3 tầng | AI (sửa CLAUDE.md, đồng bộ kiến trúc) | Ngày 1 |
| `docker-compose.yml` có `notification-service` port 8003 nhưng thư mục `services/notification-service/app/main.py` rất sơ khai | Backend (hoặc quyết định bỏ notification nếu không kịp) | Ngày 2 |
| CORS `allow_origins=["http://localhost:3000", "http://localhost:9180"]` — frontend thật ra đi qua nginx proxy `/api/` → APISIX `:80` | Backend (sửa CORS, thêm `http://localhost:3000, http://localhost`) | Ngày 2 |
| `services/ticket-service/app/config.py` hardcoded `dxfsm:changeme` | Backend (chuyển sang required env, fail-fast) | Ngày 1 |
| `services/ticket-service/app/routes/auth.py` 501 NotImplemented | Backend (gỡ route, frontend đi qua Keycloak trực tiếp) | Ngày 3 |
| `models/ticket.py:70` `file_size = Column(PGUUID)` nhưng init.sql là `BIGINT` | Backend | Ngày 1 |

---

## 7. Quy tắc "không làm kẹt người khác"

Khi bạn cần một thứ từ người khác, hãy:

1. **Mở issue** với label `cross-team` và gắn người đó.
2. **Stub nó ngay** trong code của bạn với TODO + comment `// @blocked-by #issue_number`.
3. **Đi tiếp** task khác, quay lại khi blocker xong.
4. Không bao giờ đợi blocker quá 4 giờ — nếu quá, ping trong daily sync.

---

## 8. Cấu trúc branch (tùy chọn, khuyến khích)

```
main                ← luôn build được
├── feat/feat-name  ← feature branch, mỗi người 1 branch độc lập
└── hotfix/...      ← fix bug khẩn
```

Nếu làm theo branch model: mỗi PR cần 1 reviewer (có thể là bất kỳ ai trong team, không cần đúng chuyên môn).

---

## 9. Tiêu chí thành công của cả đội (Definition of Done toàn đội)

- [ ] `docker compose up -d` chạy được trên máy mới trong < 5 phút.
- [ ] Đăng nhập SSO thành công, có token, gọi API 200.
- [ ] Tạo được ticket end-to-end, AI classify được, technician được gợi ý.
- [ ] Demo 10 phút chạy mượt, không cần restart service.
- [ ] Repo public trên GitHub, có LICENSE Apache 2.0 ở root và từng file có SPDX header.
- [ ] Có ≥ 1 release tag.
- [ ] README + CHANGELOG + CONTRIBUTING đầy đủ.
- [ ] Slide ≤ 12 trang, video demo 3–5 phút.
- [ ] Báo cáo kỹ thuật 8–10 trang.

---

Bây giờ đọc tiếp: **[01-backend.md](./01-backend.md)**, **[02-frontend.md](./02-frontend.md)**, **[03-ai.md](./03-ai.md)**, **[04-integration-checklist.md](./04-integration-checklist.md)**.
