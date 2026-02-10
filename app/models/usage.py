from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, BigInteger, Float


class UsageLog(SQLModel, table=True):
    __tablename__ = "usage_logs"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    user_id: UUID = Field(foreign_key="llm_app.users.id")
    model_name: str = Field(max_length=128)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    duration_ms: Optional[float] = Field(
        sa_column=Column(Float, nullable=True)
    )
    status_code: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

