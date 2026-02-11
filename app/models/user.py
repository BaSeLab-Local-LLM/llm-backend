import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Enum as SAEnum, DateTime


class UserRole(str, enum.Enum):
    admin = "admin"
    student = "student"


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[UUID] = Field(default=None, primary_key=True)
    api_key: str = Field(max_length=128)
    username: str = Field(max_length=64)
    password_hash: str = Field(max_length=256)
    role: UserRole = Field(
        sa_column=Column(
            SAEnum(UserRole, name="user_role", schema="llm_app", create_type=False),
            nullable=False,
            default="student",
        )
    )
    is_active: bool = Field(default=True)
    failed_login_attempts: int = Field(default=0)
    display_name: Optional[str] = Field(default=None, max_length=64)
    class_name: Optional[str] = Field(default=None, max_length=64)
    daily_token_limit: Optional[int] = Field(default=100000)
    api_key_expires_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    token_version: int = Field(default=1)
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
