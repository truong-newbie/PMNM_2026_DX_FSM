# 02 · Kế hoạch chi tiết — FRONTEND

> **Owner**: Frontend Dev · **Subtree sở hữu**: `app/**` (toàn bộ), `app/Dockerfile`, `app/nginx.conf`
> **Hiện trạng đọc ngày 0**: 549 LOC TypeScript, 4 trang (Login, Dashboard, Tickets, TicketDetail), không có trang Create, không có form, không có filter, không có loading/error state tốt, inline style toàn bộ, dùng `react-hook-form` nhưng chưa import, `silent-check-sso.html` không tồn tại, Layout sidebar cứng.

---

## 0. Cam kết cá nhân

- Mỗi trang mới có loading skeleton + error state + empty state.
- Mỗi form có validation + aria-label + keyboard navigation.
- Mỗi commit không phá build (`npm run build` pass).
- Cuối mỗi ngày có 1 commit `chore(frontend): daily-progress ngày X`.

---

## 1. Stack quyết định (ngày 1)

| Mục | Chọn | Lý do |
|---|---|---|
| UI library | **Không thêm** (giữ inline + CSS module) | Tránh phụ thuộc nặng, demo focus, đã có Login.module.css |
| Icons | **`lucide-react`** (~50KB) | Nhẹ, tree-shake được |
| Form | **`react-hook-form`** (đã cài) | Không cần thêm |
| Date | **`date-fns`** (~20KB) | Nhỏ, tree-shake, vi-VN locale có sẵn |
| Chart | **`recharts`** (~100KB) | Cho dashboard, demo-friendly |
| i18n | **`react-i18next` + `i18next-browser-languagedetector`** | Đề HaUI đánh giá UX cao |
| Toast | **`sonner`** (~10KB) | Nhẹ, đẹp, accessible |
| Test | **`vitest` + `@testing-library/react` + `jsdom`** | Đã có vitest, thêm RTL |

> **Nếu hết giờ**, bỏ qua i18n + chart, dùng text cứng tiếng Việt + 4 số liệu.

---

## 2. Sprint backlog (theo ngày)

### Ngày 1 (Mon) — Setup + Auth fix
- [ ] **F1.1** Fix `app/src/lib/auth.ts:13`: thêm `pkceMethod: 'S256'` (keycloak-js v26 mặc định nhưng ghi rõ).
- [ ] **F1.2** Tạo `app/public/silent-check-sso.html`:
  ```html
  <html><body><script>parent.postMessage(location.href, location.origin)</script></body></html>
  ```
