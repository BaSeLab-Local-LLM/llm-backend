import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.api.v1.api import api_router

logger = logging.getLogger(__name__)


# ─── Rate Limiter ─────────────────────────────────────────────────────────────
# 리버스 프록시(Nginx) 뒤에서 실제 클라이언트 IP를 사용
def _get_real_client_ip(request: Request) -> str:
    """X-Forwarded-For 또는 X-Real-IP 헤더에서 실제 클라이언트 IP를 추출"""
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # 첫 번째 IP가 실제 클라이언트 IP (쉼표로 구분된 목록)
        return x_forwarded_for.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=_get_real_client_ip, default_limits=["60/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행되는 이벤트"""
    # Startup
    yield
    # Shutdown
    from app.core.db import engine
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="LLM 플랫폼 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
    # 프로덕션에서는 API 문서 비활성화
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Rate Limiter 등록
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS 설정 ────────────────────────────────────────────────────────────────
# ALLOWED_ORIGINS 환경변수로 허용 오리진을 제어합니다.
# 예: ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
# 비어있으면 localhost만 허용하지만 경고를 출력합니다.
if not settings.ALLOWED_ORIGINS:
    logger.warning(
        "⚠  ALLOWED_ORIGINS가 설정되지 않았습니다. "
        "기본값 http://localhost:3000만 허용합니다. "
        "프로덕션에서는 반드시 ALLOWED_ORIGINS를 명시적으로 설정하세요."
    )
_allowed_origins = [
    origin.strip()
    for origin in settings.ALLOWED_ORIGINS.split(",")
    if origin.strip()
] if settings.ALLOWED_ORIGINS else ["http://localhost:3000"]

# 와일드카드(*) 사용 차단 — 자격 증명(credentials)을 함께 사용하면 보안 위험
if "*" in _allowed_origins:
    logger.error(
        "🚨 ALLOWED_ORIGINS에 '*'(와일드카드)가 포함되어 있습니다! "
        "allow_credentials=True와 함께 사용하면 보안 위험이 발생합니다. "
        "특정 도메인을 명시하세요."
    )
    _allowed_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# ─── 요청 크기 제한 미들웨어 ──────────────────────────────────────────────────
MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024  # 10MB


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """요청 본문 크기를 제한하여 DoS 공격 방지"""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": "요청 본문이 너무 큽니다."},
        )
    return await call_next(request)


# ─── 보안 헤더 미들웨어 ──────────────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """보안 관련 HTTP 응답 헤더 추가"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


# API v1 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "ok"}

