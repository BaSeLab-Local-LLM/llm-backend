from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.user import User


async def get_current_user(
    x_api_key: str = Header(..., description="사용자 API Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """X-API-Key 헤더를 통해 현재 사용자를 인증합니다."""
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

