"""Regression coverage for upgrading a partially migrated local SQLite database."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings


class TestExistingDatabaseUpgrade(unittest.TestCase):
    def test_upgrade_keeps_existing_webhook_table_and_adds_expense_columns(self):
        api_root = Path(__file__).resolve().parents[1]
        previous_url = settings.database_url
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "legacy.sqlite"
            settings.database_url = f"sqlite:///{database}"
            config = Config(str(api_root / "alembic.ini"))
            try:
                command.upgrade(config, "0012_push_notifications")
                connection = sqlite3.connect(database)
                connection.executescript("""
                    CREATE TABLE webhook_subscriptions (
                        id VARCHAR(36) PRIMARY KEY,
                        owner_id VARCHAR(36) NOT NULL REFERENCES users(id),
                        target_url VARCHAR(500) NOT NULL,
                        secret VARCHAR(128) DEFAULT '' NOT NULL,
                        event_types TEXT DEFAULT '[]' NOT NULL,
                        active BOOLEAN DEFAULT 1 NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    );
                    CREATE INDEX ix_webhook_subscriptions_owner_id
                        ON webhook_subscriptions(owner_id);
                """)
                connection.close()

                command.upgrade(config, "head")

                connection = sqlite3.connect(database)
                itinerary_columns = {row[1] for row in connection.execute("PRAGMA table_info(itineraries)")}
                webhook_indexes = {row[1] for row in connection.execute("PRAGMA index_list(webhook_subscriptions)")}
                revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                connection.close()

                self.assertIn("expenses_json", itinerary_columns)
                self.assertIn("receipts_json", itinerary_columns)
                self.assertIn("ix_webhook_subscriptions_active", webhook_indexes)
                self.assertEqual(revision, "0057_email_retry_worker_leases")
            finally:
                settings.database_url = previous_url


if __name__ == "__main__":
    unittest.main()
