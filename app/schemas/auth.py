from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    """로그인 요청"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """로그인 응답 - API Key 반환"""
    api_key: str
    role: str
    token_limit: Optional[int] = None

