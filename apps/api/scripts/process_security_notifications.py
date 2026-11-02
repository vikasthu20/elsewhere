"""Run pending security notification deliveries, with optional supervised looping."""
import argparse
import json
import sys
import time
import traceback

from app.services.security_notification_delivery import process_batch


def _run_once(batch_size: int, max_attempts: int, lease_seconds: int) -> dict:
    return process_batch(batch_size, max_attempts, lease_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-attempts", type=int, default=8)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--loop", action="store_true",
                        help="Keep running until interrupted; restart after failures.")
    parser.add_argument("--interval-seconds", type=int, default=15)
    args = parser.parse_args()
    interval = max(1, min(args.interval_seconds, 300))
    if not args.loop:
        print(json.dumps(_run_once(args.batch_size, args.max_attempts, args.lease_seconds)))
        raise SystemExit(0)
    while True:
        try:
            result = _run_once(args.batch_size, args.max_attempts, args.lease_seconds)
            print(json.dumps(result), flush=True)
        except Exception as exc:
            print(json.dumps({
                "error": str(exc)[:500],
                "traceback": traceback.format_exc()[-1500:],
            }), file=sys.stderr, flush=True)
        time.sleep(interval)
