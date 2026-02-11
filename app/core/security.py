from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def create_jwt_token(user: User) -> str:
    """사용자 정보로 JWT 토큰 생성 (만료 없음)"""
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "tv": user.token_version,  # token_version: 강제 로그아웃용
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None, description="사용자 API Key (하위 호환)"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT Bearer 토큰 또는 X-API-Key 헤더로 사용자를 인증합니다.
    JWT가 우선이며, 없으면 X-API-Key로 폴백합니다.
    """

    # ── 1. JWT Bearer 토큰 인증 ──
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 토큰이 유효하지 않습니다. 변조되었거나 형식이 올바르지 않습니다.",
            )

        user_id = payload.get("sub")
        token_version = payload.get("tv")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT 토큰에 사용자 정보가 없습니다.",
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

    # ── 2. X-API-Key 헤더 폴백 (하위 호환) ──
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
