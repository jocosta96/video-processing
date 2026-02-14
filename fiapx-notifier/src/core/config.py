from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    database_url: str = "postgresql://fiapx:fiapx@localhost:5432/fiapx"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@fiapx.com"

    video_retention_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
