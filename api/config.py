from functools import lru_cache

from pydantic_settings import BaseSettings


# AUD-036 / AUD-037: in production we refuse to boot with these defaults.
# They're only acceptable for local dev where the env vars aren't set.
DEFAULT_ADMIN_KEY = "sp_admin_0000000000000000000000000000dead"  # nosec
DEFAULT_SECRET_KEY = "change-me-in-production"  # nosec


class InsecureDefaultError(RuntimeError):
    """Raised at startup when an env var is missing or set to a known default in production."""


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://soundpulse:soundpulse_dev@localhost:5432/soundpulse"
    database_url_sync: str = "postgresql://soundpulse:soundpulse_dev@localhost:5432/soundpulse"
    redis_url: str = "redis://localhost:6379/0"
    api_admin_key: str = DEFAULT_ADMIN_KEY
    api_secret_key: str = DEFAULT_SECRET_KEY
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
    groq_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def assert_secure_in_production(self) -> None:
        """Refuse to boot in production with insecure defaults. Called at app startup."""
        if self.environment.lower() != "production":
            return
        problems: list[str] = []
        if self.api_admin_key == DEFAULT_ADMIN_KEY or not self.api_admin_key:
            problems.append("API_ADMIN_KEY is unset or equal to the documented default")
        if self.api_secret_key == DEFAULT_SECRET_KEY or not self.api_secret_key:
            problems.append("API_SECRET_KEY is unset or equal to the documented default")
        if problems:
            raise InsecureDefaultError(
                "Refusing to boot in ENVIRONMENT=production: "
                + "; ".join(problems)
                + ". Set the env vars before starting the API."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.assert_secure_in_production()
    return settings
