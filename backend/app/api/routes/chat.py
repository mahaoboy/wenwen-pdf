"""问答路由：检索 → 生成 → 引用校验 → 多轮对话（模块4）。

POST /api/chat/ask：提问（带 session 多轮 + 额度闸 + 缓存闸 + 幻觉闸）
GET  /api/chat/history：拉取某文档某会话的历史消息
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db import Document, Message, QuotaUsage, User
from app.db.session import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services.cache import get as cache_get, put as cache_put
from app.services.generation.answer import generate_answer
from app.services.generation.citations import extract_citations
from app.services.metrics import client_ip, record
from app.services.retrieval import hybrid

router = APIRouter(prefix="/chat", tags=["chat"])

HISTORY_ROUNDS = 3  # 多轮上下文窗口：最近 3 轮


def _history(db: Session, document_id: int, session_id: str) -> list[tuple[str, str]]:
    """取该会话最近 N 轮 (user, assistant) 问答对，按时间序。"""
    if not session_id:
        return []
    msgs = (
        db.query(Message)
        .filter(Message.document_id == document_id, Message.session_id == session_id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    pairs: list[tuple[str, str]] = []
    pending: str | None = None
    for m in msgs:
        if m.role == "user":
            pending = m.content
        elif m.role == "assistant" and pending is not None:
            pairs.append((pending, m.content))
            pending = None
    return pairs[-HISTORY_ROUNDS:]


def _require_doc(db: Session, doc_id: int, user: User) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    if doc.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "文档尚未解析完成，请稍候")
    return doc


@router.post("/ask", response_model=ChatResponse)
def ask(
    request: Request,
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    ip = client_ip(request)
    settings = get_settings()
    doc = _require_doc(db, req.document_id, user)
    session_id = req.session_id or uuid.uuid4().hex
    history = _history(db, doc.id, session_id)
    last_round = tuple(history[-1:]) if history else ()

    # 成本闸：相同文档+上下文+问题的缓存命中直接返回，不扣额度（消息仍落库保持会话历史连贯）
    cached = cache_get(doc.id, req.question, last_round)
    if cached is not None:
        db.add(Message(document_id=doc.id, session_id=session_id, role="user", content=req.question))
        db.add(
            Message(
                document_id=doc.id,
                session_id=session_id,
                role="assistant",
                content=cached["answer"],
                citations=json.dumps(cached["citations"], ensure_ascii=False),
            )
        )
        db.commit()
        return ChatResponse(
            answer=cached["answer"],
            citations=cached["citations"],
            session_id=session_id,
            mode=cached["mode"],
        )

    # 额度闸：免费版提问次数硬限制
    usage = db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).first()
    q_used = usage.question_count if usage else 0
    q_limit = settings.free_question_limit  # TODO(阶段5): 按 user.plan 取对应档位额度
    if q_used >= q_limit:
        record("quota_blocked", ip=ip, user_id=user.id)
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, f"提问次数已达上限（{q_limit}），请升级套餐")

    # 混合检索 → 生成（用户自备 Key 优先）→ 引用校验（幻觉闸：引用必须来自真实检索结果）
    retrieved = hybrid.retrieve(doc.id, req.question)
    generated = generate_answer(req.question, retrieved, history, user_api_key=user.deepseek_api_key)
    citations = extract_citations(generated["answer"], retrieved)

    db.add(Message(document_id=doc.id, session_id=session_id, role="user", content=req.question))
    db.add(
        Message(
            document_id=doc.id,
            session_id=session_id,
            role="assistant",
            content=generated["answer"],
            citations=json.dumps(citations, ensure_ascii=False),
        )
    )
    if usage is None:
        db.add(QuotaUsage(user_id=user.id, question_count=1))
    else:
        usage.question_count += 1
    db.commit()

    cache_put(doc.id, req.question, {"answer": generated["answer"], "citations": citations, "mode": generated["mode"]}, last_round)
    record("chat", ip=ip, user_id=user.id, meta={"question_chars": len(req.question), "mode": generated["mode"]})
    return ChatResponse(answer=generated["answer"], citations=citations, session_id=session_id, mode=generated["mode"])


@router.get("/history")
def history(
    document_id: int,
    session_id: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    doc = _require_doc(db, document_id, user)
    q = db.query(Message).filter(Message.document_id == doc.id)
    if session_id:
        q = q.filter(Message.session_id == session_id)
    msgs = q.order_by(Message.created_at, Message.id).all()
    return [
        {
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "citations": json.loads(m.citations),
        }
        for m in msgs
    ]
