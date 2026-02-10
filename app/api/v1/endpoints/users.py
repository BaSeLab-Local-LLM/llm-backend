from typing import Optional
from uuid import UUID
from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


class UserInfoResponse(BaseModel):
    """사용자 정보 응답"""
    id: UUID
    username: str
    role: str
    is_active: bool
    daily_token_limit: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    """비밀번호 변경 요청"""
    current_password: str
    new_password: str = Field(min_length=1, max_length=10)


@router.get("/me", response_model=UserInfoResponse)
async def get_my_info(
    current_user: User = Depends(get_current_user),
):
    """현재 로그인된 사용자 정보 조회"""
    return UserInfoResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        is_active=current_user.is_active,
        daily_token_limit=current_user.daily_token_limit,
        created_at=current_user.created_at,
    )


@router.post("/me/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경"""
    # 현재 비밀번호 검증
    try:
        valid = bcrypt.checkpw(
            body.current_password.encode("utf-8"),
            current_user.password_hash.encode("utf-8"),
        )
    except Exception:
        valid = False

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 올바르지 않습니다.",
        )

    # 새 비밀번호 해시 생성
    new_hash = bcrypt.hashpw(
        body.new_password.encode("utf-8"),
        bcrypt.gensalt(rounds=8),
    ).decode("utf-8")

    current_user.password_hash = new_hash
    await db.flush()

    return {"message": "비밀번호가 변경되었습니다."}

