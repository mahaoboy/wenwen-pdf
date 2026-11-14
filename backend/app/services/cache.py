"""问答结果缓存（成本闸）：命中缓存直接返回，省 LLM 调用。

MVP 用进程内 LRU；后续切 Redis。
key = hash(doc_id + 最近1轮上下文 + 问题)
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

_CACHE_MAX = 256
_cache: OrderedDict[str, dict] = OrderedDict()


def _key(doc_id: int, question: str, last_history: tuple[tuple[str, str], ...] = ()) -> str:
    raw = json.dumps([doc_id, question, last_history[-1:]], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(doc_id: int, question: str, last_history: tuple[tuple[str, str], ...] = ()) -> dict | None:
    k = _key(doc_id, question, last_history)
    if k in _cache:
        _cache.move_to_end(k)
        return _cache[k]
    return None


def put(doc_id: int, question: str, value: dict, last_history: tuple[tuple[str, str], ...] = ()) -> None:
    _cache[_key(doc_id, question, last_history)] = value
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


def invalidate_doc(doc_id: int) -> None:
    """隐私闸：删除文档时清空问答缓存。MVP 进程内缓存采用全清策略（代价可忽略）。"""
    _cache.clear()
