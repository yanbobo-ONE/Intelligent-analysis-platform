from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable

import certifi
import httpx
import ssl
from langchain_openai import ChatOpenAI

from load_env import load_env_file

DEFAULT_VENDOR_BASE_URL = "https://cpa.ceastar.cn/v1"
DEFAULT_VENDOR_MODEL = "gpt-5.3-codex"


def _build_http_client() -> httpx.Client:
    if os.getenv('ALLOW_INSECURE_SSL', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        return httpx.Client(verify=False)
    return httpx.Client(verify=ssl.create_default_context(cafile=certifi.where()))


HTTP_CLIENT = _build_http_client()


@lru_cache(maxsize=1)
def get_vendor_model() -> ChatOpenAI:
    load_env_file()

    api_key = os.getenv("VENDOR_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("VENDOR_API_KEY is empty or not set in .env")

    model_name = os.getenv("VENDOR_MODEL", DEFAULT_VENDOR_MODEL).strip() or DEFAULT_VENDOR_MODEL
    timeout = float(os.getenv("VENDOR_TIMEOUT", "60"))
    max_tokens = int(os.getenv("VENDOR_MAX_TOKENS", "1024"))
    max_retries = int(os.getenv("VENDOR_MAX_RETRIES", "0"))
    base_url = os.getenv("VENDOR_BASE_URL", DEFAULT_VENDOR_BASE_URL).strip() or DEFAULT_VENDOR_BASE_URL

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


@lru_cache(maxsize=8)
def get_vendor_model_from_config(base_url: str, model_name: str, api_key: str) -> ChatOpenAI:
    if not api_key:
        raise RuntimeError("api_key is empty")
    return ChatOpenAI(
        api_key=api_key,
        base_url=(base_url or DEFAULT_VENDOR_BASE_URL).strip() or DEFAULT_VENDOR_BASE_URL,
        model=(model_name or DEFAULT_VENDOR_MODEL).strip() or DEFAULT_VENDOR_MODEL,
        max_tokens=int(os.getenv("VENDOR_MAX_TOKENS", "1024")),
        timeout=float(os.getenv("VENDOR_TIMEOUT", "60")),
        max_retries=int(os.getenv("VENDOR_MAX_RETRIES", "0")),
        temperature=0,
        http_client=HTTP_CLIENT,
    )


def stream_vendor_model(prompt: str, base_url: str | None = None, model_name: str | None = None, api_key: str | None = None) -> Iterable[str]:
    llm = get_vendor_model_from_config(
        base_url or os.getenv("VENDOR_BASE_URL", DEFAULT_VENDOR_BASE_URL),
        model_name or os.getenv("VENDOR_MODEL", DEFAULT_VENDOR_MODEL),
        api_key or os.getenv("VENDOR_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")),
    )
    for chunk in llm.stream(prompt):
        content = getattr(chunk, "content", None)
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        yield text
        elif content:
            yield content


def bind_tools_vendor(tools: list) -> ChatOpenAI:
    llm = get_vendor_model()
    return llm.bind_tools(tools)
