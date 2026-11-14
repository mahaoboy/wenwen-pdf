"""引用映射：从模型回答中抽取 [来源:doc-cN] 标注，校验后映射为结构化引用。

幻觉闸第二道防线：只允许引用真实存在于检索结果中的 chunk，
模型编造的引用一律丢弃。宽进严出的唯一例外：模型漏写 doc 前缀
只写 c{N} 时，若能在本次检索结果中唯一匹配则映射（引用对象仍受闸门约束）。
"""
from __future__ import annotations

import re

CITATION_PAT = re.compile(r"\[来源:(\S+-c\d+)\]")
BARE_SEQ_PAT = re.compile(r"\[来源:c(\d+)\]")


def extract_citations(answer: str, retrieved: list[dict]) -> list[dict]:
    """返回 [{"chunk_id", "page", "snippet"}]，按回答中出现顺序去重。"""
    valid = {c["chunk_id"]: c for c in retrieved}
    seen: list[str] = []
    for cid in CITATION_PAT.findall(answer):
        if cid in valid and cid not in seen:
            seen.append(cid)

    # 兜底：模型漏写 doc 前缀（如 [来源:c1]），按序号匹配本次检索结果
    by_seq: dict[str, dict] = {}
    for c in retrieved:
        seq = c["chunk_id"].rsplit("-c", 1)[-1]
        by_seq.setdefault(seq, c)  # 同文档内 seq 唯一；重复时保留第一个
    for bare in BARE_SEQ_PAT.findall(answer):
        cand = by_seq.get(bare)
        if cand and cand["chunk_id"] not in seen:
            seen.append(cand["chunk_id"])

    return [
        {
            "chunk_id": cid,
            "page": valid[cid]["page"],
            "snippet": valid[cid]["snippet"],
        }
        for cid in seen
    ]


def clean_answer(answer: str) -> str:
    """前端渲染用：保留标注（前端将其转为可点击引用角标）。"""
    return answer.strip()
