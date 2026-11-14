"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentOut(BaseModel):
    id: int
    filename: str
    status: str
    page_count: int
    chunk_count: int

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
