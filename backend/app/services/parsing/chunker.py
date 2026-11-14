"""切片器：按块/条款聚合切片，每片带页码与位置信息（页内字符偏移 + bbox）。

引用溯源契约（与产品设计 §4.2 对齐）：
- chunk_id 全局稳定：{doc_id}-c{序号}，作为引用映射与前端跳转的主键
- 每片记录 page / char_start / char_end / bbox，供生成层引用与前端高亮
- 相邻片保留少量文本重叠（前片结尾），保证跨条款上下文不丢
"""
from __future__ import annotations

import re

# 常见合同/法规条款编号模式，命中则优先按条款切
CLAUSE_PAT = re.compile(r"^(第[一二三四五六七八九十百\d]+条|[一二三四五六七八九十]+、|\d+(?:\.\d+)*[、.．])\s*")

MAX_CHARS = 600    # 单片上限
OVERLAP_CHARS = 100  # 相邻片文本重叠


def chunk_pages(pages: list[dict], doc_id: int) -> list[dict]:
    """输入 extract_pages 的页结构，输出切片列表：
    [{"chunk_id", "page", "char_start", "char_end", "bbox", "text", "snippet"}]

    重叠规则：仅在按长度截断（非语义边界）时，下一片才带前片结尾上下文；
    条款边界与页边界是语义边界，不重叠，避免引用文本被污染。
    """
    chunks: list[dict] = []
    seq = 0
    pending_overlap = False
    prev_own = ""
    for p in pages:
        buf_blocks: list[dict] = []
        buf_len = 0
        for block in p["blocks"]:
            starts_clause = bool(CLAUSE_PAT.match(block["text"]))
            if buf_blocks and (starts_clause or buf_len + len(block["text"]) > MAX_CHARS):
                chunk = _make(
                    doc_id, seq, p["page"], buf_blocks,
                    prev_own[-OVERLAP_CHARS:] if pending_overlap else "",
                )
                chunks.append(chunk)
                seq += 1
                prev_own = chunk["own"]
                pending_overlap = not starts_clause  # 尺寸截断才需要重叠
                buf_blocks, buf_len = [], 0
            buf_blocks.append(block)
            buf_len += len(block["text"])
        if buf_blocks:
            chunk = _make(
                doc_id, seq, p["page"], buf_blocks,
                prev_own[-OVERLAP_CHARS:] if pending_overlap else "",
            )
            chunks.append(chunk)
            seq += 1
            prev_own = chunk["own"]
            pending_overlap = False  # 页边界为语义边界，不重叠
    return chunks


def _make(doc_id: int, seq: int, page: int, blocks: list[dict], tail: str) -> dict:
    own = "\n".join(b["text"] for b in blocks)
    text = f"…{tail}\n{own}" if tail else own
    return {
        "chunk_id": f"{doc_id}-c{seq}",
        "page": page,
        "char_start": blocks[0]["char_start"],
        "char_end": blocks[-1]["char_end"],
        "bbox": [
            min(b["bbox"][0] for b in blocks),
            min(b["bbox"][1] for b in blocks),
            max(b["bbox"][2] for b in blocks),
            max(b["bbox"][3] for b in blocks),
        ],
        "text": text,
        "own": own,  # 切片自身文本（不含重叠前缀），落库/引用以它为准
        "snippet": own[:80],
    }
