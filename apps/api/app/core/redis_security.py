"""Shared Redis primitives for distributed security counters."""
from __future__ import annotations
import hashlib
import logging
from functools import lru_cache
from app.core.config import settings

logger = logging.getLogger("elsewhere.security.redis")

@lru_cache(maxsize=1)
def get_redis_client():
    if not settings.redis_url.strip():
        return None
    try:
        import redis
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
            health_check_interval=30,
            decode_responses=True,
        )
        client.ping()
        return client
    except Exception:
        logger.exception("Redis security backend unavailable")
        return None

def client_key(value: str) -> str:
    # Hash the source identifier before placing it in Redis keys.
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def redis_key(namespace: str, identity: str, bucket: str) -> str:
    return f"{settings.redis_key_prefix}:{namespace}:{bucket}:{client_key(identity)}"
