from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./elsewhere.db"
    secret_key: str = "dev-only-change-this-secret"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5173,http://localhost:8081"
    upload_dir: str = "./uploads"
settings = Settings()
