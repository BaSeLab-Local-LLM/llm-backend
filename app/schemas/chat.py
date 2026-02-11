from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Conversation ─────────────────────────────────────────────────────────────


class ConversationCreate(BaseModel):
    """대화방 생성 요청"""
    title: Optional[str] = "새 대화"
    model: Optional[str] = None


class ConversationRename(BaseModel):
    """대화방 이름 변경 요청"""
    title: str = Field(min_length=1, max_length=100)


class ConversationOut(BaseModel):
    """대화방 응답"""
    id: UUID
    title: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Message ──────────────────────────────────────────────────────────────────


class MessageCreate(BaseModel):
    """메시지 저장 요청"""
    conv_id: UUID
    role: str  # 'system', 'user', 'assistant'
    content: str


class MessageOut(BaseModel):
    """메시지 응답"""
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageSaveResponse(BaseModel):
    """메시지 저장 완료 응답"""
    id: int
    status: str = "saved"

