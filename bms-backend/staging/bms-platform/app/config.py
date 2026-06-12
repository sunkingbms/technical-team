from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    data_source_name: str
    allowed_origins: str
    database_url: str

    google_apps_script_url: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, secret_key: str) -> str:
        if len(secret_key) < 32:
            raise ValueError("Secret key must be at least 32 characters")
        insecure = {"changeme", "secret", "dev", "production", "test", "local", "development"}
        if secret_key.lower() in insecure:
            raise ValueError("Weak secret key")
        return secret_key

    @field_validator("data_source_name")
    @classmethod
    def validate_data_source_name(cls, v: str) -> str:
        if not v.startswith("postgresql://"):
            raise ValueError("data_source_name must start with postgresql://")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
