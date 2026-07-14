from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, SecretStr
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )
    
    app_env: str
    algorithm: str
    secret_key: SecretStr
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
    data_source_name: str
    allowed_origins: str
    database_url: str
    zendesk_fernet_key: str

    # Zendesk — Google Sheets ingestion (Apps Script web app used as a thin
    # proxy in front of the spreadsheet; see app/zendesk/services/sheets_client.py)
    google_apps_script_url: str = ""

    # Zendesk — completion/failure emails sent by the Celery bulk job worker
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, secret_key: SecretStr) -> str:
        if len(secret_key) < 32:
            raise ValueError("Invalid secret key")
        insecure_values = {"changeme", "secret", "dev", "production", "test", "local", "development"}
        if secret_key in insecure_values:
            raise ValueError("Weak secret key")
        return secret_key
    
    @field_validator("data_source_name")
    @classmethod
    def validate_database_url(cls, database_url: str) -> str:
        if not database_url.startswith("postgresql://"):
            raise ValueError("Invalid database URL")
        return database_url
    
    @field_validator("zendesk_fernet_key")
    @classmethod
    def validate_zendesk_frenet_key(cls, key: str) -> str:
        """Validates the Zendesk Frenet key"""
        if len(key) != 44:
            raise ValueError("Invalid zendesk frenet key")
        try:
            from cryptography.fernet import Fernet
            Fernet(key.encode())
            return key
        except Exception as e:
            raise ValueError(f"Invalid zendesk frenet key: {str(e)}")
    
    
@lru_cache
def get_settings() -> Settings:
    return Settings()

# Not recommended for production, it will load the variables at import
# Which is not recommended
#settings = get_settings()