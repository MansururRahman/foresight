from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API service configuration. Environment variables are prefixed with API_."""

    model_config = SettingsConfigDict(
        env_prefix="API_", env_file=(".env", ".env.local"), extra="ignore"
    )

    env: str = "dev"
    database_url: str
    auth_jwks_url: str = "http://localhost:8001/.well-known/jwks.json"
    jwt_issuer: str = "foresight-auth"
    jwt_audience: str = "foresight-api"
    web_origin: str = "http://localhost:3000"
    jwks_ttl_seconds: int = 600
    jwks_min_refetch_seconds: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
