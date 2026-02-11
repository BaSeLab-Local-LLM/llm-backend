from typing import Optional
from uuid import UUID
from datetime import datetime

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import (
    get_current_user,
    require_admin_user,
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
    display_name: Optional[str] = None
    class_name: Optional[str] = None
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
    failed_login_attempts: int = 0
    display_name: Optional[str] = None
    class_name: Optional[str] = None
    daily_token_limit: Optional[int] = None
    token_version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUpdateUserRequest(BaseModel):
    """관리자: 사용자 프로필 수정 요청"""
    username: Optional[str] = Field(default=None, min_length=1, max_length=32)
    display_name: Optional[str] = Field(default=None, max_length=64)
    class_name: Optional[str] = Field(default=None, max_length=64)


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
        display_name=current_user.display_name,
        class_name=current_user.class_name,
        daily_token_limit=current_user.daily_token_limit,
        created_at=current_user.created_at,
    )


@router.post("/me/change-password", status_code=200)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경 → token_version 증가 → 모든 기기 강제 로그아웃"""
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

    # 새 비밀번호 해시 생성 (bcrypt cost=12, 보안 강화)
    new_hash = bcrypt.hashpw(
        body.new_password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")

    current_user.password_hash = new_hash
    # 비밀번호 변경 시 token_version 증가 → 모든 기기(현재 포함) 강제 로그아웃
    current_user.token_version += 1
    # 응답 전 명시적 commit (get_db cleanup의 commit은 응답 전송 이후 실행되므로,
    # 클라이언트가 즉시 재로그인 시 새 비밀번호가 반영되지 않을 수 있음)
    await db.commit()

    return {
        "message": "비밀번호가 변경되었습니다. 모든 기기에서 로그아웃됩니다.",
        "require_relogin": True,
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
            failed_login_attempts=u.failed_login_attempts,
            display_name=u.display_name,
            class_name=u.class_name,
            daily_token_limit=u.daily_token_limit,
            token_version=u.token_version,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.patch("/admin/{user_id}", response_model=AdminUserListItem)
async def admin_update_user(
    user_id: UUID,
    body: AdminUpdateUserRequest,
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """관리자: 사용자 프로필 수정 (username, 이름, 수업)"""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    username_changed = False

    if body.username is not None and body.username != target_user.username:
        # username 중복 검사
        existing = await db.execute(
            select(User).where(User.username == body.username)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"'{body.username}'은(는) 이미 사용 중인 아이디입니다.",
            )
        target_user.username = body.username
        username_changed = True

    if body.display_name is not None:
        target_user.display_name = body.display_name or None  # 빈 문자열 → None
    if body.class_name is not None:
        target_user.class_name = body.class_name or None

    # username 변경 시 해당 사용자 강제 로그아웃
    if username_changed:
        target_user.token_version += 1

    await db.flush()
    await db.refresh(target_user)

    return AdminUserListItem(
        id=target_user.id,
        username=target_user.username,
        role=target_user.role.value,
        is_active=target_user.is_active,
        failed_login_attempts=target_user.failed_login_attempts,
        display_name=target_user.display_name,
        class_name=target_user.class_name,
        daily_token_limit=target_user.daily_token_limit,
        token_version=target_user.token_version,
        created_at=target_user.created_at,
    )


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
    if target_user.is_active:
        # 활성화 시 로그인 실패 횟수 초기화 (계정 잠금 해제)
        target_user.failed_login_attempts = 0
    else:
        # 비활성화 시 강제 로그아웃
        target_user.token_version += 1

    await db.flush()

    return {
        "message": f"'{target_user.username}' 사용자가 {'활성화' if target_user.is_active else '비활성화'}되었습니다.",
        "is_active": target_user.is_active,
    }
