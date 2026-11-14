"""模块1测试：上传 / 列表 / 删除 + 后台解析流水线集成。"""
import fitz
import pytest
import time
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import Chunk
from app.main import app


def make_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "1. The Buyer shall pay the price within 30 days.", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((72, 100), "2. The Seller shall ensure goods meet national standards.", fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _register(client: TestClient) -> str:
    from tests.helpers import register_verified

    return register_verified(client)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_upload_list_delete_roundtrip(client, monkeypatch):
    """上传→提问→删除全链路：覆盖「删除带对话消息的文档」级联清理回归。"""
    # stub 嵌入器：让本用例不依赖真实模型，聚焦接口与级联行为
    import hashlib

    import numpy as np

    from app.services.retrieval import embeddings as emb_mod

    def fake_embed(texts):
        out = []
        for t in texts:
            v = np.zeros(64, dtype=np.float32)
            for ch in t:
                v[int(hashlib.md5(ch.encode()).hexdigest(), 16) % 64] += 1.0
            n = float(np.linalg.norm(v)) or 1.0
            out.append((v / n).tolist())
        return out

    monkeypatch.setattr(emb_mod, "embed", fake_embed)

    token = _register(client)
    headers = _auth(token)

    # 上传：响应返回创建快照（pending），后台流水线随后完成 → 轮询至 ready
    resp = client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("contract.pdf", make_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["status"] in {"pending", "parsing", "ready"}

    deadline = time.time() + 15
    docs = []
    while time.time() < deadline:
        docs = client.get("/api/documents", headers=headers).json()
        if docs and docs[0]["status"] == "ready":
            break
        time.sleep(0.2)
    assert docs and docs[0]["status"] == "ready", "解析流水线未在超时内完成"
    doc = docs[0]
    assert doc["page_count"] == 2
    assert doc["chunk_count"] >= 2  # 两页各一条条款 → 至少两片

    # 列表
    resp = client.get("/api/documents", headers=headers)
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) == 1 and docs[0]["id"] == doc["id"]

    # 切片已入库且带位置信息
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        rows = db.query(Chunk).filter(Chunk.document_id == doc["id"]).all()
        assert len(rows) == doc["chunk_count"]
        assert {r.page for r in rows} == {1, 2}
        for r in rows:
            assert r.id.startswith(f"{doc['id']}-c")
            assert 0 <= r.char_start < r.char_end
            assert r.bbox_json and r.text
    finally:
        db.close()

    # 提问一次（产生对话消息），再删除——回归：Message 级联清理
    resp = client.post(
        "/api/chat/ask",
        headers=headers,
        json={"document_id": doc["id"], "question": "付款期限"},
    )
    assert resp.status_code == 200, resp.text

    # 删除 → 文件/切片/消息/文档一并清理
    resp = client.delete(f"/api/documents/{doc['id']}", headers=headers)
    assert resp.status_code == 204, resp.text
    resp = client.get("/api/documents", headers=headers)
    assert resp.json() == []

    db = SessionLocal()
    try:
        assert db.query(Chunk).filter(Chunk.document_id == doc["id"]).count() == 0
        from app.db import Message

        assert db.query(Message).filter(Message.document_id == doc["id"]).count() == 0
    finally:
        db.close()


def test_upload_rejects_non_pdf(client):
    token = _register(client)
    resp = client.post(
        "/api/documents/upload",
        headers=_auth(token),
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_requires_auth(client):
    resp = client.post(
        "/api/documents/upload",
        files={"file": ("x.pdf", make_pdf_bytes(), "application/pdf")},
    )
    assert resp.status_code == 401


def test_doc_quota_gate(client):
    token = _register(client)
    headers = _auth(token)
    settings = get_settings()
    old_limit = settings.free_doc_limit
    settings.free_doc_limit = 1
    try:
        resp = client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("a.pdf", make_pdf_bytes(), "application/pdf")},
        )
        assert resp.status_code == 201
        resp = client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("b.pdf", make_pdf_bytes(), "application/pdf")},
        )
        assert resp.status_code == 402  # 免费版 1 篇上限（测试内临时改小）
    finally:
        settings.free_doc_limit = old_limit

def test_upload_size_limit_413(client):
    """应用层大小限制：超限返回 413（与 nginx 20MB 双重防御）。"""
    from app.core.config import get_settings
    from tests.helpers import auth_headers

    headers = auth_headers(client)
    settings = get_settings()
    old = settings.max_upload_mb
    settings.max_upload_mb = 1
    try:
        big = b"%PDF-1.4 " + b"0" * (2 * 1024 * 1024)  # 2MB 假 PDF
        resp = client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("big.pdf", big, "application/pdf")},
        )
        assert resp.status_code == 413, resp.text
        assert "文件过大" in resp.json()["detail"]
    finally:
        settings.max_upload_mb = old


def test_startup_recovery_marks_stuck_docs(client):
    """启动自愈：重启后卡在 pending/parsing 的文档标记为 error。"""
    from app.api.routes.documents import recover_stuck_documents
    from app.db import Document
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        from tests.helpers import current_user_id

        db.add(Document(id=876601, user_id=current_user_id(), filename="stuck.pdf",
                        file_path="stuck.pdf", status="parsing"))
        db.commit()
    finally:
        db.close()

    n = recover_stuck_documents()
    db = SessionLocal()
    try:
        status = db.get(Document, 876601).status
        assert status == "error"
        assert n >= 1
        db.delete(db.get(Document, 876601))
        db.commit()
    finally:
        db.close()
