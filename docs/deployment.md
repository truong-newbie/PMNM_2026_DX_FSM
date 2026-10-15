# DX-FSM Deployment Guide

## Yêu cầu hệ thống

- Docker Engine 24.0+
- Docker Compose v2.x
- RAM: 8GB (khuyến nghị 16GB)
- Disk: 20GB trống

## Các bước triển khai

### 1. Chuẩn bị

```bash
cd dx-fsm

# Copy .env
cp .env.example .env

# Build images
docker compose build
```

### 2. Khởi động

```bash
# Toàn bộ hệ thống
docker compose up -d

# Chỉ Open-Core trước (kiểm tra infrastructure)
docker compose -f docker-compose.yml -f docker-compose.core.yml up -d
```

### 3. Kiểm tra

```bash
# Tất cả containers
docker compose ps

# Health check từng service
curl http://localhost:8080/health/ready      # Keycloak
curl http://localhost:5432                    # PostgreSQL
curl http://localhost:9000/minio/health/live # MinIO
curl http://localhost:9180/apisix/admin/health # APISIX
curl http://localhost:8001/health             # Ticket Service
curl http://localhost:3000                    # Frontend
```

### 4. Truy cập

| Service | URL | Credentials |
|---|---|---|
| Frontend | http://localhost:3000 | SSO |
| Keycloak | http://localhost:8080 | admin / <DEMO_PASSWORD> |
| MinIO Console | http://localhost:9001 | minioadmin / changeme_minio_123 |
| n8n | http://localhost:5678 | admin / changeme_n8n_123 |
| API (via APISIX) | http://localhost:9180/api/v1 | JWT |

### 5. Dừng

```bash
docker compose down
```

### 6. Xóa toàn bộ (bao gồm data)

```bash
docker compose down -v
```

## Triển khai môi trường Production

1. Đổi tất cả passwords trong `.env`
2. Enable HTTPS (đặt sau reverse proxy như Nginx/Traefik)
3. Enable JWT validation trong APISIX
4. Cấu hình Keycloak production realm
5. Backup PostgreSQL và MinIO định kỳ
6. Cấu hình monitoring (Prometheus + Grafana)

## Troubleshooting

```bash
# Xem logs
docker compose logs -f postgres
docker compose logs -f ticket-service

# Restart service
docker compose restart ticket-service

# Rebuild không cache
docker compose build --no-cache
```
