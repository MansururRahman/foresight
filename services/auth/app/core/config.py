from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Auth service configuration. Environment variables are prefixed with AUTH_."""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_", env_file=(".env", ".env.local"), extra="ignore"
    )

    env: str = "dev"
    database_url: str
    jwt_private_key_file: str = ""
    jwt_private_key_pem: str = ""
    jwt_issuer: str = "foresight-auth"
    jwt_audience: str = "foresight-api"
    access_ttl_seconds: int = 900
    refresh_ttl_days: int = 30
    cookie_secure: bool = False
    web_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
