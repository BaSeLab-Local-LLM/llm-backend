from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    """로그인 요청"""
    username: str = Field(min_length=1, max_length=12)
    password: str = Field(min_length=1, max_length=12)


class LoginResponse(BaseModel):
    """로그인 응답 - JWT 토큰 반환"""
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
