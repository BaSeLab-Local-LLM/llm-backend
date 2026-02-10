from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.settings import LLMAvailabilityResponse

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/availability", response_model=LLMAvailabilityResponse)
async def check_availability(
    db: AsyncSession = Depends(get_db),
):
    """
    현재 LLM 사용 가능 여부 확인

    llm_app.v_llm_availability 뷰를 조회하여
    비상 정지 여부 및 운영 시간 스케줄을 확인합니다.
    """
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

