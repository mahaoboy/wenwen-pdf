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
    import uuid

    email = f"{uuid.uuid4().hex[:12]}@test.dev"
    resp = client.post("/api/auth/register", json={"email": email, "password": "pass1234"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_upload_list_delete_roundtrip(client):
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

    # 删除 → 文件/切片/文档一并清理
    resp = client.delete(f"/api/documents/{doc['id']}", headers=headers)
    assert resp.status_code == 204
    resp = client.get("/api/documents", headers=headers)
    assert resp.json() == []

    db = SessionLocal()
    try:
        assert db.query(Chunk).filter(Chunk.document_id == doc["id"]).count() == 0
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
