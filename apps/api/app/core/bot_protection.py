"""Optional Cloudflare Turnstile verification and lightweight abuse signals."""
from __future__ import annotations
import json
import logging
import os
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from fastapi import Request
from starlette.responses import JSONResponse
from app.core.config import settings
from app.core.redis_security import get_redis_client, redis_key

logger = logging.getLogger("elsewhere.security")
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

class SuspiciousActivityMonitor:
    """Process-local signal counter; never stores credentials or request bodies."""
    def __init__(self):
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def record_auth_failure(self, client_ip: str, now: float | None = None) -> bool:
        now = monotonic() if now is None else now
        window = settings.suspicious_auth_window_seconds
        if settings.rate_limit_backend.strip().lower() == "redis":
            redis = get_redis_client()
            if redis is not None:
                key = redis_key("authfail", client_ip, "login")
                count = redis.incr(key)
                if count == 1:
                    redis.expire(key, window)
                if count > settings.suspicious_auth_failure_threshold:
                    logger.warning("suspicious_auth_activity source_hash=%s failures=%s window_seconds=%s",
                                   __import__("hashlib").sha256(client_ip.encode()).hexdigest(), count, window)
                    return True
                return False
            if settings.redis_required:
                logger.error("Redis unavailable; shared suspicious activity counter not updated")
                return False
        with self._lock:
            bucket = self._failures[client_ip]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            bucket.append(now)
            if len(bucket) > settings.suspicious_auth_failure_threshold:
                logger.warning("suspicious_auth_activity ip=%s failures=%s window_seconds=%s",
                               client_ip, len(bucket), window)
                return True
        return False

monitor = SuspiciousActivityMonitor()

def verify_turnstile(token: str, remote_ip: str | None = None) -> bool:
    secret = settings.turnstile_secret_key.strip()
    if not secret:
        return not settings.turnstile_required
    if not token or len(token) > 4096:
        return False
    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    request = urllib.request.Request(
        VERIFY_URL,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            result = json.loads(response.read(16384).decode("utf-8"))
        return bool(result.get("success"))
    except Exception:
        logger.exception("Turnstile verification service unavailable")
        return False

async def bot_protection_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/")
    protected = request.method == "POST" and path in {
        "/api/v1/auth/register", "/api/v1/auth/login",
        "/api/v1/auth/password-reset/request",
    }
    if protected and (settings.turnstile_required or settings.turnstile_secret_key.strip()):
        token = request.headers.get("X-Turnstile-Token", "")
        ip = request.client.host if request.client else None
        if not verify_turnstile(token, ip):
            return JSONResponse(status_code=403,
                content={"detail": "Complete the security challenge and try again."},
                headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    if path == "/api/v1/auth/login" and response.status_code == 401:
        ip = request.client.host if request.client else "unknown"
        monitor.record_auth_failure(ip)
    return response
