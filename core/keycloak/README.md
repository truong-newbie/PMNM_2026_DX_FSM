# Keycloak Configuration

## Realm: dx-fsm

Import tự động qua `realm-export.json` khi container khởi động.

## Client: dx-fsm-api

- Protocol: openid-connect
- Access Type: confidential
- Service Accounts Enabled: true

## Client: dx-fsm-frontend

- Protocol: openid-connect
- Access Type: public
- Standard Flow Enabled: true

## Roles

- `admin` – Quản trị hệ thống
- `manager` – Quản lý team
- `technician` – Kỹ thuật viên
- `customer` – Khách hàng

## Admin Console

URL: http://localhost:8080/auth/admin
User: admin / <DEMO_PASSWORD>
