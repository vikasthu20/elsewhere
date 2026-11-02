"""Distributed sliding-window rate limiting with optional Redis backend."""
from __future__ import annotations
from collections import defaultdict, deque
from threading import Lock
from time import monotonic, time
from fastapi import Request
from starlette.responses import JSONResponse
from app.core.config import settings
from app.core.redis_security import get_redis_client, redis_key

# Atomic sorted-set sliding window. Each request gets a unique member; expired
# events are pruned and the count/check/insert happen in one Redis transaction.
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', key)
if count >= limit then
  local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = math.max(1, math.ceil((tonumber(first[2]) + window_ms - now_ms) / 1000))
  return {0, retry}
end
redis.call('ZADD', key, now_ms, member)
redis.call('PEXPIRE', key, window_ms + 1000)
return {1, 0}
"""

class SlidingWindowRateLimiter:
    def __init__(self):
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _consume_memory(self, key, limit, window, now):
        with self._lock:
            bucket = self._events[key]
            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False, max(1, int(window - (now - bucket[0])))
            bucket.append(now)
            if len(self._events) > settings.rate_limit_max_tracked_clients:
                stale_before = now - max(window, settings.auth_rate_limit_window_seconds)
                stale = [k for k, values in self._events.items() if not values or values[-1] <= stale_before]
                for item in stale[:max(1, len(self._events)//10)]:
                    self._events.pop(item, None)
            return True, 0

    def _consume(self, namespace, client, limit, window, now):
        if settings.rate_limit_backend.strip().lower() != "redis":
            allowed, retry = self._consume_memory((namespace, client), limit, window, now)
            return allowed, retry, "ok"
        redis = get_redis_client()
        if redis is None:
            if settings.redis_required:
                return False, max(1, int(settings.redis_socket_timeout_seconds)), "backend_unavailable"
            allowed, retry = self._consume_memory((namespace, client), limit, window, now)
            return allowed, retry, "ok"
        key = redis_key("ratelimit", client, namespace)
        now_ms = int(time() * 1000)
        member = f"{now_ms}:{__import__('secrets').token_hex(8)}"
        result = redis.eval(SLIDING_WINDOW_LUA, 1, key, now_ms, int(window*1000), limit, member)
        return bool(int(result[0])), int(result[1]), "ok"

    def check(self, client, path, now=None):
        now = monotonic() if now is None else now
        normalized = path.split("?",1)[0].rstrip("/") or "/"
        auth_sensitive = normalized.endswith(("/auth/login", "/auth/otp/verify", "/auth/otp/request",
                                              "/auth/password/reset", "/auth/register"))
        if auth_sensitive:
            allowed, retry, status = self._consume("auth", client, settings.auth_rate_limit_attempts,
                                                   settings.auth_rate_limit_window_seconds, now)
            if not allowed:
                return False, retry, "authentication" if status != "backend_unavailable" else status
        allowed, retry, status = self._consume("api", client, settings.rate_limit_requests,
                                               settings.rate_limit_window_seconds, now)
        if not allowed:
            return False, retry, "api" if status != "backend_unavailable" else status
        return True, 0, "ok"

limiter = SlidingWindowRateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    if not settings.rate_limit_enabled or request.method == "OPTIONS" or request.url.path == "/health":
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    allowed, retry_after, category = limiter.check(client, request.url.path)
    if not allowed:
        status = 503 if category == "backend_unavailable" else 429
        message = "Security rate-limit service unavailable." if status == 503 else "Too many requests. Please retry later."
        response = JSONResponse(status_code=status, content={"detail": message, "limit_category": category},
                                headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"})
    else:
        response = await call_next(request)
    response.headers["X-RateLimit-Policy"] = settings.rate_limit_backend
    return response
