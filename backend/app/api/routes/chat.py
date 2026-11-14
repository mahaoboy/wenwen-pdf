"""问答路由：检索 → 生成 → 引用映射，支持多轮对话。"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import Document, Message, QuotaUsage, User
from app.db.session import get_db
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/documents/{doc_id}/chat", response_model=ChatResponse)
def chat(
    doc_id: int,
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    settings = get_settings()

    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    if doc.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "文档尚未解析完成，请稍候")

    # 额度闸：免费 20 次提问
    usage = db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).first()
    q_used = usage.question_count if usage else 0
    q_limit = settings.free_question_limit  # TODO(阶段5): 按 user.plan 取对应档位额度
    if q_used >= q_limit:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"提问次数已达上限（{q_limit}），请升级套餐")

    # TODO(阶段3): 混合检索 → LLM 生成 → 引用映射
    # TODO(阶段3): 问答结果缓存命中则直接返回（成本闸）
    answer = "（开发中）检索与生成流水线接入后返回。"
    citations: list[dict] = []

    db.add(Message(document_id=doc.id, role="user", content=req.question))
    db.add(Message(document_id=doc.id, role="assistant", content=answer, citations=json.dumps(citations, ensure_ascii=False)))
    if usage is None:
        usage = QuotaUsage(user_id=user.id, question_count=1)
        db.add(usage)
    else:
        usage.question_count += 1
    db.commit()
    return ChatResponse(answer=answer, citations=citations)


@router.get("/documents/{doc_id}/messages")
def list_messages(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    msgs = db.query(Message).filter(Message.document_id == doc.id).order_by(Message.created_at).all()
    return [
        {"role": m.role, "content": m.content, "citations": json.loads(m.citations)}
        for m in msgs
    ]
