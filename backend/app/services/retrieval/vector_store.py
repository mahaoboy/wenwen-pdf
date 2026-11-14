"""本地向量索引：每文档一个 numpy 矩阵 + meta，零外部依赖。

设计（与切片契约对齐）：
- 向量矩阵按 chunk seq 顺序存储，chunk_ids 记录在 meta 中做对齐
- 向量入库前归一化，检索用点积 = 余弦相似度
- 模型名记录在 meta；模型切换后维度/语义不匹配，索引视为失效（需重建）
- 删除文档即删文件（隐私闸）
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

VECTORS_DIR = Path(__file__).resolve().parents[3] / "vectors"


def _paths(doc_id: int) -> tuple[Path, Path]:
    return VECTORS_DIR / f"doc_{doc_id}.npy", VECTORS_DIR / f"doc_{doc_id}.json"


def index_chunks(doc_id: int, chunk_ids: list[str], vectors: list[list[float]], model_name: str) -> None:
    VECTORS_DIR.mkdir(exist_ok=True)
    npy_path, meta_path = _paths(doc_id)
    mat = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms
    np.save(npy_path, mat)
    meta_path.write_text(
        json.dumps({"model": model_name, "dim": int(mat.shape[1]), "chunk_ids": list(chunk_ids)}, ensure_ascii=False),
        encoding="utf-8",
    )


def get_meta(doc_id: int) -> dict | None:
    meta_path = _paths(doc_id)[1]
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def has_index(doc_id: int) -> bool:
    return _paths(doc_id)[0].exists()


def search(doc_id: int, query_vector: list[float], top_k: int = 10) -> list[dict]:
    """返回 [{"seq", "chunk_id", "score"}]，按相似度降序。无索引返回空。"""
    npy_path, meta_path = _paths(doc_id)
    if not npy_path.exists() or not meta_path.exists():
        return []
    mat = np.load(npy_path)
    if mat.shape[0] == 0:
        return []
    q = np.array(query_vector, dtype=np.float32)
    qn = np.linalg.norm(q) or 1.0
    sims = mat @ (q / qn)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    k = min(top_k, len(sims))
    order = np.argsort(-sims)[:k]
    return [
        {"seq": int(i), "chunk_id": meta["chunk_ids"][int(i)], "score": float(sims[int(i)])}
        for i in order
    ]


def delete_doc(doc_id: int) -> None:
    """隐私闸：删除文档时连带删除向量索引。"""
    for p in _paths(doc_id):
        p.unlink(missing_ok=True)
