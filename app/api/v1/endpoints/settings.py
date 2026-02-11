from datetime import time as dt_time, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import text, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin_user
from app.models.property import OperationSchedule, SystemSetting
from app.models.user import User
from app.schemas.settings import (
    LLMAvailabilityResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
    SystemSettingResponse,
    SystemSettingUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["Settings"])


# ─── Public ───────────────────────────────────────────────────────────────────


@router.get("/availability", response_model=LLMAvailabilityResponse)
async def check_availability(
    db: AsyncSession = Depends(get_db),
):
    """
    현재 LLM 사용 가능 여부 확인

    llm_app.v_llm_availability 뷰를 조회하여
    비상 정지 여부 및 운영 시간 스케줄을 확인합니다.
    """
    # 보안: 이 쿼리는 하드코딩된 뷰 조회이며 사용자 입력을 포함하지 않음.
    # SQL 인젝션 위험 없음. 향후 수정 시 반드시 파라미터화된 쿼리를 사용할 것.
    result = await db.execute(
        text("SELECT llm_available, emergency_enabled, schedule_mode, within_schedule FROM llm_app.v_llm_availability")
    )
    row = result.first()

    if row is None:
        return LLMAvailabilityResponse(
            llm_available=False,
            message="시스템 설정을 조회할 수 없습니다.",
        )

    llm_available = row.llm_available

    # 상세 메시지 생성
    if not row.emergency_enabled:
        message = "비상 정지 상태입니다. LLM 추론이 비활성화되어 있습니다."
    elif row.schedule_mode and not row.within_schedule:
        message = "현재 운영 시간이 아닙니다."
    elif llm_available:
        message = "LLM 서비스가 정상 운영 중입니다."
    else:
        message = "LLM 서비스를 사용할 수 없습니다."

    return LLMAvailabilityResponse(
        llm_available=llm_available,
        message=message,
    )


# ─── Admin: Operation Schedules ──────────────────────────────────────────────


def _schedule_to_response(s: OperationSchedule) -> ScheduleResponse:
    """OperationSchedule 모델 → ScheduleResponse 변환 헬퍼"""
    return ScheduleResponse(
        id=s.id,
        day_of_week=s.day_of_week,
        start_time=s.start_time.strftime("%H:%M"),
        end_time=s.end_time.strftime("%H:%M"),
        is_active=s.is_active,
    )


@router.get(
    "/schedules",
    response_model=List[ScheduleResponse],
    summary="운영 스케줄 전체 조회 (관리자)",
)
async def get_schedules(
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """7일(일~토) 운영 스케줄을 모두 반환합니다."""
    result = await db.execute(
        select(OperationSchedule).order_by(OperationSchedule.day_of_week)
    )
    schedules = result.scalars().all()
    return [_schedule_to_response(s) for s in schedules]


@router.put(
    "/schedules/{day_of_week}",
    response_model=ScheduleResponse,
    summary="요일별 스케줄 수정 (관리자)",
)
async def update_schedule(
    day_of_week: int = Path(..., ge=0, le=6, description="요일 (0=일, 1=월, ..., 6=토)"),
    body: ScheduleUpdateRequest = ...,
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 요일의 운영 스케줄(시작/종료 시간, 활성 여부)을 수정합니다."""
    result = await db.execute(
        select(OperationSchedule).where(OperationSchedule.day_of_week == day_of_week)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"요일 {day_of_week}에 대한 스케줄을 찾을 수 없습니다.",
        )

    if body.start_time is not None:
        h, m = map(int, body.start_time.split(":"))
        schedule.start_time = dt_time(h, m)
    if body.end_time is not None:
        h, m = map(int, body.end_time.split(":"))
        schedule.end_time = dt_time(h, m)
    if body.is_active is not None:
        schedule.is_active = body.is_active

    schedule.updated_at = datetime.now(timezone.utc)

    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)

    return _schedule_to_response(schedule)


# ─── Admin: System Settings ──────────────────────────────────────────────────


@router.get(
    "/system",
    response_model=List[SystemSettingResponse],
    summary="시스템 설정 전체 조회 (관리자)",
)
async def get_system_settings(
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """모든 시스템 설정(schedule_enabled, llm_enabled 등)을 반환합니다."""
    result = await db.execute(select(SystemSetting))
    settings = result.scalars().all()
    return [
        SystemSettingResponse(key=s.key, value=s.value, description=s.description)
        for s in settings
    ]


@router.put(
    "/system/{key}",
    response_model=SystemSettingResponse,
    summary="시스템 설정 수정 (관리자)",
)
async def update_system_setting(
    key: str = Path(..., max_length=64, description="설정 키 (예: schedule_enabled)"),
    body: SystemSettingUpdateRequest = ...,
    admin_user: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 시스템 설정의 값을 변경합니다."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"설정 '{key}'을(를) 찾을 수 없습니다.",
        )

    setting.value = body.value
    setting.updated_by = admin_user.id
    setting.updated_at = datetime.now(timezone.utc)

    db.add(setting)
    await db.commit()
    await db.refresh(setting)

    return SystemSettingResponse(
        key=setting.key,
        value=setting.value,
        description=setting.description,
    )

