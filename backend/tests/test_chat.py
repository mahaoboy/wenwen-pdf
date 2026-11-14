"""模块4测试：问答 + 引用校验 + 多轮对话 + 缓存/额度闸（stub 嵌入与 LLM，不依赖网络）。"""
import hashlib

import numpy as np
import pytest

from app.services.generation import answer as answer_svc
from app.services.generation import llm as llm_svc
from app.services.retrieval import embeddings

DIM = 64


def fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        v = np.zeros(DIM, dtype=np.float32)
        for ch in t:
            bucket = int(hashlib.md5(ch.encode()).hexdigest(), 16) % DIM
            v[bucket] += 1.0
        n = float(np.linalg.norm(v)) or 1.0
        out.append((v / n).tolist())
    return out


@pytest.fixture
def stub_embed(monkeypatch):
    monkeypatch.setattr(embeddings, "embed", fake_embed)
    yield


def _stub_llm_cite_first_chunk(monkeypatch):
    """假 LLM：从拼好的 prompt 里取第一个检索片段 chunk_id 并引用它（模拟真实引用行为）。"""

    def fake_completion(messages: list[dict], api_key: str | None = None, temperature: float = 0.1) -> str:
        cid = None
        for m in messages:
            if m["role"] == "user" and "【检索片段】" in m["content"]:
                cid = m["content"].split("【片段 ")[1].split("｜")[0]
                break
        return f"根据文档内容，相关条款如下 [来源:{cid}]。"

    monkeypatch.setattr(llm_svc, "chat_completion", fake_completion)
    monkeypatch.setattr(answer_svc.llm, "chat_completion", fake_completion)


def _current_user_id() -> int:
    """client fixture 每个用例新注册的用户（最新一条）。"""
    from app.db import User
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return db.query(User).order_by(User.id.desc()).first().id
    finally:
        db.close()


@pytest.fixture
def seeded_doc(client):
    """向 DB 灌一个归属于当前测试用户的已就绪文档（三条切片）。"""
    from app.db import Chunk, Document
    from app.db.session import SessionLocal

    doc_id = 876543
    user_id = _current_user_id()
    db = SessionLocal()
    try:
        db.add(Document(id=doc_id, user_id=user_id, filename="t.pdf", file_path="t.pdf", status="ready"))
        texts = [
            "甲方违反合同约定，应当承担违约责任，赔偿损失。",
            "乙方应当在收货后三十日内支付货款。",
            "本合同一式两份，自双方签字之日起生效。",
        ]
        for seq, text in enumerate(texts):
            db.add(Chunk(
                id=f"{doc_id}-c{seq}", document_id=doc_id, seq=seq, page=1,
                char_start=0, char_end=len(text), bbox_json="[]", text=text, snippet=text[:20],
            ))
        db.commit()
    finally:
        db.close()
    yield doc_id
    from app.services.retrieval import hybrid

    hybrid.delete_doc(doc_id)
    db = SessionLocal()
    try:
        db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
        db.query(Document).filter(Document.id == doc_id).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_answer_cache():
    """用例间清空问答缓存，避免同文档同问题的跨用例缓存串扰。"""
    from app.services.cache import _cache

    _cache.clear()
    yield
    _cache.clear()


