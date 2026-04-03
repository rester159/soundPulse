from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://soundpulse:soundpulse_dev@localhost:5432/soundpulse"
    database_url_sync: str = "postgresql://soundpulse:soundpulse_dev@localhost:5432/soundpulse"
    redis_url: str = "redis://localhost:6379/0"
    api_admin_key: str = "sp_admin_0000000000000000000000000000dead"
    api_secret_key: str = "change-me-in-production"
    environment: str = "development"
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    soundpulse_api_url: str = "http://localhost:8000"
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    chartmetric_api_key: str = ""
    shazam_rapidapi_key: str = ""
    apple_music_team_id: str = ""
    apple_music_key_id: str = ""
    apple_music_private_key_path: str = ""
    celery_broker_url: str = ""
    celery_result_backend: str = ""
    genius_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
