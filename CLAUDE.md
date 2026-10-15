# DX-FSM – Architecture & Engineering Notes

## Tổng quan kiến trúc

DX-FSM là nền tảng quản lý dịch vụ thực địa (Field Service Management) được thiết kế theo mô hình Open-Core với 3 tầng.

## Mô hình 3 tầng

### Tầng 1: Open-Core (Headless)
Infrastructure và services nền tảng, không có UI.

| Component | Technology | Port |
|---|---|---|
| Keycloak | SSO/Identity | 8080 |
| nginx | API Gateway | 80 |
| PostgreSQL | Database | 5432 |
| MinIO | Object Storage | 9000/9001 (disabled) |
| n8n | Workflow Automation | 5678 |

### Tầng 2: H-P-D-I (Service Tier)
Các microservice xử lý nghiệp vụ.

- `ticket-service` (port 8001) – Core CRUD cho tickets, users, AI classification
- `ai-service` (port 8002) – AI inference (rule-based + Ollama)
- `notification-service` (port 8003) – Notifications

### Tầng 3: User Interface (Open-Core Frontend)
React 18 SPA cho user tương tác.

## Cách khởi động

```bash
# Build và chạy toàn bộ (khuyến nghị)
docker compose up -d --build

# Chỉ infrastructure + gateway
docker compose up -d postgres keycloak gateway n8n

# Smoke test
curl http://localhost/health
curl http://localhost/api/v1/tickets
curl http://localhost:8080/realms/dx-fsm/.well-known/openid-configuration
```

## Cấu trúc thư mục

```
dx-fsm/
├── core/                   # Tầng 1: Open-Core
│   ├── keycloak/          # Realm configuration + JSON
│   ├── nginx/             # Gateway config (thay APISIX)
│   ├── postgres/          # Schema + seed data
│   ├── minio/             # Storage init (disabled trong compose)
│   └── n8n/               # Workflow JSON exports
├── services/               # Tầng 2: H-P-D-I
│   ├── ticket-service/     # FastAPI + SQLAlchemy + asyncpg
│   ├── ai-service/        # FastAPI + Ollama
│   └── notification-service/
├── app/                   # Tầng 3: React 18 Frontend
│   └── src/
│       ├── pages/
│       ├── components/
│       └── lib/
├── docs/                  # Documentation
└── docker-compose.yml
```

## Database

PostgreSQL với schema bao gồm:
- `users` – metadata từ Keycloak
- `tickets` – ticket chính (50+ seed records)
- `technicians` – thông tin KTV mở rộng
- `ticket_comments`, `ticket_attachments`, `ticket_history`
- `notifications`

Views cho dashboard:
- `v_ticket_stats` – thống kê tổng quan
- `v_tickets_by_category` – theo danh mục
- `v_technician_load` – tải KTV

## AI Integration

ai-service có 2 lớp:
1. **Rule-based** (luôn hoạt động) – keyword matching
2. **Ollama** (tùy chọn) – LLM inference qua local

## Authentication

Keycloak với:
- Realm: `dx-fsm`
- Clients: `dx-fsm-api` (confidential), `dx-fsm-frontend` (public)
- Demo users: admin, manager, technician, customer (password: `{username}123`)

## License

Apache 2.0 cho Open-Core + Documentation.
