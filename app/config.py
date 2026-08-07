"""Application configuration — loads from environment / .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    DATABASE_URL: str = "postgresql://lusajo1:lusajo321@localhost:5432/fazza-prod"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"
    APP_ENV: str = "development"
    APP_NAME: str = "FAZZA API"
    UPLOAD_DIR: str = "uploads"
    API_PUBLIC_URL: str = "http://127.0.0.1:8000"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
