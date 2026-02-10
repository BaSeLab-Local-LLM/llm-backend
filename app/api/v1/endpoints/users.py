from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
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

