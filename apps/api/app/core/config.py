import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    enforce_https: bool = False
    database_url: str = "sqlite:///./elsewhere.db"
    secret_key: str = "dev-only-change-this-secret"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8081"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    upload_dir: str = "./uploads"
    otp_secret: str = "dev-only-otp-secret-change-me"
    otp_delivery_mode: str = "console"
    payment_provider: str = "unconfigured"
    payment_secret_key: str = ""
    document_scan_mode: str = "manual"
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_requests: int = 120
    auth_rate_limit_window_seconds: int = 300
    auth_rate_limit_attempts: int = 10
    rate_limit_max_tracked_clients: int = 20000
    turnstile_secret_key: str = ""
    turnstile_required: bool = False
    suspicious_auth_failure_threshold: int = 8
    suspicious_auth_window_seconds: int = 600
    rate_limit_backend: str = "memory"
    redis_url: str = ""
    redis_socket_timeout_seconds: float = 1.5
    redis_required: bool = False
    redis_key_prefix: str = "elsewhere:security"
    audit_checkpoint_signing_key: str = ""
    audit_checkpoint_key_id: str = "primary-v1"
    audit_archive_enabled: bool = False
    audit_archive_s3_bucket: str = ""
    audit_archive_s3_region: str = "ap-south-1"
    audit_archive_s3_prefix: str = "elsewhere/audit-evidence"
    audit_archive_retention_days: int = 2555
    audit_archive_object_lock_mode: str = "COMPLIANCE"
    audit_archive_kms_key_id: str = ""
    audit_archive_retry_base_seconds: int = 60
    audit_archive_retry_max_seconds: int = 21600
    audit_archive_failure_webhook_url: str = ""
    audit_compliance_enabled: bool = False
    audit_compliance_period: str = "daily"
    audit_compliance_retention_warning_days: int = 30

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}

    def validate_runtime_configuration(self) -> None:
        """Fail closed for unsafe production configuration before serving traffic."""
        if not self.is_production:
            return
        problems = []
        if len(self.secret_key) < 32 or self.secret_key == "dev-only-change-this-secret":
            problems.append("SECRET_KEY must be a unique secret of at least 32 characters")
        if len(self.otp_secret) < 32 or self.otp_secret == "dev-only-otp-secret-change-me":
            problems.append("OTP_SECRET must be a unique secret of at least 32 characters")
        if self.otp_delivery_mode.strip().lower() == "console":
            problems.append("OTP_DELIVERY_MODE=console is not allowed in production")
        origins = [value.strip() for value in self.cors_origins.split(",") if value.strip()]
        if not origins or "*" in origins:
            problems.append("CORS_ORIGINS must contain explicit trusted origins; wildcard is forbidden")
        if any(not value.startswith("https://") for value in origins):
            problems.append("all production CORS_ORIGINS must use HTTPS")
        if not self.enforce_https:
            problems.append("ENFORCE_HTTPS must be true in production")
        database_url = self.database_url.strip().lower()
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
            problems.append("DATABASE_URL must use PostgreSQL in production")
        if self.access_token_minutes < 5 or self.access_token_minutes > 60:
            problems.append("ACCESS_TOKEN_MINUTES must be between 5 and 60 in production")
        if self.rate_limit_enabled and self.rate_limit_backend.strip().lower() != "redis":
            problems.append("RATE_LIMIT_BACKEND=redis is required when rate limiting is enabled in production")
        if self.rate_limit_backend.strip().lower() == "redis" and not self.redis_url.strip():
            problems.append("REDIS_URL is required when RATE_LIMIT_BACKEND=redis")
        if self.redis_required and not self.redis_url.strip():
            problems.append("REDIS_URL is required when REDIS_REQUIRED is enabled")
        if self.payment_provider.strip().lower() not in {"", "unconfigured", "none"} and not self.payment_secret_key.strip():
            problems.append("PAYMENT_SECRET_KEY is required when a payment provider is configured")
        hosts = [value.strip() for value in self.allowed_hosts.split(",") if value.strip()]
        if not hosts or "*" in hosts:
            problems.append("ALLOWED_HOSTS must contain explicit hostnames; wildcard is forbidden")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))

settings = Settings()
