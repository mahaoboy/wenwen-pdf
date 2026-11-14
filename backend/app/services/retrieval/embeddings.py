"""BGE 向量化。单例懒加载，避免重复加载模型。

MVP 默认用轻量的 bge-small-zh-v1.5（512 维）跑通流程；
更换 BAAI/bge-m3 只需改 EMBEDDING_MODEL 配置。

加载策略：优先本地缓存（offline，秒级）；首次使用未缓存时自动下载，
国内网络默认走 hf-mirror，避免直连 huggingface.co 挂死。
"""
from __future__ import annotations

import os

from app.core.config import get_settings

_model = None
_model_name: str | None = None


def _get_model():
    global _model, _model_name
    settings = get_settings()
    if _model is None or _model_name != settings.embedding_model:
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from sentence_transformers import SentenceTransformer

        name = settings.embedding_model
        try:
            _model = SentenceTransformer(name, local_files_only=True)
        except Exception:
            _model = SentenceTransformer(name)  # 首次使用：在线下载（走镜像）
        # 低内存环境（小内存主机/容器）：限制推理线程，避免解析期内存挤压
        import torch

        torch.set_num_threads(2)
        _model_name = settings.embedding_model
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """批量向量化，返回归一化向量（点积即余弦相似度）。"""
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]
