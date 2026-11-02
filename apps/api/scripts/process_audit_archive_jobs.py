"""Run due audit archive jobs once; invoke from cron or a scheduler."""
import argparse
from app.db import SessionLocal
from app.services.audit_archive_jobs import process_due_archive_jobs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        print(process_due_archive_jobs(db, args.batch_size))
    finally:
        db.close()

if __name__ == "__main__":
    main()
