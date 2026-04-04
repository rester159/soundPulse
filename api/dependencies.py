import hashlib
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import get_settings
from api.database import get_db
from api.models.api_key import ApiKey

settings = get_settings()

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            # Test the connection
            await _redis_pool.ping()
        except Exception:
            _redis_pool = None
    return _redis_pool


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_api_key_record(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Validate API key and return the key record."""
    # Check if it matches the bootstrap admin key from env
    if x_api_key == settings.api_admin_key:
        # Return a synthetic admin key record
        key = ApiKey(
            key_hash=_hash_key(x_api_key),
            key_prefix=x_api_key[:9],
            key_last4=x_api_key[-4:],
            tier="admin",
            owner="bootstrap",
        )
        return key

    key_hash = _hash_key(x_api_key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing API key",
                    "details": {},
                }
            },
        )

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    return api_key


async def require_admin(api_key: ApiKey = Depends(get_api_key_record)) -> ApiKey:
    """Require admin tier API key."""
    if api_key.tier != "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Admin API key required for this endpoint",
                    "details": {},
                }
            },
        )
    return api_key
