# Sprint Plan — DX-FSM (DX-Lab, 14 ngày)

> Cuộc thi **PMNM HaUI 2026** — chủ đề **DX-OS Open-Core**, hạn nộp theo lịch vòng HaUI.
> 3 thành viên: **Backend** / **Frontend** / **AI**. Mỗi người sở một subtree, làm song song, daily sync 15 phút, tích hợp cuối ngày 11.

---

## 📁 Tài liệu sprint

| # | File | Chủ sở hữu | Đọc khi nào |
|---|---|---|---|
| 00 | [00-phoi-hop.md](./00-phoi-hop.md) | Cả 3 | **Đầu tiên** — quy ước, subtree, lộ trình tổng |
| 01 | [01-backend.md](./01-backend.md) | Backend Dev | Ngày 1, mỗi ngày |
| 02 | [02-frontend.md](./02-frontend.md) | Frontend Dev | Ngày 1, mỗi ngày |
| 03 | [03-ai.md](./03-ai.md) | AI Dev | Ngày 1, mỗi ngày |
| 04 | [04-integration-checklist.md](./04-integration-checklist.md) | Cả 3 | **API contract — bất di bất dịch** |
| 05 | [05-daily-log.md](./05-daily-log.md) | Cả 3 | Cuối mỗi ngày |

---

## 🚀 Bắt đầu nhanh

1. Đọc `00-phoi-hop.md` để hiểu quy ước làm việc.
2. Đọc file role của bạn (01 / 02 / 03).
3. Mở issue list trên GitHub, copy task từ file role của bạn thành issues.
4. Đọc `04-integration-checklist.md` để biết API phải tuân theo.
5. Hằng ngày: cập nhật `05-daily-log.md` trước khi push daily commit.

---

## 📅 Tóm tắt lộ trình 14 ngày

| Ngày | Mốc chung | Backend | Frontend | AI |
|---|---|---|---|---|
| 1–2 | Phân tích + cleanup | Fix schema mismatch, auth, route chuẩn | Fix auth flow, design system | Setup eval, KB, fix docs |
| 3–4 | Open-Core | CRUD ticket, comments, attachments, n8n fix | Tickets list, create form | Classify + Recommend cải tiến |
| 5–7 | H-P-D-I | Stats endpoint, overdue, assign | Ticket detail + actions, dashboard | RAG, duplicate, summary |
| 8–10 | I + App + E2E | APISIX, notification, smoke | Polish, i18n, a11y | Observability, model card |
| 11 | **Tích hợp full** | Code freeze, pair with FE/AI | Code freeze, pair with BE/AI | Code freeze, pair with BE/FE |
| 12 | Hardening PoF | License, secret, README, CI | License, README screenshots | Model card, eval report |
| 13 | **Release v0.1.0** | Tag, GitHub Release | Prod build test | Eval report final |
| 14 | Demo | Slide, video, rehearsal | Slide, video | Slide, video |

---

## 🎯 Definition of Done (toàn đội)

- [ ] `docker compose up -d` chạy từ zero trong < 5 phút
- [ ] SSO login OK → API call 200
- [ ] Customer tạo ticket end-to-end, AI classify, recommend KTV
- [ ] Demo 10 phút mượt, không restart service
- [ ] Repo public trên GitHub, Apache 2.0 ở root + SPDX header mọi file
- [ ] ≥ 1 release tag
- [ ] README, CHANGELOG, CONTRIBUTING đầy đủ
- [ ] Slide ≤ 12 trang, video 3–5 phút
- [ ] Báo cáo kỹ thuật 8–10 trang
