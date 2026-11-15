"""今晚升级项测试：SSE 流式问答 / 文档摘要 / 失败文档重解析。"""
import json

import pytest

from app.services.generation import llm as llm_svc
from app.services.generation.summary import generate_summary_and_suggestions


@pytest.fixture
def stub_stream(monkeypatch):
    """假流式 LLM：从 prompt 提取首个检索片段 chunk_id，分三段输出并带引用。"""
    def fake_stream(messages, api_key=None, temperature=0.1):
        cid = None
        for m in messages:
            if m["role"] == "user" and "【检索片段】" in m["content"]:
                cid = m["content"].split("【片段 ")[1].split("｜")[0]
                break
        yield "根据文档内容，"
        yield f"相关条款 [来源:{cid}]"
        yield "。"

    monkeypatch.setattr(llm_svc, "chat_completion_stream", fake_stream)
    monkeypatch.setattr("app.api.routes.chat.chat_completion_stream", fake_stream)


# ---------- SSE 流式 ----------

def test_stream_endpoint_deltas_and_citations(client, stub_embed, seeded_doc, stub_stream):
    resp = client.post(
        f"/api/chat/documents/{seeded_doc}/stream",
        json={"document_id": seeded_doc, "question": "违约责任"},
        headers=client.headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = [json.loads(line.removeprefix("data: ")) for line in resp.text.splitlines() if line.startswith("data: ")]
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    done = [e for e in events if e["type"] == "done"]
    assert "相关条款" in deltas
    assert done, "缺少 done 事件"
    assert done[0]["citations"][0]["chunk_id"] == f"{seeded_doc}-c0"
    assert done[0]["session_id"]


def test_stream_cache_hit_single_shot(client, stub_embed, seeded_doc, stub_stream):
    q = {"document_id": seeded_doc, "question": "违约责任是什么"}
    for _ in range(2):  # 第二次命中缓存
        client.post(f"/api/chat/documents/{seeded_doc}/stream", json=q)
    resp = client.post(f"/api/chat/documents/{seeded_doc}/stream", json=q)
    events = [json.loads(line.removeprefix("data: ")) for line in resp.text.splitlines() if line.startswith("data: ")]
    # 缓存命中：单次全量 delta（无多段流式）
    delta_events = [e for e in events if e["type"] == "delta"]
    assert len(delta_events) == 1


def test_stream_quota_blocked_before_stream(client, stub_embed, seeded_doc):
    from app.core.config import get_settings

    settings = get_settings()
    old = settings.free_question_limit
    settings.free_question_limit = 0
    try:
        resp = client.post(
            f"/api/chat/documents/{seeded_doc}/stream",
            json={"document_id": seeded_doc, "question": "任意"},
            headers=client.headers,
        )
        assert resp.status_code == 402  # 额度闸在流开始前返回（可正常显示错误）
    finally:
        settings.free_question_limit = old


# ---------- 摘要生成 ----------

def test_summary_generation_parses_llm_json(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    old = settings.deepseek_api_key
    settings.deepseek_api_key = "sk-test"
    monkeypatch.setattr(llm_svc, "chat_completion", lambda *a, **k: '{"summary": "稳健投资手册。", "questions": ["怎么分配？", "收益多少？", "风险？"]}')
    try:
        summary, questions = generate_summary_and_suggestions(999, [{"text": "八笔投资内容"}])
        assert summary == "稳健投资手册。"
        assert len(questions) == 3
    finally:
        settings.deepseek_api_key = old


def test_summary_bad_json_returns_empty(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    old = settings.deepseek_api_key
    settings.deepseek_api_key = "sk-test"
    monkeypatch.setattr(llm_svc, "chat_completion", lambda *a, **k: "这不是JSON")
    try:
        summary, questions = generate_summary_and_suggestions(999, [{"text": "x"}])
        assert summary == "" and questions == []
    finally:
        settings.deepseek_api_key = old


def test_summary_skipped_without_key():
    from app.core.config import get_settings

    assert get_settings().deepseek_api_key == ""  # conftest 隔离
    summary, questions = generate_summary_and_suggestions(1, [{"text": "x"}])
    assert summary == "" and questions == []


# ---------- 失败文档重解析 ----------

def test_reparse_error_doc(client, stub_embed):
    import uuid

    from app.db import Document
    from app.db.session import SessionLocal

    from tests.helpers import current_user_id

    doc_id = 900000 + (int(uuid.uuid4().hex[:6], 16) % 90000)
    db = SessionLocal()
    try:
        db.add(Document(id=doc_id, user_id=current_user_id(), filename="broken.pdf",
                        file_path="/tmp/broken.pdf", status="error"))
        db.commit()
    finally:
        db.close()

    resp = client.post(f"/api/documents/{doc_id}/reparse")
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"

    # 非 error 文档 → 409
    ready = SessionLocal()
    try:
        ready.add(Document(id=doc_id + 1, user_id=current_user_id(), filename="ok.pdf",
                           file_path="ok.pdf", status="ready"))
        ready.commit()
    finally:
        ready.close()
    resp2 = client.post(f"/api/documents/{doc_id + 1}/reparse")
    assert resp2.status_code == 409

    # 清理
    db = SessionLocal()
    try:
        for did in (doc_id, doc_id + 1):
            row = db.get(Document, did)
            if row:
                db.delete(row)
        db.commit()
    finally:
        db.close()
