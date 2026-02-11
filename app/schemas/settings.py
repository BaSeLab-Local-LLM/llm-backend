from typing import Optional

from pydantic import BaseModel, Field


class LLMAvailabilityResponse(BaseModel):
    """LLM 사용 가능 여부 응답"""
    llm_available: bool
    message: str


# ─── Operation Schedule ───────────────────────────────────────────────────────


class ScheduleResponse(BaseModel):
    """운영 스케줄 응답 (요일별)"""
    id: int
    day_of_week: int          # 0=일, 1=월, ..., 6=토
    start_time: str           # "HH:MM" 형식
    end_time: str             # "HH:MM" 형식
    is_active: bool


class ScheduleUpdateRequest(BaseModel):
    """운영 스케줄 수정 요청"""
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    is_active: Optional[bool] = None


# ─── System Settings ──────────────────────────────────────────────────────────


class SystemSettingResponse(BaseModel):
    """시스템 설정 응답"""
    key: str
    value: str
    description: Optional[str] = None


class SystemSettingUpdateRequest(BaseModel):
    """시스템 설정 수정 요청"""
    value: str = Field(min_length=1, max_length=256)

