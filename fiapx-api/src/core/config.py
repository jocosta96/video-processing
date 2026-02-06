from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql://fiapx:fiapx@localhost:5432/fiapx"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"

    # MinIO/S3
    minio_endpoint: str = "http://localhost:9000"
    minio_external_endpoint: str | None = None  # For presigned URLs (external access)
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "fiapx-videos"

    # Security
    jwt_secret: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # Limits
    max_video_size_mb: int = 500
    video_retention_days: int = 7
    presigned_url_expiry_seconds: int = 900

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]

    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
