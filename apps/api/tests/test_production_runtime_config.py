"""Production runtime configuration guard regression tests."""
import unittest
from app.core.config import Settings


def valid_production_settings(**overrides):
    values = dict(
        app_env="production",
        enforce_https=True,
        database_url="postgresql+psycopg://user:pass@db.example/elsewhere",
        secret_key="s" * 48,
        otp_secret="o" * 48,
        otp_delivery_mode="email",
        cors_origins="https://app.example.com",
        allowed_hosts="api.example.com",
        access_token_minutes=30,
        rate_limit_enabled=True,
        rate_limit_backend="redis",
        redis_url="redis://redis.example:6379/0",
        payment_provider="unconfigured",
    )
    values.update(overrides)
    return Settings(**values)


class TestProductionRuntimeConfig(unittest.TestCase):
    def test_valid_production_configuration_passes(self):
        valid_production_settings().validate_runtime_configuration()

    def test_rejects_sqlite_database(self):
        settings = valid_production_settings(database_url="sqlite:///./prod.db")
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
            settings.validate_runtime_configuration()

    def test_rejects_memory_rate_limiting(self):
        settings = valid_production_settings(rate_limit_backend="memory")
        with self.assertRaisesRegex(RuntimeError, "RATE_LIMIT_BACKEND"):
            settings.validate_runtime_configuration()

    def test_rejects_missing_redis_url(self):
        settings = valid_production_settings(redis_url="")
        with self.assertRaisesRegex(RuntimeError, "REDIS_URL"):
            settings.validate_runtime_configuration()

    def test_rejects_long_access_token_lifetime(self):
        settings = valid_production_settings(access_token_minutes=120)
        with self.assertRaisesRegex(RuntimeError, "ACCESS_TOKEN_MINUTES"):
            settings.validate_runtime_configuration()

    def test_requires_payment_secret_for_configured_provider(self):
        settings = valid_production_settings(payment_provider="stripe", payment_secret_key="")
        with self.assertRaisesRegex(RuntimeError, "PAYMENT_SECRET_KEY"):
            settings.validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
