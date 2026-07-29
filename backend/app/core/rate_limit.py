"""Redis-backed fixed-window rate limiting with a safe in-process fallback.

If Redis is unreachable the limiter degrades to a local window so a cache outage
never takes the API down, and never silently disables protection either.
"""

import time
from dataclasses import dataclass, field

from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


@dataclass
class _LocalWindow:
    counts: dict[str, tuple[int, float]] = field(default_factory=dict)

    def hit(self, key: str, limit: int, window: int) -> RateLimitDecision:
        now = time.monotonic()
        count, expires_at = self.counts.get(key, (0, now + window))
        if now >= expires_at:
            count, expires_at = 0, now + window
        count += 1
        self.counts[key] = (count, expires_at)
        retry_after = max(1, int(expires_at - now))
        return RateLimitDecision(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            retry_after_seconds=retry_after,
        )


class RateLimiter:
    def __init__(self, redis: Redis | None, *, limit_per_minute: int, burst: int) -> None:
        self._redis = redis
        self._limit = max(1, limit_per_minute + burst)
        self._window = 60
        self._local = _LocalWindow()

    async def check(self, identity: str, scope: str = "default") -> RateLimitDecision:
        key = f"ratelimit:{scope}:{identity}"
        if self._redis is None:
            return self._local.hit(key, self._limit, self._window)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.ttl(key)
                count, ttl = await pipe.execute()
            if ttl is None or ttl < 0:
                await self._redis.expire(key, self._window)
                ttl = self._window
        except Exception as exc:  # degrade, never fail the request path
            logger.warning("rate_limit_redis_unavailable", error=str(exc))
            return self._local.hit(key, self._limit, self._window)

        return RateLimitDecision(
            allowed=int(count) <= self._limit,
            limit=self._limit,
            remaining=max(0, self._limit - int(count)),
            retry_after_seconds=max(1, int(ttl)),
        )
