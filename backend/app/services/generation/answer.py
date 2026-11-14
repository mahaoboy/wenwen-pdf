"""回答生成：检索片段 → LLM 生成 / 无 Key 时抽取式降级。

幻觉闸：
- LLM 模式：Prompt 强制仅基于检索片段作答，找不到就明说（prompts.py）
- 降级模式（未配置 DEEPSEEK_API_KEY）：直接摘录检索原文并标注引用，绝不编造
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.services.generation import llm, prompts

logger = logging.getLogger(__name__)


def generate_answer(question: str, retrieved: list[dict], history: list[tuple[str, str]]) -> dict:
    """返回 {"answer": 回答文本, "mode": "llm" | "extractive"}。

    answer 中的引用统一用 [来源:{chunk_id}] 标注，由 citations.py 校验映射。
    """
    settings = get_settings()
    if settings.deepseek_api_key:
        messages = prompts.build_messages(question, retrieved, history)
        text = llm.chat_completion(messages)
        return {"answer": text, "mode": "llm"}
    return {"answer": _extractive(question, retrieved), "mode": "extractive"}


def _extractive(question: str, retrieved: list[dict]) -> str:
    """无 LLM Key 的降级回答：摘录最相关片段原文（诚实降级，不编造）。"""
    if not retrieved:
        return "文档中未找到相关内容。"
    top = retrieved[0]
    lines = [
        "（LLM 未配置，以下为文档原文摘录；配置 DEEPSEEK_API_KEY 后启用生成式回答）",
        "",
        f"根据文档第 {top['page']} 页，与问题最相关的内容如下 [来源:{top['chunk_id']}]：",
        "",
        f"「{top['text'][:300]}」",
    ]
    return "\n".join(lines)
