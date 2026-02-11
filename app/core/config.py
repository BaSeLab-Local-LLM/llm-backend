from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """애플리케이션 환경변수 설정"""

    # Database — 기본값 없음: 환경변수 필수
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL 연결 문자열 (환경변수 필수)",
    )

    # Application
    APP_NAME: str = "LLM Platform Backend"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # CORS — 허용 오리진 목록 (쉼표 구분)
    ALLOWED_ORIGINS: str = ""

    # LiteLLM
    LITELLM_URL: str = "http://litellm:4000"
    LITELLM_MASTER_KEY: str = Field(
        ...,
        min_length=1,
        description="LiteLLM 마스터 키 (환경변수 필수)",
    )

    # JWT — 기본값 없음: 환경변수 필수, 최소 32자
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="JWT 서명 키 (최소 32자, 환경변수 필수)",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24  # JWT 토큰 만료 시간 (시간)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
