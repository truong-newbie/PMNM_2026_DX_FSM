# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – JWT Authentication via Keycloak JWKS

"""
security.py
───────────
JWT verification using Keycloak JWKS (JSON Web Key Set).

Flow:
  1. Extract Bearer token from Authorization header.
  2. Decode header to get `kid` (key ID).
  3. Fetch JWKS from Keycloak (Docker internal DNS).
  4. Match `kid` → public RSA key.
  5. Verify signature, expiry, audience, issuer.

NOTE: Verification uses PUBLIC key from JWKS — no client secret required.
The secret is only needed for service-to-service calls (not implemented here).
"""

from __future__ import annotations

import time
from typing import Annotated, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings


# ─── Pydantic models ────────────────────────────────────────────────────────


class TokenUser(BaseModel):
    """Decoded JWT claims."""

    sub: str
    preferred_username: str
    email: str | None = None
    full_name: str | None = None
    role: str | None = None
    exp: int
    iss: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role in ("admin", "manager")

    @property
    def is_technician(self) -> bool:
        return self.role in ("admin", "manager", "technician")


# ─── Keycloak JWKS ───────────────────────────────────────────────────────────

_JWKS_CACHE_TTL = 3600
_jwks_cache: dict = {}
_jwks_fetched_at: float = 0.0


async def get_jwks() -> dict:
    """Fetch + cache JWKS from Keycloak internal URL."""
    global _jwks_cache, _jwks_fetched_at

    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_CACHE_TTL:
        return _jwks_cache

    jwks_url = (
        f"{settings.keycloak_internal_url}"
        f"/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/certs"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(jwks_url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = now

    return _jwks_cache


def _find_key(jwks: dict, kid: str) -> dict | None:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def _decode_token(token: str) -> dict:
    """Verify + decode a JWT using Keycloak JWKS."""
    try:
        unverified = jwt.get_unverified_header(token)
        kid = unverified.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing 'kid' in header",
            )

        jwks = await get_jwks()
        rsa_key = _find_key(jwks, kid)
        if not rsa_key:
            # Key may have rotated — refresh and retry once
            global _jwks_cache, _jwks_fetched_at
            _jwks_cache = {}
            _jwks_fetched_at = 0.0
            jwks = await get_jwks()
            rsa_key = _find_key(jwks, kid)
            if not rsa_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unknown signing key",
                )

        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            issuer=f"{settings.keycloak_public_url}/realms/{settings.keycloak_realm}",
        )
        return claims

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


# ─── FastAPI security scheme ─────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(_bearer),
    ],
) -> TokenUser:
    """
    FastAPI Dependency — validates the JWT and returns a TokenUser.

    Usage:
        @router.get("/tickets")
        async def list(user: TokenUser = Depends(get_current_user)):
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    claims = await _decode_token(token)

    # Extract role from Keycloak token structure
    realm_roles: list[str] = claims.get("realm_access", {}).get("roles", [])
    role: str | None = None
    if "admin" in realm_roles:
        role = "admin"
    elif "manager" in realm_roles:
        role = "manager"
    elif "technician" in realm_roles:
        role = "technician"
    elif "customer" in realm_roles:
        role = "customer"

    return TokenUser(
        sub=claims.get("sub", ""),
        preferred_username=claims.get("preferred_username", ""),
        email=claims.get("email"),
        full_name=claims.get("name") or claims.get("given_name", ""),
        role=role,
        exp=claims.get("exp", 0),
        iss=claims.get("iss", ""),
    )


# ─── Role guard ──────────────────────────────────────────────────────────────


def require_roles(*roles: str):
    """Factory: returns a FastAPI Dependency that enforces one of the given roles."""
    async def role_checker(user: TokenUser = Depends(get_current_user)) -> TokenUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of roles: {roles}",
            )
        return user

    return role_checker


CurrentUser = Annotated[TokenUser, Depends(get_current_user)]
