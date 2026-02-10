from pydantic import BaseModel


class LLMAvailabilityResponse(BaseModel):
    """LLM 사용 가능 여부 응답"""
    llm_available: bool
    message: str

