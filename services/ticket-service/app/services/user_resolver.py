# SPDX-License-Identifier: Apache-2.0
# DX-FSM Ticket Service – User Resolver
# Helper: lookup hoặc auto-provision user từ Keycloak token claim.

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenUser
from app.models.user import User

logger = logging.getLogger(__name__)


async def resolve_or_create_user(
    db: AsyncSession,
    user: TokenUser,
) -> Optional[UUID]:
    """
    Trả về User.id tương ứng với Keycloak `sub`.
    Auto-provision nếu chưa có trong DB.

    Flow:
      1. Tìm theo keycloak_id (sub)
      2. Fallback: tìm theo username (legacy seed)
      3. Cuối cùng: INSERT user mới
    """
    if not user.sub:
        return None

    # 1. Lookup by keycloak_id
    result = await db.execute(
        select(User.id).where(User.keycloak_id == user.sub)
    )
    user_id = result.scalar_one_or_none()
    if user_id is not None:
        return user_id

    # 2. Legacy match by username
    if user.preferred_username:
        result = await db.execute(
            select(User.id).where(User.username == user.preferred_username)
        )
        legacy = result.scalar_one_or_none()
        if legacy:
            # Migrate legacy → keycloak_id
            await db.execute(
                update(User)
                .where(User.id == legacy)
                .values(keycloak_id=user.sub)
            )
            return legacy

    # 3. Auto-provision
    role = user.role if user.role in ("admin", "manager", "technician", "customer") else "customer"
    new_user = User(
        keycloak_id=user.sub,
        username=user.preferred_username or user.sub[:8],
        email=user.email,
        full_name=user.full_name,
        role=role,
    )
    db.add(new_user)
    await db.flush()
    logger.info(f"Auto-provisioned user: {new_user.username} (sub={user.sub[:8]}...)")
    return new_user.id
