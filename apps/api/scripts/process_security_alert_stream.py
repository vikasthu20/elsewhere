"""Consume security alert events with Redis consumer groups and a dead-letter stream."""
import argparse
import json
import logging
import os
import socket
import time

from app.core.redis_security import get_redis_client
from app.core.security_events import ALERT_STREAM

logger = logging.getLogger("elsewhere.security.stream_worker")
GROUP = "elsewhere-security-alert-workers"
DLQ = "elsewhere:security:alert-stream:dead-letter:v1"


def process(fields):
    # Validate the compact event envelope. Alert details remain in PostgreSQL.
    if fields.get("type") != "alert_changed" or not fields.get("alert_id"):
        raise ValueError("Invalid security alert event envelope")
    return {"alert_id": fields["alert_id"], "type": fields["type"]}


def run(batch_size=25, max_deliveries=5, block_ms=5000):
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis is required for the security stream worker")
    try:
        client.xgroup_create(ALERT_STREAM, GROUP, id="0-0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    consumer = f"{socket.gethostname()}-{os.getpid()}"
    while True:
        batches = client.xreadgroup(GROUP, consumer, {ALERT_STREAM: ">"}, count=batch_size, block=block_ms)
        for _stream, entries in batches:
            for event_id, fields in entries:
                try:
                    result = process(fields)
                    # Acknowledge only after successful validation/handling.
                    logger.info("Accepted security alert event %s", result["alert_id"])
                    client.xack(ALERT_STREAM, GROUP, event_id)
                except Exception as exc:
                    pending = client.xpending_range(ALERT_STREAM, GROUP, event_id, event_id, 1)
                    deliveries = int(pending[0].get("times_delivered", 1)) if pending else 1
                    if deliveries >= max_deliveries:
                        client.xadd(DLQ, {"source_id": event_id, "error": str(exc)[:500],
                                          "payload": json.dumps(fields)}, maxlen=5000, approximate=True)
                        client.xack(ALERT_STREAM, GROUP, event_id)
                        logger.error("Moved event %s to dead-letter stream", event_id)
                    else:
                        logger.warning("Event %s will be retried (%s/%s): %s",
                                       event_id, deliveries, max_deliveries, exc)
        # Reclaim abandoned pending entries from workers that exited unexpectedly.
        try:
            reclaimed = client.xautoclaim(ALERT_STREAM, GROUP, consumer, min_idle_time=60000,
                                          start_id="0-0", count=batch_size)
            for event_id, fields in reclaimed[1]:
                try:
                    process(fields)
                    client.xack(ALERT_STREAM, GROUP, event_id)
                except Exception as exc:
                    pending = client.xpending_range(ALERT_STREAM, GROUP, event_id, event_id, 1)
                    deliveries = int(pending[0].get("times_delivered", 1)) if pending else 1
                    if deliveries >= max_deliveries:
                        client.xadd(DLQ, {"source_id": event_id, "error": str(exc)[:500],
                                          "payload": json.dumps(fields)}, maxlen=5000, approximate=True)
                        client.xack(ALERT_STREAM, GROUP, event_id)
        except Exception:
            logger.exception("Unable to reclaim pending security alert events")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-deliveries", type=int, default=5)
    parser.add_argument("--block-ms", type=int, default=5000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(max(1, min(args.batch_size, 500)), max(1, args.max_deliveries), max(100, args.block_ms))
