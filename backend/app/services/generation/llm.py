"""DeepSeek LLM 客户端（OpenAI 兼容协议），Qwen 为备选。"""
from __future__ import annotations

from openai import OpenAI

from app.core.config import get_settings


def chat_completion(messages: list[dict], temperature: float = 0.1) -> str:
    settings = get_settings()
    client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        stream=False,
    )
    return resp.choices[0].message.content or ""
