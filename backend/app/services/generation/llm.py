"""DeepSeek LLM 客户端（OpenAI 兼容协议），Qwen 为备选。支持用户自备 Key（BYOK）。"""
from __future__ import annotations

from collections.abc import Generator

from openai import OpenAI

from app.core.config import get_settings
from app.services.metrics import record


def chat_completion(messages: list[dict], api_key: str | None = None, temperature: float = 0.1) -> str:
    """api_key 传入用户自备 Key（BYOK）时优先使用；否则回落全局配置。"""
    settings = get_settings()
    key = api_key or settings.deepseek_api_key
    client = OpenAI(api_key=key, base_url=settings.deepseek_base_url)
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        stream=False,
    )
    if resp.usage:
        record(
            "llm_tokens",
            meta={
                "model": settings.deepseek_model,
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            },
        )
    return resp.choices[0].message.content or ""


def chat_completion_stream(
    messages: list[dict], api_key: str | None = None, temperature: float = 0.1
) -> Generator[str, None, None]:
    """流式生成：逐步 yield 增量文本；结束时记录 token 用量。"""
    settings = get_settings()
    key = api_key or settings.deepseek_api_key
    client = OpenAI(api_key=key, base_url=settings.deepseek_base_url)
    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=temperature,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in resp:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if getattr(chunk, "usage", None):
            record(
                "llm_tokens",
                meta={
                    "model": settings.deepseek_model,
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                },
            )
