from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    database_url: str = "postgresql://fiapx:fiapx@localhost:5432/fiapx"
    redis_url: str = "redis://localhost:6379"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"

    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "fiapx-videos"

    worker_concurrency: int = 2
    max_retries: int = 3
    retry_delay: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
