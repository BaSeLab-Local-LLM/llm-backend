from datetime import datetime
from typing import Optional, Union, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Conversation ─────────────────────────────────────────────────────────────


class ConversationCreate(BaseModel):
    """대화방 생성 요청"""
    title: Optional[str] = Field(default="새 대화", max_length=256)
    model: Optional[str] = Field(default=None, max_length=128)


class ConversationRename(BaseModel):
    """대화방 이름 변경 요청"""
    title: str = Field(min_length=1, max_length=256)


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
    role: str = Field(min_length=1, max_length=16)  # 'system', 'user', 'assistant'
    content: str = Field(min_length=1, max_length=100_000)  # 최대 10만 자


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


# ─── OpenAI 멀티모달 Content Parts ───────────────────────────────────────────


class TextContentPart(BaseModel):
    """텍스트 content part (OpenAI 멀티모달 형식)"""
    type: Literal["text"]
    text: str = Field(max_length=100_000)


class ImageUrlDetail(BaseModel):
    """이미지 URL 상세 (base64 data URI 또는 URL)"""
    url: str = Field(max_length=10_000_000)  # base64 인코딩된 이미지 포함


class ImageContentPart(BaseModel):
    """이미지 content part (OpenAI 멀티모달 형식)"""
    type: Literal["image_url"]
    image_url: ImageUrlDetail


# Union 타입: 텍스트 또는 이미지
ContentPart = Union[TextContentPart, ImageContentPart]


# ─── Chat Completion Proxy ───────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """
    LLM 채팅 메시지 (OpenAI 호환 멀티모달 형식)

    content는 다음 두 형식을 모두 지원합니다:
      - str: 텍스트만 포함 (하위 호환)
      - list[ContentPart]: 텍스트 + 이미지 혼합 (멀티모달)
    """
    role: str = Field(min_length=1, max_length=16)
    content: Union[str, list[ContentPart]]


class ChatCompletionRequest(BaseModel):
    """LLM 채팅 프록시 요청 검증"""
    model: str = Field(max_length=128)
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    stream: bool = False
    max_tokens: Optional[int] = Field(default=None, le=8192)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)

