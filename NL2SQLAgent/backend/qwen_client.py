from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable

import certifi
import httpx
import ssl
from langchain_openai import ChatOpenAI

from load_env import load_env_file


def _build_http_client() -> httpx.Client:
    if os.getenv('ALLOW_INSECURE_SSL', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        return httpx.Client(verify=False)
    return httpx.Client(verify=ssl.create_default_context(cafile=certifi.where()))


HTTP_CLIENT = _build_http_client()


@lru_cache(maxsize=1)
def get_qwen_model() -> ChatOpenAI:
    load_env_file()

    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is empty or not set in .env")
    if any(ord(ch) > 127 for ch in api_key):
        raise RuntimeError("DASHSCOPE_API_KEY contains non-ASCII characters")

    model_name = os.getenv("QWEN_MODEL", "qwen3-max").strip() or "qwen3-max"
    timeout = float(os.getenv("QWEN_TIMEOUT", "60"))
    max_tokens = int(os.getenv("QWEN_MAX_TOKENS", "1024"))
    max_retries = int(os.getenv("QWEN_MAX_RETRIES", "2"))
    base_url = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).strip()

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        temperature=0,
        http_client=HTTP_CLIENT,
    )


def invoke_qwen(prompt: str) -> str:
    llm = get_qwen_model()
    response = llm.invoke(prompt)
    return response.content or ""


def stream_qwen(prompt: str) -> Iterable[str]:
    llm = get_qwen_model()
    for chunk in llm.stream(prompt):
        content = getattr(chunk, "content", None)
        if content:
            yield content


def bind_tools_qwen(tools: list) -> ChatOpenAI:
    llm = get_qwen_model()
    return llm.bind_tools(tools)
