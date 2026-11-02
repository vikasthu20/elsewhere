from contextlib import asynccontextmanager
from threading import Event, Thread
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import RedirectResponse
from app.core.config import settings
from app.core.rate_limit import rate_limit_middleware
from app.core.bot_protection import bot_protection_middleware
from app.core.security_events import persist_security_event
from app.routers import api
from app.db import Base, engine, SessionLocal
from app.models import User, SecurityAlert
from jose import jwt, JWTError
from sqlalchemy import desc
import asyncio
import app.models  # ensure models are registered with Base.metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reject unsafe production secrets, CORS and transport settings before serving traffic.
    settings.validate_runtime_configuration()
    from app.services.email_retry import run_email_retry_loop
    from app.services.security_notification_delivery import process_batch
    import os
    stop_event = Event()
    worker = Thread(target=run_email_retry_loop, args=(stop_event,), name="elsewhere-email-retry", daemon=True)
    worker.start()

    def run_notification_loop(stop_event):
        interval = max(5, int(os.getenv("SECURITY_NOTIFICATION_POLL_SECONDS", "15")))
        while not stop_event.is_set():
            try:
                process_batch()
            except Exception:
                pass
            stop_event.wait(interval)

    in_process = os.getenv("SECURITY_NOTIFICATION_WORKER_IN_PROCESS", "true").lower() in {"1", "true", "yes"}
    notify_worker = None
    if in_process:
        notify_worker = Thread(target=run_notification_loop, args=(stop_event,),
                               name="elsewhere-security-notifications", daemon=True)
        notify_worker.start()
    try:
        yield
    finally:
        stop_event.set()
        worker.join(timeout=2)
        if notify_worker:
            notify_worker.join(timeout=2)

app = FastAPI(
    title="Elsewhere API",
    version="1.1.0",
    description="Travel discovery, itinerary planning and vehicle booking API",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

app.include_router(api, prefix="/api/v1")

app.middleware("http")(rate_limit_middleware)
app.middleware("http")(bot_protection_middleware)

@app.middleware("http")
async def security_event_capture(request: Request, call_next):
    response = await call_next(request)
    persist_security_event(request, response)
    return response

# Reject unrecognised Host headers. Configure ALLOWED_HOSTS with public API hostnames.
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[host.strip() for host in settings.allowed_hosts.split(",") if host.strip()],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

@app.middleware("http")
async def security_headers_and_https(request: Request, call_next):
    # TLS termination should happen at the trusted ingress/load balancer. Set
    # --proxy-headers only behind that trusted proxy; do not trust client headers here.
    if settings.enforce_https and request.url.scheme != "https":
        target = request.url.replace(scheme="https")
        response = RedirectResponse(str(target), status_code=308)
    else:
        response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.get("/health", tags=["operations"])
def health():
    return {"status": "ok", "service": "elsewhere-api", "version": app.version}


@app.websocket("/api/v1/admin/security/live")
async def admin_security_live(websocket: WebSocket, access_token: str = ""):
    """Admin alert stream using Redis Pub/Sub across API instances, with polling fallback."""
    try:
        payload = jwt.decode(access_token, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        with SessionLocal() as auth_db:
            user = auth_db.get(User, user_id) if user_id else None
            if (not user or not user.is_active or user.role.value != "admin"
                    or int(payload.get("ver", 0)) != int(user.auth_token_version or 0)):
                await websocket.close(code=4403)
                return
    except (JWTError, TypeError, ValueError):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    from app.core.security_events import ALERT_CHANNEL, ALERT_STREAM
    from app.core.redis_security import get_redis_client
    import json
    import time
    client = get_redis_client()
    pubsub = None
    stream_cursor = "0-0"
    stream_enabled = False
    if client is not None:
        try:
            # Replay retained stream entries on connect, then advance the cursor.
            stream_enabled = bool(client.exists(ALERT_STREAM))
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(ALERT_CHANNEL)
        except Exception:
            logger = __import__("logging").getLogger("elsewhere.security.websocket")
            logger.exception("Redis Pub/Sub subscription failed; using polling fallback")
            pubsub = None
    last_signature = None
    last_heartbeat = 0.0
    try:
        while True:
            event = None
            stream_events = []
            if client is not None and stream_enabled:
                try:
                    batches = await asyncio.to_thread(client.xread, {ALERT_STREAM: stream_cursor}, count=100, block=1000)
                    for _stream, entries in batches:
                        for event_id, fields in entries:
                            stream_cursor = event_id
                            stream_events.append((event_id, fields))
                except Exception:
                    stream_enabled = False
            if pubsub is not None:
                try:
                    event = await asyncio.to_thread(pubsub.get_message, timeout=0.1)
                except Exception:
                    pubsub = None
            elif not stream_events:
                await asyncio.sleep(1)
            now = time.monotonic()
            changed = bool(stream_events or (event and event.get("type") == "message"))
            if changed or pubsub is None or now - last_heartbeat >= 30:
                with SessionLocal() as db:
                    rows = db.query(SecurityAlert).order_by(desc(SecurityAlert.created_at)).limit(50).all()
                    alerts = [{"id": row.id, "event_type": row.event_type, "severity": row.severity,
                        "title": row.title, "summary": row.summary, "event_count": row.event_count,
                        "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]
                signature = tuple((a["id"], a["status"], a["event_count"]) for a in alerts)
                if signature != last_signature:
                    await websocket.send_json({"type": "security_alert_snapshot", "alerts": alerts,
                        "sent_at": __import__("datetime").datetime.utcnow().isoformat(),
                        "delivery": "redis_stream" if stream_enabled else ("redis_pubsub" if pubsub is not None else "polling_fallback"),
                        "stream_event_ids": [event_id for event_id, _fields in stream_events]})
                    last_signature = signature
                last_heartbeat = now
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        if pubsub is not None:
            try:
                pubsub.close()
            except Exception:
                pass
