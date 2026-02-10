import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Enum as SAEnum, DateTime, Text, BigInteger


class MessageRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class FeedbackType(str, enum.Enum):
    thumbs_up = "thumbs_up"
    thumbs_down = "thumbs_down"


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[UUID] = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="llm_app.users.id")
    title: Optional[str] = Field(default="새 대화", max_length=256)
    model_name: Optional[str] = Field(default=None, max_length=128)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    conversation_id: UUID = Field(foreign_key="llm_app.conversations.id")
    role: MessageRole = Field(
        sa_column=Column(
            SAEnum(
                MessageRole, name="message_role", schema="llm_app", create_type=False
            ),
            nullable=False,
        )
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    token_count: Optional[int] = Field(default=None)
    feedback: Optional[FeedbackType] = Field(
        sa_column=Column(
            SAEnum(
                FeedbackType,
                name="feedback_type",
                schema="llm_app",
                create_type=False,
            ),
            nullable=True,
        )
    )
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

