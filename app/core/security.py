import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

# ─── Fingerprint Cookie 바인딩 ────────────────────────────────────────────────
# JWT만 탈취해서는 인증 불가. HttpOnly 쿠키와 쌍으로 검증합니다.
# 쿠키는 JavaScript로 읽을 수 없으므로 다른 브라우저로 복사할 수 없습니다.
# ──────────────────────────────────────────────────────────────────────────────

FGP_COOKIE_NAME = "_fgp"
FGP_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1년


def generate_fingerprint() -> str:
    """세션 바인딩용 랜덤 핑거프린트 생성 (64자 hex)"""
    return secrets.token_hex(32)


def hash_fingerprint(fingerprint: str) -> str:
    """핑거프린트를 SHA-256 해시로 변환 (JWT에 저장)"""
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def create_jwt_token(user: User, fingerprint_hash: str | None = None) -> str:
    """사용자 정보로 JWT 토큰 생성 (만료 시간 포함)"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "tv": user.token_version,  # token_version: 강제 로그아웃용
        "iat": now,                # 발급 시간
        "exp": now + timedelta(hours=settings.JWT_EXPIRE_HOURS),  # 만료 시간
    }
    if fingerprint_hash:
        payload["fgp"] = fingerprint_hash  # fingerprint hash: 세션 바인딩용
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def set_fingerprint_cookie(response, fingerprint: str) -> None:
    """Response에 HttpOnly 핑거프린트 쿠키를 설정합니다."""
    response.set_cookie(
        key=FGP_COOKIE_NAME,
        value=fingerprint,
        httponly=True,         # JavaScript 접근 차단
        samesite="strict",     # CSRF 방지
        secure=not settings.DEBUG,  # 프로덕션(HTTPS)에서는 True
        path="/api",           # API 요청에만 쿠키 전송
        max_age=FGP_COOKIE_MAX_AGE,
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None, description="사용자 API Key (하위 호환)"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT Bearer 토큰 또는 X-API-Key 헤더로 사용자를 인증합니다.
    JWT가 우선이며, 없으면 X-API-Key로 폴백합니다.

    JWT에 fingerprint(fgp) 클레임이 있는 경우:
        HttpOnly 쿠키의 fingerprint와 SHA-256 해시를 대조합니다.
        → JWT만 복사해서는 인증 불가 (세션 바인딩)
    """

    # ── 1. JWT Bearer 토큰 인증 ──
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 토큰이 만료되었습니다. 다시 로그인해주세요.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 토큰이 유효하지 않습니다.",
            )

        user_id = payload.get("sub")
        token_version = payload.get("tv")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 토큰에 사용자 정보가 없습니다.",
            )

        # ── Fingerprint Cookie 검증 (세션 바인딩) ──
        fgp_claim = payload.get("fgp")
        if fgp_claim:
            cookie_fgp = request.cookies.get(FGP_COOKIE_NAME, "")
            if not cookie_fgp or hash_fingerprint(cookie_fgp) != fgp_claim:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="세션 바인딩 검증 실패: 토큰이 다른 브라우저/세션에서 사용되었습니다. 다시 로그인해주세요.",
                )

        result = await db.execute(
            select(User).where(User.id == UUID(user_id), User.is_active.is_(True))
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없거나 비활성화된 계정입니다.",
            )

        # token_version 검증: 강제 로그아웃 감지
        if token_version is not None and user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="세션이 만료되었습니다. 관리자에 의해 강제 로그아웃되었습니다. 다시 로그인해주세요.",
            )

        return user

    # ── 2. X-API-Key 헤더 폴백 (하위 호환, fingerprint 불필요) ──
    if x_api_key:
        result = await db.execute(
            select(User).where(User.api_key == x_api_key, User.is_active.is_(True))
        )
        user = result.scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 API Key입니다.",
            )

        # API Key 만료 체크
        if user.api_key_expires_at is not None:
            from datetime import datetime, timezone

            if user.api_key_expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API Key가 만료되었습니다.",
                )

        return user

    # ── 3. 인증 정보 없음 ──
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 필요합니다. JWT 토큰 또는 API Key를 제공해주세요.",
    )


async def require_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """관리자 권한 검증"""
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return current_user
