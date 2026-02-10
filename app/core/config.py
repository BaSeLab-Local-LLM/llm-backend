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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

