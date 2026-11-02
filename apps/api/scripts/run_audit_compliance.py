"""Run scheduled audit compliance reporting once; schedule with cron."""
import argparse
from datetime import datetime
from app.db import SessionLocal
from app.services.audit_compliance import run_scheduled_audit_compliance

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["hourly","daily","weekly"])
    args = parser.parse_args()
    from app.core.config import settings
    if args.period:
        settings.audit_compliance_period = args.period
    db = SessionLocal()
    try:
        print(run_scheduled_audit_compliance(db))
    finally:
        db.close()

if __name__ == "__main__":
    main()
