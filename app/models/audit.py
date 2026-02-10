from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, BigInteger, JSON


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    user_id: Optional[UUID] = Field(
        default=None, foreign_key="llm_app.users.id"
    )
    action: str = Field(max_length=64)
    target_type: Optional[str] = Field(default=None, max_length=64)
    target_id: Optional[str] = Field(default=None, max_length=128)
    old_value: Optional[Any] = Field(sa_column=Column(JSON, nullable=True))
    new_value: Optional[Any] = Field(sa_column=Column(JSON, nullable=True))
    ip_address: Optional[str] = Field(default=None, max_length=45)
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class LoginHistory(SQLModel, table=True):
    __tablename__ = "login_history"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    user_id: Optional[UUID] = Field(
        default=None, foreign_key="llm_app.users.id"
    )
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=512)
    success: bool = Field(default=True)
    failure_reason: Optional[str] = Field(default=None, max_length=128)
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

