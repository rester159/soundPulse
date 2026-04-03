import json
from typing import Any

import redis.asyncio as aioredis


class CacheService:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def get(self, key: str) -> Any | None:
        data = await self.redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        await self.redis.set(key, json.dumps(value, default=str), ex=ttl)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        async for key in self.redis.scan_iter(match=pattern):
            await self.redis.delete(key)