- [ ] **F1.3** Fix `app/src/lib/auth.ts:23` (`getToken`): đổi tên thành `getAccessToken`, trả về `keycloak.tokenParsed` nếu cần. **Sửa `AuthGuard.tsx:16`** — đọc token từ `keycloak.token` (KHÔNG phải localStorage).
- [ ] **F1.4** Sửa `app/src/lib/api.ts:15` — đọc token từ `keycloak.token`, fallback in-memory cache.
- [ ] **F1.5** Fix `app/src/lib/store.ts:13` — bỏ `JSON.parse(localStorage.getItem('user') || 'null')` ở module load. Chỉ parse khi `setAuth` được gọi. Throw an toàn.
- [ ] **F1.6** Thêm `keycloak.updateToken(30)` timer 60s trong `App.tsx` để refresh token.
- [ ] **F1.7** `.env.example` cho `app/`: `VITE_API_BASE_URL`, `VITE_KEYCLOAK_URL`, `VITE_KEYCLOAK_REALM`, `VITE_KEYCLOAK_CLIENT_ID`.
- [ ] **F1.8** `package.json`: thêm `lucide-react`, `sonner`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`. Không thêm nếu không dùng tới.
- [ ] **F1.9** Setup `vitest.config.ts` + `src/test/setup.ts`.
- ✅ **Kết quả ngày 1**: Auth flow thật sự chạy, token tới backend.

### Ngày 2 (Tue) — Layout + routing polish
- [ ] **F2.1** `app/src/components/Layout.tsx`: thêm top bar (logo + user menu + logout).
- [ ] **F2.2** Thêm role-aware nav:
  - Customer: Dashboard, "Tạo ticket", "Ticket của tôi"
  - Technician: Dashboard, "Ticket của tôi", "Đã phân công"
  - Manager: Dashboard, "Tất cả ticket", "Phân công", "Báo cáo"
- [ ] **F2.3** Active state dùng `aria-current` + focus ring rõ ràng.
- [ ] **F2.4** `App.tsx`: thêm route `/tickets/new`, `/tickets/:id/edit` (stub nếu chưa làm).
- [ ] **F2.5** Thêm `NotFound.tsx` cho 404.
- [ ] **F2.6** Thêm `<Toaster />` (sonner) vào root.
- [ ] **F2.7** Test 1 case: render `<App />` với mock user, expect có sidebar.
- ✅ **Kết quả ngày 2**: Layout production-grade, role-aware, accessible cơ bản.

### Ngày 3 (Wed) — Tickets list + filters
- [ ] **F3.1** `app/src/pages/Tickets.tsx`: thêm search input (filter `title` client-side, dùng `useMemo`).
- [ ] **F3.2** Filter dropdown: status, priority, category. Multi-select.
- [ ] **F3.3** Sort by `created_at` desc / `priority` asc / `sla_deadline` asc.
- [ ] **F3.4** Pagination: page size 20, page selector.
- [ ] **F3.5** Empty state có nút "Tạo ticket đầu tiên".
- [ ] **F3.6** Loading state: skeleton table.
- [ ] **F3.7** Error state: toast + retry button.
- [ ] **F3.8** Thêm 3 file test: filter, search, empty.
- ✅ **Kết quả ngày 3**: Tickets page production-ready.

### Ngày 4 (Thu) — Create ticket + form
- [ ] **F4.1** Tạo `app/src/pages/TicketCreate.tsx`:
  - Form: title, description (textarea), category (select), priority (select), location.
  - Submit gọi `ticketApi.create` → on success redirect `/tickets/{id}`.
  - Validation: title min 5, description min 10, required fields.
  - Dùng `react-hook-form` + native validation (không cần yup/zod để giảm bundle).
- [ ] **F4.2** Thêm route `/tickets/new` trong `App.tsx` (sửa ngày 2 đã stub).
- [ ] **F4.3** `app/src/lib/api.ts`: thêm `attach(file)`, `comments.list/post`, `users.technicians`, `ai.classify` (xem ngày 5).
- [ ] **F4.4** Trên trang create: thêm nút "AI gợi ý category/priority" → gọi `ai.classify(title, description)`, auto-fill nếu confidence > 0.7.
- [ ] **F4.5** Test: form submit với validation fail + happy path.
- ✅ **Kết quả ngày 4**: Tạo được ticket end-to-end.

### Ngày 5 (Fri) — Ticket detail + actions
- [ ] **F5.1** `app/src/pages/TicketDetail.tsx`: thêm sections:
  - Header: ticket number, status badge, priority.
  - Meta: created, customer, technician, SLA countdown.
  - Description: text.
  - AI Insights: card hiển thị `ai_category/priority/confidence/recommendation`.
  - History timeline: list rows từ `/tickets/{id}/history` (cần backend thêm endpoint).
  - Comments: list + form post.
  - Attachments: list + upload.
- [ ] **F5.2** Action buttons theo role:
  - Customer: "Đóng ticket" (nếu resolved).
  - Technician: "Nhận", "Bắt đầu", "Đã giải quyết", "Upload ảnh".
  - Manager: tất cả + "Phân công lại" (modal chọn KTV).
- [ ] **F5.3** Modal "Phân công" hiển thị danh sách `users/technicians` với `current_load / max_concurrent_tickets`, highlight technician có load thấp nhất.
- [ ] **F5.4** Hiển thị nút "AI gợi ý" → gọi `ai/recommend` → show modal kết quả với `reason`, `score`, `specialty`.
- [ ] **F5.5** Loading + error + empty cho từng section.
- ✅ **Kết quả ngày 5**: Ticket detail có mọi action, AI có mặt.

### Ngày 6 (Sat) — Dashboard + charts
- [ ] **F6.1** `app/src/pages/Dashboard.tsx`:
  - 4 StatCard (giữ nguyên) + thêm 4 KPI: open, overdue, avg resolution time, SLA compliance %.
  - Bảng: top 5 KTV theo current_load (gọi `/tickets/stats/technician-load`).
  - Bảng: tickets overdue (gọi `/tickets/overdue`).
  - Bar chart: tickets by category (recharts, gọi `/tickets/stats/by-category`).
  - Line chart: ticket created last 30 days (gọi extension backend hoặc tự aggregate).
- [ ] **F6.2** Refresh button + auto-refresh mỗi 60s.
- [ ] **F6.3** Loading + error cho từng chart.
- [ ] **F6.4** Date range picker (tuần/tháng/quý) — optional, làm nếu còn time.
- ✅ **Kết quả ngày 6**: Dashboard production-grade.

### Ngày 7 (Sun) — i18n + a11y + UX polish
- [ ] **F7.1** Setup i18next: `src/i18n/vi.json`, `src/i18n/en.json`. Move tất cả string cứng sang `t('key')`.
- [ ] **F7.2** Language switcher trong top bar (vi/en).
- [ ] **F7.3** A11y pass:
  - Mỗi interactive element có `aria-label`.
  - Focus visible.
  - Tab order đúng.
  - Form errors có `aria-invalid` + `aria-describedby`.
- [ ] **F7.4** Responsive: sidebar collapse thành bottom nav khi width < 768px.
- [ ] **F7.5** Empty/loading/error states đồng bộ design.
- [ ] **F7.6** Color contrast check (axe DevTools).
- ✅ **Kết quả ngày 7**: UX production-ready, a11y cơ bản OK.

### Ngày 8 (Mon) — Notifications (UI)
- [ ] **F8.1** Thêm notification bell icon trong top bar.
- [ ] **F8.2** `app/src/lib/api.ts`: thêm `notifications.list()`, `notifications.markRead(id)`.
- [ ] **F8.3** Dropdown hiển thị 10 thông báo gần nhất, badge số unread.
- [ ] **F8.4** Polling mỗi 30s (hoặc SSE nếu backend support).
- [ ] **F8.5** Click notification → navigate tới ticket tương ứng.
- ✅ **Kết quả ngày 8**: User biết có ticket mới được giao.

### Ngày 9 (Tue) — Test + bug fix
- [ ] **F9.1** Test coverage target ≥ 50% cho `lib/` (api, auth, store) và ≥ 30% cho pages.
- [ ] **F9.2** Chạy `vitest --coverage`, fix test fail.
- [ ] **F9.3** Manual test: customer flow, technician flow, manager flow end-to-end trên dev.
- [ ] **F9.4** Fix bug UI từ manual test.
- [ ] **F9.5** Lighthouse score (Chrome DevTools): performance > 70, accessibility > 90.
- ✅ **Kết quả ngày 9**: Frontend ổn định.

### Ngày 10 (Wed) — Polish + integration test
- [ ] **F10.1** Code freeze frontend. Chỉ fix bug.
- [ ] **F10.2** Pair với Backend: test từ frontend → APISIX → backend. Fix CORS, auth, shape mismatch.
- [ ] **F10.3** Pair với AI: test nút "AI gợi ý" thực sự gọi được.
- [ ] **F10.4** Test trên Chrome, Firefox, Edge (nếu có máy).
- [ ] **F10.5** Test trên mobile view (Chrome DevTools responsive).
- [ ] **F10.6** Test từ production build (`npm run build` + `nginx -s reload` hoặc serve dist).
- ✅ **Kết quả ngày 10**: Frontend tích hợp xong.

### Ngày 11 (Thu) — Full E2E + bug bash
- [ ] **F11.1** Chạy 3 scenario end-to-end, ghi lại bug vào issue tracker.
- [ ] **F11.2** Verify tất cả link trong app không 404.
- [ ] **F11.3** Verify form submit không mất data khi refresh (autosave draft optional).
- [ ] **F11.4** Verify toast/error không spam.
- ✅ **Kết quả ngày 11**: Zero bug nghiêm trọng.

### Ngày 12 (Fri) — PoF hardening
- [ ] **F12.1** Quét tất cả `.tsx` và `.ts` xem có `// SPDX-License-Identifier: Apache-2.0` chưa. Thêm nếu thiếu.
- [ ] **F12.2** Bỏ tất cả console.log debug.
- [ ] **F12.3** Bundle analyzer: `npm run build -- --mode analyze` (nếu cấu hình). Đảm bảo bundle < 500KB gzipped.
- [ ] **F12.4** README.md: thêm screenshot 3 trang chính (Dashboard, Tickets, TicketDetail).
- [ ] **F12.5** Thêm favicon, app title tiếng Việt.
- [ ] **F12.6** Lighthouse final.
- ✅ **Kết quả ngày 12**: PoF đạt ≥ 40/50.

