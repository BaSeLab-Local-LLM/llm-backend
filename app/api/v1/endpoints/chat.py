from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.chat import Conversation, Message, MessageRole
from app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
    MessageSaveResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


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
    # 대화방 소유권 확인
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

    # 메시지 조회 (시간순 정렬)
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
    """
    메시지 저장 (User/Assistant)

    LiteLLM 호출 전(User 메시지)과 후(Assistant 메시지)에 각각 호출합니다.
    """
    # 대화방 소유권 확인
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

    # role 유효성 검증
    try:
        message_role = MessageRole(body.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 role입니다. 허용값: {[r.value for r in MessageRole]}",
        )

    # 메시지 저장
    message = Message(
        conversation_id=body.conv_id,
        role=message_role,
        content=body.content,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)

    return MessageSaveResponse(id=message.id)

