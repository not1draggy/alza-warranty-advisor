"""Redis JSON cache with graceful degradation.

Every method is a no-op when Redis is unavailable, so a cache outage slows the
system down but never breaks it.
"""

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)


def cache_key(namespace: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"wa:{namespace}:{digest}"


class Cache:
    def __init__(self, redis: Redis | None) -> None:
        self._redis = redis

    @property
    def available(self) -> bool:
        return self._redis is not None

    async def get_json(self, key: str) -> Any | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_get_failed", key=key, error=str(exc))
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("cache_corrupt_entry", key=key)
            await self.delete(key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_set_failed", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_delete_failed", key=key, error=str(exc))

    async def ping(self) -> bool:
        if self._redis is None:
            return False
        try:
            return bool(await self._redis.ping())
        except Exception:  # noqa: BLE001
            return False
