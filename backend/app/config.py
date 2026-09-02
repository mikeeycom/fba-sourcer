"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All values can be overridden via environment variables.
    Example: export CLAUDE_API_KEY=sk-...
    """

    # API Keys
    claude_api_key: str
    keepa_api_key: str

    # SP-API (Amazon fee estimates) - from Seller Central > Develop Apps
    sp_api_client_id: str
    sp_api_client_secret: str
    sp_api_refresh_token: str

    # Server
    app_title: str = "FBA Sourcer"
    app_version: str = "0.1.0"
    debug: bool = False

    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()  # type: ignore