import time
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from api.dependencies import _hash_key, get_redis
from shared.constants import RATE_LIMITS


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key_header = request.headers.get("X-API-Key")
        if not api_key_header:
            return await call_next(request)

        # Determine tier from key prefix
        if api_key_header.startswith("sp_admin_"):
            tier = "admin"
        else:
            tier = "free"  # Default; actual tier checked after auth

        limit = RATE_LIMITS.get(tier, 100)
        if limit == 0:  # unlimited
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = "unlimited"
            response.headers["X-RateLimit-Remaining"] = "unlimited"
            return response

        redis = await get_redis()
        key_id = _hash_key(api_key_header)[:16]
        window_key = f"ratelimit:{key_id}"

        now = time.time()
        window_start = now - 3600  # 1-hour sliding window

        pipe = redis.pipeline()
        pipe.zremrangebyscore(window_key, 0, window_start)
        pipe.zadd(window_key, {str(now): now})
        pipe.zcard(window_key)
        pipe.expire(window_key, 3600)
        results = await pipe.execute()

        request_count = results[2]
        remaining = max(0, limit - request_count)

        reset_at = datetime.fromtimestamp(now + 3600, tz=timezone.utc).isoformat()

        if request_count > limit:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Resets at {reset_at}",
                        "details": {
                            "limit": limit,
                            "remaining": 0,
                            "reset_at": reset_at,
                            "tier": tier,
                        },
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_at,
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = reset_at
        return response
