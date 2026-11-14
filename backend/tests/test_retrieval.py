"""模块3测试：numpy 向量索引、BM25、RRF 融合、检索流水线（stub 嵌入器，不依赖网络）。"""
import hashlib

import numpy as np
import pytest

from app.services.retrieval import bm25, embeddings, hybrid, vector_store

DIM = 64


def fake_embed(texts: list[str]) -> list[list[float]]:
    """确定性字符哈希嵌入：共享字符越多越相似，够测试用。"""
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


# ---------- vector_store ----------

def test_vector_roundtrip_and_search():
    vecs = fake_embed(["甲方违约责任", "乙方付款义务", "毫不相关的内容xyz"])
    ids = ["900-c0", "900-c1", "900-c2"]
    vector_store.index_chunks(900, ids, vecs, "test-model")
    try:
        assert vector_store.has_index(900)
        meta = vector_store.get_meta(900)
        assert meta["model"] == "test-model" and meta["chunk_ids"] == ids

        q = fake_embed(["违约"])[0]
        hits = vector_store.search(900, q, top_k=2)
        assert len(hits) == 2
        assert hits[0]["chunk_id"] == "900-c0"  # 语义最近
        assert 0.0 <= hits[0]["score"] <= 1.0001
    finally:
        vector_store.delete_doc(900)
    assert not vector_store.has_index(900)
    assert vector_store.search(900, q) == []


def test_vector_search_no_index():
    assert vector_store.search(999999, [0.1] * DIM) == []


# ---------- bm25 ----------

def test_bm25_chinese_keyword():
    chunks = [
        {"chunk_id": "901-c0", "text": "甲方违反合同约定，应当承担违约责任，赔偿损失。", "page": 1, "snippet": ""},
        {"chunk_id": "901-c1", "text": "乙方应当在收货后三十日内支付货款。", "page": 1, "snippet": ""},
    ]
    try:
        hits = bm25.search(901, chunks, "违约责任", top_k=2)
        assert hits and hits[0]["chunk_id"] == "901-c0"
        assert hits[0]["score"] > 0
        # 索引复用：chunk 集合不变时重建缓存命中
        hits2 = bm25.search(901, chunks, "支付货款", top_k=1)
        assert hits2[0]["chunk_id"] == "901-c1"
    finally:
        bm25.invalidate_doc(901)


# ---------- RRF 融合 ----------

def test_rrf_fusion_prefers_double_hits(monkeypatch):
    chunks = [
        {"chunk_id": "902-c0", "text": "A", "page": 1, "snippet": ""},
        {"chunk_id": "902-c1", "text": "B", "page": 1, "snippet": ""},
        {"chunk_id": "902-c2", "text": "C", "page": 1, "snippet": ""},
    ]
    by_id = {c["chunk_id"]: c for c in chunks}
    # 向量第1名 c0，BM25 第1名 c1，c2 两路都命中中游 → RRF 应排最前
    monkeypatch.setattr(vector_store, "search", lambda *a, **k: [
        {"chunk_id": "902-c0", "seq": 0, "score": 0.9},
        {"chunk_id": "902-c2", "seq": 2, "score": 0.8},
    ])
    monkeypatch.setattr(bm25, "search", lambda *a, **k: [
        {"chunk_id": "902-c1", "score": 5.0},
        {"chunk_id": "902-c2", "score": 4.0},
    ])
    monkeypatch.setattr(hybrid, "load_chunks", lambda doc_id: chunks)
    monkeypatch.setattr(hybrid.embeddings, "embed", fake_embed)
    monkeypatch.setattr(hybrid, "ensure_index", lambda doc_id, cs: True)

    results = hybrid.retrieve(902, "任意问题", top_k=3)
    assert results[0]["chunk_id"] == "902-c2"  # 双路命中者优先
    assert {r["chunk_id"] for r in results} == {"902-c0", "902-c1", "902-c2"}


# ---------- 检索流水线（DB + 索引） ----------

@pytest.fixture
def seeded_doc():
    """向 DB 灌一个文档的三条切片（不走上传接口，聚焦检索层）。"""
    from app.db import Chunk, Document
    from app.db.session import SessionLocal

    doc_id = 987654
    db = SessionLocal()
    try:
        db.add(Document(id=doc_id, user_id=1, filename="t.pdf", file_path="t.pdf", status="ready"))
        texts = [
            "甲方违反合同约定，应当承担违约责任。",
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
    # 清理
    hybrid.delete_doc(doc_id)
    db = SessionLocal()
    try:
        db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
        db.query(Document).filter(Document.id == doc_id).delete()
        db.commit()
    finally:
        db.close()


def test_retrieve_end_to_end(stub_embed, seeded_doc):
    doc_id = seeded_doc
    assert not vector_store.has_index(doc_id)
    hits = hybrid.retrieve(doc_id, "违约责任", top_k=3)
    assert hits, "应召回结果"
    assert hits[0]["text"].startswith("甲方")  # 语义+关键词双路都该命中第一条
    assert hits[0]["page"] == 1
    assert vector_store.has_index(doc_id)  # ensure_index 已建索引
    # 二次检索复用索引
    hits2 = hybrid.retrieve(doc_id, "支付货款", top_k=1)
    assert hits2[0]["text"].startswith("乙方")


def test_delete_doc_clears_everything(stub_embed, seeded_doc):
    doc_id = seeded_doc
    hybrid.retrieve(doc_id, "合同", top_k=1)
    assert vector_store.has_index(doc_id)
    hybrid.delete_doc(doc_id)
    assert not vector_store.has_index(doc_id)
    # Bug2 修复回归：delete_doc 连带清理 DB 切片（隐私闸自洽，不再只依赖路由层）
    assert vector_store.get_meta(doc_id) is None
    assert hybrid.load_chunks(doc_id) == []
    bm25.invalidate_doc(doc_id)


# ---------- 上传→解析→索引 集成 ----------

def test_upload_builds_vector_index(stub_embed):
    import fitz
    import time
    from fastapi.testclient import TestClient

    from app.main import app

    def make_pdf() -> bytes:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 100), "1. The Buyer shall pay the price within 30 days.", fontsize=12)
        page2 = doc.new_page()
        page2.insert_text((72, 100), "2. The Seller shall ensure goods meet standards.", fontsize=12)
        data = doc.tobytes()
        doc.close()
        return data

    with TestClient(app) as client:
        import uuid

        email = f"{uuid.uuid4().hex[:12]}@test.dev"
        token = client.post("/api/auth/register", json={"email": email, "password": "pass1234"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/documents/upload", headers=headers, files={"file": ("c.pdf", make_pdf(), "application/pdf")})
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        deadline = time.time() + 15
        status = None
        while time.time() < deadline:
            docs = client.get("/api/documents", headers=headers).json()
            status = docs[0]["status"]
            if status == "ready":
                break
            time.sleep(0.2)
        assert status == "ready"
        assert vector_store.has_index(doc_id)

        hits = hybrid.retrieve(doc_id, "pay the price", top_k=2)
        assert hits and "pay" in hits[0]["text"]

        # 删除连带清理向量
        client.delete(f"/api/documents/{doc_id}", headers=headers)
        assert not vector_store.has_index(doc_id)
