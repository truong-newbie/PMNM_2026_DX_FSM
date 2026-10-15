# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service Configuration

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://dxfsm:changeme@postgres:5432/dxfsm"

    # Keycloak
    # keycloak_public_url: dùng cho issuer verify (phải khớp với iss trong JWT)
    # keycloak_internal_url: dùng để fetch JWKS từ Docker network
    keycloak_public_url: str = "http://localhost:8080"
    keycloak_internal_url: str = "http://keycloak:8080"
    keycloak_realm: str = "dx-fsm"
    # Client ID cho audience verify; secret chỉ cần cho service-to-service call,
    # JWT verify dùng public key từ JWKS nên KHÔNG cần secret trong code
    keycloak_client_id: str = "dx-fsm-api"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "changeme"
    minio_bucket: str = "attachments"

    # AI Service
    ai_service_url: str = "http://ai-service:8002"

    # n8n
    n8n_webhook_url: str = "http://n8n:5678/webhook"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:9180",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Module-level singleton – dùng trực tiếp trong các file import
settings = get_settings()
