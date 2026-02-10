import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
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
    ID/PW 검증 후 API Key 반환

    1. users 테이블에서 username 조회
    2. bcrypt로 비밀번호 검증
    3. 성공 시 api_key 반환
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
        # 로그인 실패 기록
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

    # 5. API Key 만료 확인
    if user.api_key_expires_at is not None:
        from datetime import datetime, timezone

        if user.api_key_expires_at < datetime.now(timezone.utc):
            login_log = LoginHistory(
                user_id=user.id,
                ip_address=client_ip,
                user_agent=user_agent,
                success=False,
                failure_reason="key_expired",
            )
            db.add(login_log)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key가 만료되었습니다. 관리자에게 문의하세요.",
            )

    # 6. 로그인 성공 기록
    login_log = LoginHistory(
        user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        success=True,
    )
    db.add(login_log)

    return LoginResponse(
        api_key=user.api_key,
        role=user.role.value,
        token_limit=user.daily_token_limit,
    )

