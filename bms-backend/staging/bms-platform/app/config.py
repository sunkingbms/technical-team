from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )
    
    app_env: str
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    postgres_exporter_data_source_name: str
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, secret_key: str) -> str:
        if len(secret_key) < 32:
            raise ValueError("Invalid secret key")
        insecure_values = {"changeme", "secret", "dev", "production", "test", "local", "development"}
        if secret_key.lower() in insecure_values:
            raise ValueError("Weak secret key")
        return secret_key
    
    @field_validator("postgres_exporter_data_source_name")
    @classmethod
    def validate_database_url(cls, database_url: str) -> str:
        if not database_url.startswith("postgresql://"):
            raise ValueError("Invalid database URL")
        return database_url
    
    
@lru_cache
def get_settings() -> Settings:
    return Settings()

# Not recommended for production, it will load the variables at import
# Which is not recommended
#settings = get_settings()