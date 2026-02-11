import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import create_jwt_token, get_current_user
from app.models.user import User
from app.models.audit import LoginHistory
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """bcrypt 해시 비밀번호 검증 (pgcrypto crypt 호환)"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    ID/PW 검증 후 JWT 토큰 반환

    1. users 테이블에서 username 조회
    2. bcrypt로 비밀번호 검증
    3. 성공 시 JWT access_token 반환
    """
    # 1. 사용자 조회
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalars().first()

    # 클라이언트 정보
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    # 2. 사용자 존재 확인
    if not user:
        login_log = LoginHistory(
            user_id=None,
            ip_address=client_ip,
            user_agent=user_agent,
            success=False,
            failure_reason="user_not_found",
        )
        db.add(login_log)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
        )

    # 3. 계정 활성 상태 확인
    if not user.is_active:
        login_log = LoginHistory(
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            success=False,
            failure_reason="account_disabled",
        )
        db.add(login_log)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    # 4. 비밀번호 검증
    if not verify_password(body.password, user.password_hash):
        login_log = LoginHistory(
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            success=False,
            failure_reason="invalid_password",
        )
        db.add(login_log)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 올바르지 않습니다.",
        )

    # 5. 로그인 성공 기록
    login_log = LoginHistory(
        user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        success=True,
    )
    db.add(login_log)

    # 6. JWT 토큰 생성
    access_token = create_jwt_token(user)

    return LoginResponse(
        access_token=access_token,
        role=user.role.value,
        username=user.username,
    )


@router.get("/verify")
async def verify_token(
    current_user: User = Depends(get_current_user),
):
    """
    JWT 토큰 사전 검증 엔드포인트 (Pre-flight check)

    LLM 프롬프트 전송 전에 호출하여 토큰의 유효성을 확인합니다.
    - JWT 서명 검증
    - token_version 일치 여부 (강제 로그아웃 감지)
    - 계정 활성 상태 확인

    토큰이 유효하면 {"valid": true}를 반환하고,
    유효하지 않으면 get_current_user에서 401을 반환합니다.
    """
    return {
        "valid": True,
        "username": current_user.username,
        "role": current_user.role.value,
    }


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """현재 로그인된 사용자 정보를 서버에서 검증 후 반환"""
    return {
        "username": current_user.username,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
    }