def test_ask_extractive_with_citations(client, stub_embed, seeded_doc):
    """无 DEEPSEEK_API_KEY：抽取式降级，回答摘录原文并带合法引用。"""
    resp = client.post("/api/chat/ask", json={"document_id": seeded_doc, "question": "违约责任"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "extractive"
    assert data["answer"] and "违约" in data["answer"]
    assert data["citations"], "降级回答也应带引用"
    assert data["citations"][0]["chunk_id"] == f"{seeded_doc}-c0"
    assert data["session_id"]


def test_ask_llm_mode_citation_validation(client, stub_embed, seeded_doc, monkeypatch):
    """LLM 模式：引用来自检索结果，编造引用被丢弃。"""
    from app.core.config import get_settings

    settings = get_settings()
    old_key = settings.deepseek_api_key
    settings.deepseek_api_key = "test-key"
    _stub_llm_cite_first_chunk(monkeypatch)
    try:
        resp = client.post("/api/chat/ask", json={"document_id": seeded_doc, "question": "违约责任"})
        data = resp.json()
        assert data["mode"] == "llm"
        assert data["citations"][0]["chunk_id"] == f"{seeded_doc}-c0"

        # 编造引用：LLM 引用不存在的 chunk → 应被过滤为空
        monkeypatch.setattr(
            answer_svc.llm, "chat_completion", lambda msgs, api_key=None, temperature=0.1: "胡说 [来源:fake-c999]"
        )
        resp2 = client.post("/api/chat/ask", json={"document_id": seeded_doc, "question": "付款义务", "session_id": data["session_id"]})
        assert resp2.json()["citations"] == []
    finally:
        settings.deepseek_api_key = old_key


def test_ask_multi_turn_session(client, stub_embed, seeded_doc):
    """多轮对话：同 session_id 延续上下文，history 可查。"""
    r1 = client.post("/api/chat/ask", json={"document_id": seeded_doc, "question": "违约责任"}).json()
    sid = r1["session_id"]
    r2 = client.post(
        "/api/chat/ask",
        json={"document_id": seeded_doc, "question": "那货款呢？", "session_id": sid},
    ).json()
    assert r2["session_id"] == sid  # 同会话延续

    hist = client.get(f"/api/chat/history", params={"document_id": seeded_doc, "session_id": sid}).json()
    assert len(hist) == 4  # 2 轮 × (user + assistant)
    assert [m["role"] for m in hist] == ["user", "assistant", "user", "assistant"]
    assert hist[2]["content"] == "那货款呢？"


def test_ask_cache_hit_not_charged(client, stub_embed, seeded_doc):
    """成本闸：同问题同上下文二次提问命中缓存，不扣提问额度。"""
    q = {"document_id": seeded_doc, "question": "违约责任是什么"}
    r1 = client.post("/api/chat/ask", json=q).json()
    r2 = client.post("/api/chat/ask", json=q).json()  # 全新会话但上下文相同 → 命中
    assert r2["answer"] == r1["answer"]

    from app.db import QuotaUsage
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        from app.db import User

        user = db.query(User).filter(User.email.like("%@test.dev")).order_by(User.id.desc()).first()
        usage = db.query(QuotaUsage).filter(QuotaUsage.user_id == user.id).first()
        assert usage.question_count == 1, "缓存命中不应扣额度"
    finally:
        db.close()


def test_ask_doc_not_found_and_not_ready(client, stub_embed):
    assert client.post("/api/chat/ask", json={"document_id": 999999, "question": "x"}).status_code == 404

    # pending 文档不可提问（归属当前用户）
    from app.db import Document
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.add(Document(id=876500, user_id=_current_user_id(), filename="p.pdf", file_path="p.pdf", status="pending"))
        db.commit()
    finally:
        db.close()
    resp = client.post("/api/chat/ask", json={"document_id": 876500, "question": "x"})
    assert resp.status_code == 409
    db = SessionLocal()
    try:
        db.query(Document).filter(Document.id == 876500).delete()
        db.commit()
    finally:
        db.close()


def test_ask_quota_gate(client, stub_embed, seeded_doc):
    from app.core.config import get_settings

    settings = get_settings()
    old_limit = settings.free_question_limit
    settings.free_question_limit = 1
    try:
        first = client.post("/api/chat/ask", json={"document_id": seeded_doc, "question": "问题A"})
        assert first.status_code == 200
        second = client.post("/api/chat/ask", json={"document_id": seeded_doc, "question": "问题B"})
        assert second.status_code == 402  # 额度用尽
    finally:
        settings.free_question_limit = old_limit
