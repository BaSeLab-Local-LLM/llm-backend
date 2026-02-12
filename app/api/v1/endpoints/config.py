"""공개 설정 API — 인증 불필요"""

import os

from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("")
async def get_public_config():
    """
    프론트엔드가 사용할 공개 설정값을 반환합니다.
    인증이 필요하지 않으며, 민감 정보는 포함하지 않습니다.
    """
    max_model_len = int(os.environ.get("VLLM_MAX_MODEL_LEN", "4096"))
    # 응답 생성용 예약 토큰 (컨텍스트 길이에 비례하여 조정)
    if max_model_len <= 8192:
        reserved_output = 512
    elif max_model_len <= 32768:
        reserved_output = 1024
    else:
        reserved_output = 2048  # 128K+ 컨텍스트에서는 긴 응답 허용
    max_input_tokens = max_model_len - reserved_output

    return {
        "max_model_len": max_model_len,
        "reserved_output_tokens": reserved_output,
        "max_input_tokens": max_input_tokens,
    }
