from typing import Optional
from uuid import UUID
from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import (
    create_jwt_token,
    generate_fingerprint,
    get_current_user,
    hash_fingerprint,
    require_admin_user,
    set_fingerprint_cookie,
)
from app.models.user import User

router = APIRouter(prefix="/users", tags=["Users"])


# ─── Schemas ──────────────────────────────────────────────────────────────────


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
    current_password: str = Field(min_length=1, max_length=12)
    new_password: str = Field(min_length=1, max_length=12)


class AdminUserListItem(BaseModel):
    """관리자용 사용자 목록 아이템"""
    id: UUID
    username: str
    role: str
    is_active: bool
    daily_token_limit: Optional[int] = None
    token_version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── 일반 사용자 엔드포인트 ──────────────────────────────────────────────────


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
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경 → token_version 증가 → 새 JWT + 새 fingerprint 반환"""
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
    # 비밀번호 변경 시 token_version 증가 → 다른 세션 강제 로그아웃
    current_user.token_version += 1
    await db.flush()

    # 새 fingerprint + JWT 토큰 발급 (현재 세션 유지)
    fingerprint = generate_fingerprint()
    fp_hash = hash_fingerprint(fingerprint)
    new_token = create_jwt_token(current_user, fingerprint_hash=fp_hash)

    # HttpOnly 쿠키에 새 fingerprint 설정
    set_fingerprint_cookie(response, fingerprint)

    return {
        "message": "비밀번호가 변경되었습니다. 다른 기기의 세션은 로그아웃됩니다.",
        "access_token": new_token,
    }


# ─── 관리자 엔드포인트 ──────────────────────────────────────────────────────


@router.get("/admin/list", response_model=list[AdminUserListItem])
async def admin_list_users(
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """관리자: 전체 사용자 목록 조회"""
    result = await db.execute(
        select(User).order_by(User.created_at.asc())
    )
    users = result.scalars().all()
    return [
        AdminUserListItem(
            id=u.id,
            username=u.username,
            role=u.role.value,
            is_active=u.is_active,
            daily_token_limit=u.daily_token_limit,
            token_version=u.token_version,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/admin/{user_id}/force-logout")
async def admin_force_logout(
    user_id: UUID,
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """관리자: 특정 사용자 강제 로그아웃 (token_version 증가)"""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    target_user.token_version += 1
    await db.flush()

    return {
        "message": f"'{target_user.username}' 사용자의 모든 세션이 강제 로그아웃되었습니다.",
        "new_token_version": target_user.token_version,
    }


@router.post("/admin/{user_id}/toggle-active")
async def admin_toggle_active(
    user_id: UUID,
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """관리자: 사용자 활성/비활성 토글"""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    # 자기 자신 비활성화 방지
    if target_user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="자기 자신을 비활성화할 수 없습니다.",
        )

    target_user.is_active = not target_user.is_active
    # 비활성화 시 강제 로그아웃
    if not target_user.is_active:
        target_user.token_version += 1

    await db.flush()

    return {
        "message": f"'{target_user.username}' 사용자가 {'활성화' if target_user.is_active else '비활성화'}되었습니다.",
        "is_active": target_user.is_active,
    }
