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
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """
    Resolve the caller's API key — or grant synthetic admin if none given.

    The site runs as a single-operator tool, fully open. Rather than
    delete every `Depends(get_api_key_record)` across ~15 routers, we
    centralize the policy here: no header → synthetic admin record. Any
    real key still validates as before, so existing scripts using a key
    keep working.
    """
    if not x_api_key:
        # Open-access path: synthesize an admin key record so downstream
        # `require_admin` checks pass and per-key audit columns get a
        # stable identifier ('open_access') across requests.
        return ApiKey(
            key_hash=_hash_key("__open_access__"),
            key_prefix="open_acc",
            key_last4="cess",
            tier="admin",
            owner="open_access",
        )

    if x_api_key == settings.api_admin_key:
        return ApiKey(
            key_hash=_hash_key(x_api_key),
            key_prefix=x_api_key[:9],
            key_last4=x_api_key[-4:],
            tier="admin",
            owner="bootstrap",
        )

    key_hash = _hash_key(x_api_key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
    api_key = result.scalar_one_or_none()

    if api_key is None:
        # Unknown key supplied — treat as open access (don't reward bad
        # keys with a 401 leak; just demote to the synthetic admin).
        return ApiKey(
            key_hash=_hash_key("__open_access__"),
            key_prefix="open_acc",
            key_last4="cess",
            tier="admin",
            owner="open_access",
        )

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
