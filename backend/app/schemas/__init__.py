"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_id: str
    captcha_code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    captcha_id: str
    captcha_code: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class ResendRequest(BaseModel):
    email: EmailStr
    code: str = ""  # 占位（重发逻辑不使用邮箱验证码）
    captcha_id: str
    captcha_code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    captcha_id: str
    captcha_code: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ForgotPasswordResponse(BaseModel):
    email: str
    smtp_configured: bool
    # 开发模式（SMTP 未配置）：重置链接直接返回页面，明确标注；生产恒为 None
    dev_reset_url: str | None = None


class RegisterResponse(BaseModel):
    email: str
    verification_required: bool
    smtp_configured: bool
    # 开发模式（SMTP 未配置）才返回验证码本身；生产恒为 None
    dev_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentOut(BaseModel):
    id: int
    filename: str
    status: str
    page_count: int
    chunk_count: int
    summary: str = ""
    suggestions: list[str] = []

    model_config = {"from_attributes": True}


class Citation(BaseModel):
    chunk_id: str
    page: int
    snippet: str


class ChatRequest(BaseModel):
    document_id: int
    question: str
    # 多轮会话 ID：不传则新建并返回；传同一 ID 即延续上下文
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    session_id: str
    # "llm" = DeepSeek 生成；"extractive" = 未配置 Key 的原文摘录降级
    mode: str = "llm"


class QuotaOut(BaseModel):
    plan: str
    doc_used: int
    doc_limit: int
    question_used: int
    question_limit: int
