"""认证路由：注册（邮箱验证）/ 登录 / 图片验证码 / 验证码重发。

流程：
- GET  /api/auth/captcha        图片验证码（登录、注册、重发前必须过）
- POST /api/auth/register       校验验证码 + 邮箱唯一 → 建号（未验证）→ 发验证码
- POST /api/auth/verify-email   邮箱验证码校验 → 标记已验证 → 直接发 JWT
- POST /api/auth/resend         重发验证码（60s 冷却，需图片验证码）
- POST /api/auth/login          图片验证码 + 密码；未验证邮箱 → 403

SMTP 未配置时进入开发模式：验证码直接返回给页面（明确标注），流程不受阻。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db import User
from app.db.session import get_db
from app.schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResendRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.services.captcha import new_captcha, verify_captcha
from app.services.email_codes import issue, seconds_until_resend, verify as verify_email_code
from app.services.email_sender import email_configured, send_verification_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_UNVERIFIED_MSG = "邮箱未验证，请输入邮件中的 6 位验证码完成验证"


@router.get("/captcha")
def get_captcha() -> dict:
    cid, image = new_captcha()
    out: dict = {"captcha_id": cid, "image": image}
    from app.core.config import get_settings

    if get_settings().captcha_echo:  # 仅自动化测试环境开启
        from app.services.captcha import _store

        out["answer"] = _store.get(cid, ("", 0))[0]
    return out


def _require_captcha(captcha_id: str, captcha_code: str) -> None:
    if not verify_captcha(captcha_id or "", captcha_code or ""):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片验证码错误或已过期，请刷新后重试")


@router.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    _require_captcha(req.captcha_id, req.captcha_code)

    email = req.email.strip().lower()
    exists = db.query(User).filter(User.email == email).first()
    if exists:
        hint = "该邮箱已注册，请直接登录" if exists.email_verified else "该邮箱已注册但未验证，请完成邮箱验证"
        raise HTTPException(status.HTTP_400_BAD_REQUEST, hint)

    user = User(email=email, password_hash=hash_password(req.password), email_verified=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    issued = issue(email)
    if issued is None:  # 冷却期内（理论少见：新注册用户）
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "验证码发送过于频繁，请稍后再试")
    code, _ = issued
    sent = send_verification_email(email, code)
    logger.info("注册待验证 email=%s 发信=%s", email, sent)

    return RegisterResponse(
        email=email,
        verification_required=True,
        smtp_configured=email_configured(),
        # 开发模式（SMTP 未配置）：验证码直接返回页面，明确标注；配置后恒为 None
        dev_code=None if sent else code,
    )


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在，请先注册")
    if user.email_verified:
        return TokenResponse(access_token=create_access_token(str(user.id)))  # 已验证直接登录
    if not verify_email_code(email, req.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")

    user.email_verified = True
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/resend", response_model=RegisterResponse)
def resend_code(req: ResendRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    """重发验证码：需要新的图片验证码。"""
    user = db.query(User).filter(User.email == req.email.strip().lower()).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    if user.email_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该邮箱已验证，无需重发")
    _require_captcha(req.captcha_id, req.captcha_code)

    email = user.email
    issued = issue(email)
    if issued is None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"发送过于频繁，请 {seconds_until_resend(email)} 秒后再试",
        )
    code, _ = issued
    sent = send_verification_email(email, code)
    return RegisterResponse(
        email=email,
        verification_required=True,
        smtp_configured=email_configured(),
        dev_code=None if sent else code,
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    _require_captcha(req.captcha_id, req.captcha_code)

    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _UNVERIFIED_MSG)
    return TokenResponse(access_token=create_access_token(str(user.id)))
