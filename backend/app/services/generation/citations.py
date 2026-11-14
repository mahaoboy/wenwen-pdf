"""引用映射：从模型回答中抽取 [来源:doc-cN] 标注，校验后映射为结构化引用。

幻觉闸第二道防线：只允许引用真实存在于检索结果中的 chunk，
模型编造的引用一律丢弃。
"""
from __future__ import annotations

import re

CITATION_PAT = re.compile(r"\[来源:(\S+-c\d+)\]")


def extract_citations(answer: str, retrieved: list[dict]) -> list[dict]:
    """返回 [{"chunk_id", "page", "snippet"}]，按回答中出现顺序去重。"""
    valid = {c["chunk_id"]: c for c in retrieved}
    seen: list[str] = []
    for cid in CITATION_PAT.findall(answer):
        if cid in valid and cid not in seen:
            seen.append(cid)
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
