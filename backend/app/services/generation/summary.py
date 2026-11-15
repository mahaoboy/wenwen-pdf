"""文档摘要与动态建议问题：解析完成后自动生成（增值首屏）。

- 使用全局兜底 Key（解析阶段无用户上下文；BYOK 仅作用于问答）
- 无可用 Key / 调用失败 → 留空，前端回落静态建议，不影响解析主流程
"""
from __future__ import annotations

import json
import logging

from app.services.generation import llm

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 4000  # 摘要上下文上限，控制成本


def generate_summary_and_suggestions(doc_id: int, chunks: list[dict]) -> tuple[str, list[str]]:
    """从切片生成摘要与 3 个建议问题。失败返回 ("", [])。"""
    from app.core.config import get_settings

    if not get_settings().deepseek_api_key:
        logger.info("doc %s 无全局 Key，跳过摘要生成", doc_id)
        return "", []

    context = "\n\n".join(c["text"] for c in chunks)[:MAX_CONTEXT_CHARS]
    prompt = (
        "基于以下文档片段（可能被截断），完成两件事并以 JSON 返回，不要输出其他内容：\n"
        '1. "summary"：3~4 句中文摘要，概括文档主题、结构与最重要的结论\n'
        '2. "questions"：3 个用户最可能想问的问题（中文，不带问号结尾的序号）\n\n'
        f"文档片段：\n{context}\n\n"
        '返回格式：{"summary": "...", "questions": ["...", "...", "..."]}'
    )
    try:
        raw = llm.chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(cleaned)
        summary = str(data.get("summary", "")).strip()
        questions = [str(q).strip() for q in data.get("questions", [])][:3]
        questions = [q for q in questions if q]
        return summary, questions
    except Exception:
        logger.warning("doc %s 摘要生成失败（不影响解析主流程）", doc_id, exc_info=True)
        return "", []