### Ngày 13 (Sat) — Release prep
- [ ] **F13.1** Test production build: `docker compose up -d app`, mở browser, click từng trang.
- [ ] **F13.2** Fix bug release-blocking.
- [ ] **F13.3** Generate icon set nếu cần.
- [ ] **F13.4** `CHANGELOG.md`: liệt kê tính năng mới.
- [ ] **F13.5** Update version trong `package.json` nếu backend cũng bump.
- ✅ **Kết quả ngày 13**: Sẵn sàng release.

### Ngày 14 (Sun) — Demo
- [ ] **F14.1** Rehearsal demo 3 lần.
- [ ] **F14.2** Slide 4–7 (UI walkthrough) do frontend viết.
- [ ] **F14.3** Quay video demo 3–5 phút, mình là người thao tác chính.
- [ ] **F14.4** Báo cáo phần UI/UX (1–2 trang).
- [ ] **F14.5** Backup static files (build output) trước demo.
- ✅ **Kết quả ngày 14**: Demo mượt.

---

## 3. Cấu trúc code đề xuất (ngày 2)

```
app/src/
├── App.tsx
├── main.tsx
├── index.css
├── components/
│   ├── Layout.tsx
│   ├── AuthGuard.tsx
│   ├── TopBar.tsx           # mới
│   ├── Sidebar.tsx          # tách từ Layout
│   ├── NotificationBell.tsx  # mới
│   ├── TicketTable.tsx      # mới
│   ├── TicketFilters.tsx    # mới
│   ├── StatusBadge.tsx      # mới
│   ├── PriorityBadge.tsx    # mới
│   ├── StatCard.tsx         # mới
│   ├── EmptyState.tsx       # mới
│   ├── LoadingSkeleton.tsx  # mới
│   ├── ErrorState.tsx       # mới
│   ├── AssignModal.tsx      # mới
│   └── AiSuggestionModal.tsx# mới
├── pages/
│   ├── Login.tsx
│   ├── Dashboard.tsx
│   ├── Tickets.tsx
│   ├── TicketCreate.tsx     # mới
│   ├── TicketDetail.tsx
│   ├── Profile.tsx          # mới (optional)
│   └── NotFound.tsx         # mới
├── lib/
│   ├── api.ts
│   ├── auth.ts
│   ├── store.ts
│   ├── i18n.ts              # mới
│   └── utils.ts             # format date, currency, etc.
├── hooks/
│   ├── useAuth.ts           # mới (wrap auth + store)
│   ├── useRole.ts           # mới
│   └── useDebounce.ts       # mới
└── i18n/
    ├── vi.json
    └── en.json
```

