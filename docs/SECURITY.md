# DX-FSM — Security & Secret Management

> **Mục đích**: Quy định cách quản lý credentials, secrets, và rotation
> cho mọi thành viên trong nhóm + CI/CD.
>
> **Cập nhật lần cuối**: Ngày 0

---

## 1. Nguyên tắc chung

1. **Không commit secrets vào git** — bất kỳ lúc nào.
2. **Local dev**: dùng file `.env` (đã gitignored).
3. **Production**: dùng secret manager (Vault, AWS Secrets Manager, Keycloak).
4. **Rotation**: Mọi secret leak → rotate trong 24h.
5. **Demo credentials** trong docs (`<DEMO_PASSWORD>`, `${VAR_NAME:?set in .env}`)
   KHÔNG phải real secrets — chỉ là placeholder.

---

## 2. Quy trình khi setup local

```bash
# 1. Copy template
cp .env.example .env

# 2. Sửa .env với giá trị thực (LẤY TỪ Keycloak admin / team lead)
#    KHÔNG dùng placeholder

# 3. Verify .env không bị commit
git status  # .env phải hiện "Untracked" hoặc không có
```

**Nếu .env chưa tồn tại**, hỏi team lead hoặc tự tạo trong Keycloak:

```bash
# Lấy Keycloak admin token
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -d "grant_type=password" -d "client_id=admin-cli" \
  -d "username=admin" -d "password=${KC_ADMIN_PASSWORD}" \
  | jq -r .access_token)

# Xem secret hiện tại
curl -s "http://localhost:8080/admin/realms/dx-fsm/clients/dx-fsm-api/client-secret" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## 3. Demo Credentials (LOCAL DEV ONLY)

Các credentials dưới đây dùng trong docs/README là **placeholder**,
không phải real production secrets. KHÔNG dùng cho prod.

| Username | Password | Role | File |
|---|---|---|---|
| `admin` | `admin123` | admin | seed-data |
| `manager` | `manager123` | manager | seed-data |
| `technician` | `tech123` | technician | seed-data |
| `customer` | `customer123` | customer | seed-data |

> **Trước khi deploy production**:
> 1. Đổi tất cả password này trong Keycloak admin
> 2. Rotate client secret cho `dx-fsm-api`
> 3. Update `.env` với secret mới
> 4. Xóa file `core/keycloak/realm-export.json` khỏi git (nếu có)

---

## 4. Rotation

### 4.1. Keycloak client secret (`dx-fsm-api`)

```bash
# 1. Lấy admin token
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -d "grant_type=password" -d "client_id=admin-cli" \
  -d "username=admin" -d "password=${KC_ADMIN_PASSWORD}" \
  | jq -r .access_token)

# 2. Regenerate secret
NEW_SECRET=$(curl -s -X POST "http://localhost:8080/admin/realms/dx-fsm/clients/dx-fsm-api/client-secret" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"realm": "dx-fsm"}' | jq -r .value)

# 3. Update .env
echo "KEYCLOAK_CLIENT_SECRET=$NEW_SECRET" >> .env

# 4. Restart services
docker compose restart ticket-service ai-service
```

### 4.2. User passwords

Vào Keycloak admin → Users → chọn user → Credentials → Reset Password.

### 4.3. PostgreSQL password

```bash
# 1. Đổi password
docker compose exec postgres psql -U dxfsm -c "ALTER USER dxfsm WITH PASSWORD 'NEW_PASSWORD';"

# 2. Update .env
echo "POSTGRES_PASSWORD=NEW_PASSWORD" >> .env

# 3. Update DATABASE_URL
# 4. Restart
```

---

## 5. Pre-commit Secret Scanner

DX-FSM repo có **pre-commit hook** tự động scan staged files cho secrets.

### Setup
```bash
bash scripts/install-hooks.sh
```

### Cách hoạt động
- Scan 13 patterns phổ biến: AWS, GitHub, OpenAI, Stripe, JWT, PEM keys, etc.
- Block commit nếu phát hiện secret mới
- Allowlist demo patterns: `<DEMO_PASSWORD>`, `${VAR:?set in .env}`

### Bypass (KHÔNG khuyến nghị)
```bash
git commit --no-verify -m "..."
```

### Patterns được detect
- AWS: `AKIA[0-9A-Z]{16}`
- GitHub tokens: `ghp_*`, `gho_*`, `ghs_*`, `ghu_*`
- OpenAI: `sk-*` (≥32 chars)
- Stripe: `sk_test_*`, `pk_live_*`
- Slack: `xox[abprs]-*`
- Google API: `AIza*`
- Generic: `password=...`, `secret=...` (trong code)
- PostgreSQL URL: `postgresql://user:pass@host`
- PEM private keys
- JWT tokens (hardcoded)

### Nếu scanner flag false positive
1. Kiểm tra xem secret có thật không
2. Nếu là false positive (ví dụ: test fixture, documentation):
   - Thêm pattern vào `.secrets.allowlist`
   - HOẶC thêm file vào `ALLOWLIST_FILES` trong `scripts/check-secrets.cjs`
3. KHÔNG dùng `--no-verify` để bypass

---

## 6. Nếu lỡ commit secret

1. **Rotate ngay lập tức** trong service gốc (Keycloak, AWS, etc.)
2. **Xóa khỏi git history**:
   ```bash
   # Option A: git filter-branch (cũ nhưng có sẵn)
   git filter-branch -f --tree-filter \
     "sed -i 's/OLD_SECRET/NEW_PLACEHOLDER/g' path/to/file" HEAD
   
   # Option B: git filter-repo (khuyến nghị)
   pip install git-filter-repo
   git filter-repo --replace-text expressions.txt
   ```
3. **Force-push** (cảnh báo team trước):
   ```bash
   git push --force-with-lease origin <branch>
   ```
4. **Notify team** trong Slack/email để fresh-clone.
5. **Verify** trên GitHub: secret không còn ở history.

---

## 7. Checklist trước khi merge PR

- [ ] Không có secret trong code (chỉ `.env` placeholders)
- [ ] Không có `console.log(token)` debug statements
- [ ] Không có URL/database chứa credentials thật
- [ ] `.env.example` được update nếu có biến mới
- [ ] Pre-commit hook scan clean
- [ ] GitGuardian scan clean (nếu có)

---

## 8. Liên hệ

- **Security issue** (đã lộ secret): tạo GitHub issue với label `security`
- **Câu hỏi**: ping team lead hoặc mở discussion

**Cập nhật lần cuối**: Sprint 4
