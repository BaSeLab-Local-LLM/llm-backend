from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 환경변수 설정"""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://llmadmin:password@localhost:5432/litellm"

    # Application
    APP_NAME: str = "LLM Platform Backend"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # LiteLLM
    LITELLM_URL: str = "http://litellm:4000"
    LITELLM_MASTER_KEY: str = ""

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