---

## 4. Pages tôi sẽ tạo (cross-check với 04)

| Path | Trang | Ai dùng | Status |
|---|---|---|---|
| `/login` | Login | All | ✅ |
| `/` | Dashboard | All | ✅ stub |
| `/tickets` | Tickets list | All | ✅ stub |
| `/tickets/new` | Create ticket | Customer/Manager | ❌ |
| `/tickets/:id` | Detail | All | ✅ stub |
| `/my-tickets` | My queue | Customer/Technician | ❌ |
| `/assign` | Assign dashboard | Manager | ❌ |
| `/reports` | Reports | Manager | ❌ optional |
| `/404` | NotFound | All | ❌ |

---

## 5. UI Component "design system" tối thiểu (ngày 2)

Để tránh mỗi trang dùng style khác nhau, tôi tạo file `src/index.css` với:

```css
:root {
  --color-bg: #f9fafb;
  --color-surface: #ffffff;
  --color-border: #e5e7eb;
  --color-text: #111827;
  --color-text-muted: #6b7280;
  --color-primary: #4f46e5;
  --color-primary-hover: #4338ca;
  --color-success: #10b981;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-info: #3b82f6;
  --radius: 0.5rem;
  --shadow-sm: 0 1px 2px 0 rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1);
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem;
  --space-4: 1rem; --space-6: 1.5rem; --space-8: 2rem;
}
```

Sau đó dùng class `.card`, `.btn`, `.btn-primary`, `.input`, `.badge` thay vì inline style.

---

## 6. Tôi sẽ review chéo

- Mọi PR của Backend liên quan `services/ticket-service/app/routes/tickets.py` (vì frontend cần đúng shape).
- Mọi PR của AI liên quan API response (cùng lý do).

---

## 7. Khi nào tôi báo blocker

- Backend chưa có endpoint → mở issue `cross-team` + label `backend` trong 1 giờ. Trong lúc chờ, dùng mock data + TODO.
- API shape khác expectation → tạo issue + ping backend. Tôi chịu trách nhiệm update `04-integration-checklist.md`.

---

## 8. Đề xuất Task Chip cho ngày 0–1 (quick wins)

Nếu team chưa rảnh, tôi sẽ gán cho mình 2 task chip có thể làm ngay:
1. `Fix auth token flow` — silent-check-sso + keycloak.updateToken
2. `Tạo silent-check-sso.html` — file 1 dòng, fix bug demo không vào được app
