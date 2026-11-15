"""测试环境隔离与共享 fixtures。

- 真实 .env 的全局 Key / 邮件通道不进测试（用例内自行设置）
- client / stub_embed / seeded_doc 为跨文件共享 fixtures
"""
import pytest

from app.core.config import get_settings
from app.db.session import SessionLocal
from tests.helpers import current_user_id, register_verified


@pytest.fixture(autouse=True)
def _isolate_global_llm_key():
    settings = get_settings()
    old = settings.deepseek_api_key
    settings.deepseek_api_key = ""
    yield
    settings.deepseek_api_key = old


@pytest.fixture(autouse=True)
def _isolate_email_transport():
    """测试默认禁用真实邮件通道（gmail_api/smtp），需要发信的用例自行设置。"""
    settings = get_settings()
    old_transport = settings.email_transport
    old_smtp_host = settings.smtp_host
    settings.email_transport = ""
    settings.smtp_host = ""
    yield
    settings.email_transport = old_transport
    settings.smtp_host = old_smtp_host


@pytest.fixture()
def client():
    """注册一个已验证用户并注入 Authorization 头的测试客户端。"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        token = register_verified(c)
        c.headers = {"Authorization": f"Bearer {token}"}
        yield c


_DIM = 64


def fake_embed(texts: list[str]) -> list[str]:
    """确定性字符哈希嵌入（测试专用）。"""
    import hashlib

    import numpy as np

    out = []
    for t in texts:
        v = np.zeros(_DIM, dtype=np.float32)
        for ch in t:
            v[int(hashlib.md5(ch.encode()).hexdigest(), 16) % _DIM] += 1.0
        n = float(np.linalg.norm(v)) or 1.0
        out.append((v / n).tolist())
    return out


@pytest.fixture
def stub_embed(monkeypatch):
    from app.services.retrieval import embeddings

    monkeypatch.setattr(embeddings, "embed", fake_embed)


@pytest.fixture
def seeded_doc(client):
    """向 DB 灌一个归属于当前测试用户的已就绪文档（三条切片）。"""
    from app.db import Chunk, Document
    from app.services.retrieval import hybrid

    doc_id = 876543
    user_id = current_user_id()
    db = SessionLocal()
    try:
        db.add(
            Document(
                id=doc_id, user_id=user_id, filename="t.pdf", file_path="t.pdf", status="ready"
            )
        )
        texts = [
            "甲方违反合同约定，应当承担违约责任，赔偿损失。",
            "乙方应当在收货后三十日内支付货款。",
            "本合同一式两份，自双方签字之日起生效。",
        ]
        for seq, text in enumerate(texts):
            db.add(
                Chunk(
                    id=f"{doc_id}-c{seq}",
                    document_id=doc_id,
                    seq=seq,
                    page=1,
                    char_start=0,
                    char_end=len(text),
                    bbox_json="[]",
                    text=text,
                    snippet=text[:20],
                )
            )
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
