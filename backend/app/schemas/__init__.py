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
    question: str
    # 多轮对话：携带历史，后端截断窗口
    history: list[tuple[str, str]] = []


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]


class QuotaOut(BaseModel):
    plan: str
    doc_used: int
    doc_limit: int
    question_used: int
    question_limit: int
