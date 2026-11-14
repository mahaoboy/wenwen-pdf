"""真实嵌入端到端冒烟（手动跑，不进 CI）：bge-small-zh 真实向量 + 混合检索。

用法：cd backend && HF_ENDPOINT=https://hf-mirror.com .venv/bin/python scripts/smoke_real_retrieval.py
"""
import time
import uuid

import fitz
from fastapi.testclient import TestClient

from app.main import app
from app.services.retrieval import embeddings, hybrid, vector_store


def make_pdf() -> bytes:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text(
        (72, 100),
        "第一条 甲方未按期付款的，每逾期一日按未付金额千分之一支付违约金。",
        fontsize=12,
        fontname="china-s",
    )
    p2 = doc.new_page()
    p2.insert_text(
        (72, 100),
        "第二条 乙方交付的货物质量应当符合国家标准及合同约定。",
        fontsize=12,
        fontname="china-s",
    )
    data = doc.tobytes()
    doc.close()
    return data


def main() -> None:
    with TestClient(app) as client:
        email = f"{uuid.uuid4().hex[:12]}@test.dev"
        token = client.post("/api/auth/register", json={"email": email, "password": "pass1234"}).json()[
            "access_token"
        ]
        h = {"Authorization": f"Bearer {token}"}
        r = client.post("/api/documents/upload", headers=h, files={"file": ("合同.pdf", make_pdf(), "application/pdf")})
        assert r.status_code == 201, r.text
        doc_id = r.json()["id"]

        deadline = time.time() + 120
        status, docs = None, None
        while time.time() < deadline:
            docs = client.get("/api/documents", headers=h).json()
            status = docs[0]["status"]
            if status == "ready":
                break
            time.sleep(0.5)
        print("status:", status, "| pages:", docs[0]["page_count"], "| chunks:", docs[0]["chunk_count"])
        assert status == "ready"

        q1 = "甲方逾期付款的违约金怎么算？"
        qv = embeddings.embed([q1])[0]
        vec_top = vector_store.search(doc_id, qv, top_k=3)[0]
        print("向量检索 top1:", vec_top["chunk_id"], round(vec_top["score"], 3))
        hits = hybrid.retrieve(doc_id, q1, top_k=3)
        print("混合检索 top1:", hits[0]["chunk_id"], "| page", hits[0]["page"], "|", hits[0]["text"][:32])
        assert "违约金" in hits[0]["text"], "真实嵌入应命中违约金条款"

        hits2 = hybrid.retrieve(doc_id, "货物质量标准是什么？", top_k=3)
        print("混合检索 top1:", hits2[0]["chunk_id"], "|", hits2[0]["text"][:32])
        assert "质量" in hits2[0]["text"]

        client.delete(f"/api/documents/{doc_id}", headers=h)
        assert not vector_store.has_index(doc_id)
        print("SMOKE OK: 真实 bge-small-zh 端到端通过")


if __name__ == "__main__":
    main()
