"""BM25 关键词检索：jieba 分词 + 自实现 BM25 评分，索引按文档缓存。

不使用 rank_bm25 的 BM25Okapi：其 IDF 公式 ln((N-n+0.5)/(n+0.5)) 在小语料下
退化——词出现于 2 篇中的 1 篇时 IDF = ln(1) = 0，检索全零分。
本实现采用平滑 IDF：ln((N+1)/(n+0.5))，恒为正，小语料可用。

评分公式：score = Σ IDF(qi) * f*(k1+1) / (f + k1*(1-b+b*|D|/avgdl))
"""
from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass

import jieba

jieba.setLogLevel(60)  # 静音 jieba 建词典日志
logger = logging.getLogger(__name__)

K1 = 1.5
B = 0.75


@dataclass
class _Index:
    tf: list[Counter[str]]   # 每文档词频
    doc_lens: list[int]
    df: Counter[str]         # 词文档频率
    avgdl: float


# doc_id -> (chunk_ids 指纹, 索引)
_cache: dict[int, tuple[tuple[str, ...], _Index | None]] = {}


def _tokenize(text: str) -> list[str]:
    return [t for t in jieba.lcut(text.lower()) if t.strip()]


def build_index(doc_id: int, chunks: list[dict]) -> _Index | None:
    """构建/复用 BM25 索引。chunks 变化时自动重建。空/退化语料返回 None。"""
    key = tuple(c["chunk_id"] for c in chunks)
    cached = _cache.get(doc_id)
    if cached and cached[0] == key:
        return cached[1]

    index: _Index | None = None
    tf = [Counter(_tokenize(c["text"])) for c in chunks]
    if chunks and any(tf):
        doc_lens = [sum(t.values()) for t in tf]
        df: Counter[str] = Counter()
        for t in tf:
            df.update(t.keys())
        avgdl = (sum(doc_lens) / len(doc_lens)) or 1.0
        index = _Index(tf=tf, doc_lens=doc_lens, df=df, avgdl=avgdl)
    _cache[doc_id] = (key, index)
    return index


def search(doc_id: int, chunks: list[dict], query: str, top_k: int = 10) -> list[dict]:
    """返回 [{"chunk_id", "text", ..., "score"}]，按 BM25 分数降序。"""
    index = build_index(doc_id, chunks)
    if index is None:
        return []
    q_tokens = set(_tokenize(query))
    if not q_tokens:
        return []

    n_docs = len(index.tf)
    scores = [0.0] * n_docs
    for term in q_tokens:
        n = index.df.get(term, 0)
        if n == 0:
            continue
        idf = math.log((n_docs + 1) / (n + 0.5))  # 平滑 IDF，恒为正
        for i, tfd in enumerate(index.tf):
            f = tfd.get(term, 0)
            if f == 0:
                continue
            denom = f + K1 * (1 - B + B * index.doc_lens[i] / index.avgdl)
            scores[i] += idf * (f * (K1 + 1)) / denom

    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [{**c, "score": s} for c, s in ranked if s > 0]


def invalidate_doc(doc_id: int) -> None:
    """隐私闸：删除文档时清空其 BM25 索引缓存。"""
    _cache.pop(doc_id, None)
