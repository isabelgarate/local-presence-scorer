from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API keys
    google_places_api_key: str
    rapidapi_key: str = ""

    # Scoring caps (log-scale normalization anchors)
    review_cap: int = 500
    follower_cap: int = 100_000

    # Rate limiting (req/s)
    google_rate_limit: float = 10.0
    instagram_rate_limit: float = 2.0

    # App
    log_level: str = "INFO"
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Module-level singleton — import this everywhere
settings = Settings()  # type: ignore[call-arg]
