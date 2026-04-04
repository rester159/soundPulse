import json
from typing import Any

import redis.asyncio as aioredis


class CacheService:
    def __init__(self, redis: aioredis.Redis | None):
        self.redis = redis

    async def get(self, key: str) -> Any | None:
        if self.redis is None:
            return None
        try:
            data = await self.redis.get(key)
            if data is None:
                return None
            return json.loads(data)
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception:
            pass

    async def delete(self, key: str) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.delete(key)
        except Exception:
            pass

    async def delete_pattern(self, pattern: str) -> None:
        if self.redis is None:
            return
        try:
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)
        except Exception:
            pass
