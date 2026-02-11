from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.chat import Conversation, Message, MessageRole
from app.schemas.chat import (
    ChatCompletionRequest,
    ConversationCreate,
    ConversationRename,
    ConversationOut,
    MessageCreate,
    MessageOut,
    MessageSaveResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ─── LLM Proxy ────────────────────────────────────────────────────────────────


@router.post("/completions")
async def proxy_chat_completions(
    body: ChatCompletionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    LLM 채팅 프록시 엔드포인트

    JWT 인증 → 사용자의 LiteLLM API Key로 LiteLLM에 프록시.
    프론트엔드는 LiteLLM API Key를 알 필요 없이 JWT만으로 LLM 사용 가능.
    강제 로그아웃(token_version 증가) 시 즉시 LLM 접근도 차단됨.

    Pydantic으로 입력 검증: 메시지 수, 길이, 파라미터 범위를 제한합니다.
    """
    # Pydantic 모델 → dict 변환 (None 값 제외)
    request_body = body.model_dump(exclude_none=True)

    litellm_url = f"{settings.LITELLM_URL}/v1/chat/completions"
    is_stream = body.stream

    if is_stream:
        # SSE 스트리밍 프록시
        async def stream_generator():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    litellm_url,
                    json=request_body,
                    headers={
                        "Authorization": f"Bearer {current_user.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=120.0,
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield f"data: {error_body.decode()}\n\n"
                        return
                    async for chunk in response.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # 일반 (non-stream) 프록시
        async with httpx.AsyncClient() as client:
            response = await client.post(
                litellm_url,
                json=request_body,
                headers={
                    "Authorization": f"Bearer {current_user.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
            return response.json()


# ─── Conversations ────────────────────────────────────────────────────────────


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 대화방 목록 조회 (최신순)"""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.is_active.is_(True),
        )
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    return conversations


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 대화방 생성"""
    conversation = Conversation(
        user_id=current_user.id,
        title=body.title,
        model_name=body.model,
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: UUID,
    body: ConversationRename,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대화방 이름 변경"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = result.scalars().first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대화방을 찾을 수 없습니다.",
        )
    conversation.title = body.title
    await db.flush()
    await db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대화방 소프트 삭제 (is_active = False)"""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalars().first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대화방을 찾을 수 없습니다.",
        )

    conversation.is_active = False
    await db.flush()
    return None


# ─── Messages ─────────────────────────────────────────────────────────────────


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
async def list_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 대화방의 메시지 전체 조회 (시간순)"""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalars().first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대화방을 찾을 수 없습니다.",
        )

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return messages


@router.post("/messages", response_model=MessageSaveResponse, status_code=201)
async def save_message(
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """메시지 저장 (User/Assistant)"""
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == body.conv_id,
            Conversation.user_id == current_user.id,
        )
    )
    conversation = conv_result.scalars().first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대화방을 찾을 수 없습니다.",
        )

    try:
        message_role = MessageRole(body.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 메시지 역할(role)입니다.",
        )

    message = Message(
        conversation_id=body.conv_id,
        role=message_role,
        content=body.content,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)

    return MessageSaveResponse(id=message.id)
