"""设置路由：用户自备 DeepSeek API Key（BYOK）。

GET  /api/settings/llm          当前 Key 状态（脱敏）与生效模式
PUT  /api/settings/llm          保存/清除用户 Key
POST /api/settings/llm/verify   校验 Key 是否可用（调 DeepSeek models 接口）
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


def _mask(key: str) -> str:
    return f"{key[:6]}***{key[-4:]}" if len(key) > 12 else "***"


class LlmKeyRequest(BaseModel):
    deepseek_api_key: str = ""


class LlmStatusOut(BaseModel):
    configured: bool
    masked: str | None = None
    mode: str  # user / global / extractive


class VerifyOut(BaseModel):
    ok: bool
    message: str


def _status(user: User) -> LlmStatusOut:
    settings = get_settings()
    if user.deepseek_api_key:
        return LlmStatusOut(configured=True, masked=_mask(user.deepseek_api_key), mode="user")
    if settings.deepseek_api_key:
        return LlmStatusOut(configured=True, masked=_mask(settings.deepseek_api_key), mode="global")
    return LlmStatusOut(configured=False, masked=None, mode="extractive")


@router.get("/llm", response_model=LlmStatusOut)
def llm_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),  # noqa: ARG001 统一签名
) -> LlmStatusOut:
    return _status(user)


@router.put("/llm", response_model=LlmStatusOut)
def save_llm_key(
    req: LlmKeyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LlmStatusOut:
    key = req.deepseek_api_key.strip()
    if key and not key.startswith("sk-"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "DeepSeek Key 以 sk- 开头，请检查是否复制完整")
    user.deepseek_api_key = key
    db.commit()
    return _status(user)


@router.post("/llm/verify", response_model=VerifyOut)
def verify_llm_key(
    req: LlmKeyRequest,
    user: User = Depends(get_current_user),
) -> VerifyOut:
    """校验 Key 可用性：用该 Key 请求 DeepSeek 模型列表（不消耗 token）。"""
    key = req.deepseek_api_key.strip() or user.deepseek_api_key
    if not key:
        return VerifyOut(ok=False, message="未填写 Key")
    settings = get_settings()
    try:
        client = OpenAI(api_key=key, base_url=settings.deepseek_base_url, timeout=15)
        models = client.models.list()
        names = [m.id for m in models.data][:5]
        return VerifyOut(ok=True, message=f"Key 有效，可用模型示例：{', '.join(names)}")
    except Exception as exc:  # noqa: BLE001 网络与鉴权错误统一报告
        logger.info("Key 校验失败：%s", type(exc).__name__)
        return VerifyOut(ok=False, message="Key 无效或网络不通，请检查后重试")
