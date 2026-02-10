from datetime import datetime, time
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime, Time, SmallInteger


class SystemSetting(SQLModel, table=True):
    __tablename__ = "system_settings"
    __table_args__ = {"schema": "llm_app"}

    key: str = Field(primary_key=True, max_length=64)
    value: str
    description: Optional[str] = Field(default=None, max_length=256)
    updated_by: Optional[UUID] = Field(
        default=None, foreign_key="llm_app.users.id"
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class OperationSchedule(SQLModel, table=True):
    __tablename__ = "operation_schedules"
    __table_args__ = {"schema": "llm_app"}

    id: Optional[int] = Field(default=None, primary_key=True)
    day_of_week: int = Field(
        sa_column=Column(SmallInteger, nullable=False)
    )
    start_time: time = Field(sa_column=Column(Time, nullable=False))
    end_time: time = Field(sa_column=Column(Time, nullable=False))
    is_active: bool = Field(default=True)
    created_by: Optional[UUID] = Field(
        default=None, foreign_key="llm_app.users.id"
    )
    created_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: Optional[datetime] = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

