"""混合检索：SQLite 切片 + numpy 向量 + BM25，RRF 融合排序。

流程：ensure_index（按需建/重建向量索引）→ 向量召回 + BM25 召回 → RRF 融合 → Top-K。
向量索引构建失败时自动降级为纯 BM25（保证解析与检索可用性）。
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.db import Chunk
from app.db.session import SessionLocal
from app.services.retrieval import bm25, embeddings, vector_store

logger = logging.getLogger(__name__)

TOP_K = 5
RRF_K = 60  # RRF 平滑常数


def load_chunks(doc_id: int) -> list[dict]:
    """从 SQLite 读回文档全部切片（seq 升序），带引用溯源位置信息。"""
    db = SessionLocal()
    try:
        rows = db.query(Chunk).filter(Chunk.document_id == doc_id).order_by(Chunk.seq).all()
        return [
            {
                "chunk_id": r.id,
                "seq": r.seq,
                "page": r.page,
                "char_start": r.char_start,
                "char_end": r.char_end,
                "bbox": r.bbox_json,
                "text": r.text,
                "snippet": r.snippet,
            }
            for r in rows
        ]
    finally:
        db.close()


def ensure_index(doc_id: int, chunks: list[dict]) -> bool:
    """确保向量索引存在且与当前 embedding 模型匹配；缺失/失效时重建。"""
    meta = vector_store.get_meta(doc_id)
    settings = get_settings()
    if (
        meta
        and meta.get("model") == settings.embedding_model
        and len(meta.get("chunk_ids", [])) == len(chunks)
    ):
        return True
    if not chunks:
        return False
    try:
        vectors = embeddings.embed([c["text"] for c in chunks])
        vector_store.index_chunks(doc_id, [c["chunk_id"] for c in chunks], vectors, settings.embedding_model)
        return True
    except Exception:
        logger.warning("doc %s 向量索引构建失败，降级 BM25", doc_id, exc_info=True)
        return False


def retrieve(doc_id: int, query: str, top_k: int = TOP_K) -> list[dict]:
    """返回 [{"chunk_id", "page", "char_start", "char_end", "bbox", "text", "snippet", "score"}]。"""
    chunks = load_chunks(doc_id)
    if not chunks:
        return []

    indexed = ensure_index(doc_id, chunks)
    vec_hits: list[dict] = []
    if indexed:
        try:
            q_vec = embeddings.embed([query])[0]
            vec_hits = vector_store.search(doc_id, q_vec, top_k=top_k * 2)
        except Exception:
            logger.warning("doc %s 向量检索失败，降级 BM25", doc_id)
            vec_hits = []

    kw_hits = bm25.search(doc_id, chunks, query, top_k=top_k * 2)
    by_id = {c["chunk_id"]: c for c in chunks}

    fused: dict[str, dict] = {}
    for rank, hit in enumerate(vec_hits):
        cid = hit["chunk_id"]
        if cid in by_id:
            fused.setdefault(cid, {**by_id[cid], "score": 0.0})
            fused[cid]["score"] += 1.0 / (RRF_K + rank + 1)
    for rank, hit in enumerate(kw_hits):
        cid = hit["chunk_id"]
        if cid in by_id:
            fused.setdefault(cid, {**by_id[cid], "score": 0.0})
            fused[cid]["score"] += 1.0 / (RRF_K + rank + 1)

    results = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def delete_doc(doc_id: int) -> None:
    """隐私闸：删除文档时清理向量索引、BM25 缓存与 DB 切片记录。"""
    vector_store.delete_doc(doc_id)
    bm25.invalidate_doc(doc_id)
    db = SessionLocal()
    try:
        db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
        db.commit()
    finally:
        db.close()
