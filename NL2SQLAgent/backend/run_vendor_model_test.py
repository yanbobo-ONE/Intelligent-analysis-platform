from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://cpa.ceastar.cn/v1"
DEFAULT_MODEL_NAME = "gpt-5.3-codex"
DEFAULT_PROMPT = "Reply with: connection ok"


def _print_env_status(name: str, value: str | None) -> None:
    if value:
        if name == "API_KEY":
            print(f"{name}: set (length={len(value)})")
        else:
            print(f"{name}: {value}")
    else:
        print(f"{name}: missing")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Direct vendor API connectivity test.")
    parser.add_argument("--base-url", default=os.getenv("VENDOR_BASE_URL", DEFAULT_BASE_URL), help="Vendor API base URL")
    parser.add_argument("--model", default=os.getenv("VENDOR_MODEL", DEFAULT_MODEL_NAME), help="Model name")
    parser.add_argument("--prompt", default=os.getenv("VENDOR_TEST_PROMPT", DEFAULT_PROMPT), help="Prompt to send")
    parser.add_argument("--api-key", default=os.getenv("VENDOR_API_KEY") or os.getenv("DASHSCOPE_API_KEY"), help="API key to use")
    parser.add_argument("--max-tokens", type=int, default=int(os.getenv("VENDOR_MAX_TOKENS", "4096")), help="Maximum output tokens")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    parser.add_argument("--traceback", action="store_true", help="Print full traceback on failure")
    return parser


def _extract_text(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("output_text", "text", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        output = payload.get("output")
        if isinstance(output, dict):
            content = output.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        for key in ("text", "output_text", "content"):
                            value = item.get(key)
                            if isinstance(value, str) and value.strip():
                                parts.append(value)
                                break
                    elif isinstance(item, str):
                        parts.append(item)
                if parts:
                    return "".join(parts)
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
                    if isinstance(content, list):
                        parts: list[str] = []
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text")
                                if isinstance(text, str) and text.strip():
                                    parts.append(text)
                            elif isinstance(item, str):
                                parts.append(item)
                        if parts:
                            return "".join(parts)
        return ""
    if isinstance(payload, list):
        parts: list[str] = []
        for item in payload:
            if isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


def main() -> int:
    args = _build_parser().parse_args()

    api_key = (args.api_key or "").strip()
    base_url = (args.base_url or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model_name = (args.model or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
    prompt = args.prompt or DEFAULT_PROMPT
    max_tokens = max(1, int(args.max_tokens))
    url = f"{base_url.rstrip('/')}/responses"

    print("=== DIRECT VENDOR API TEST ===")
    _print_env_status("API_KEY", api_key)
    _print_env_status("BASE_URL", base_url)
    _print_env_status("MODEL", model_name)
    _print_env_status("PROMPT", prompt)
    print(f"URL: {url}")

    if not api_key:
        print(
            "\nError: missing API key. Set VENDOR_API_KEY / DASHSCOPE_API_KEY or pass --api-key.",
            file=sys.stderr,
        )
        return 1

    body = {
        "model": model_name,
        "input": prompt,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    verify_ssl = not args.insecure
    if args.insecure:
        print("WARNING: TLS certificate verification is disabled.")

    try:
        with httpx.Client(timeout=60.0, verify=verify_ssl) as client:
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print("\nRequest failed with HTTP status error:", file=sys.stderr)
        print(f"status_code: {exc.response.status_code}", file=sys.stderr)
        print(f"response_text: {exc.response.text}", file=sys.stderr)
        if args.traceback:
            traceback.print_exc()
        return 2
    except httpx.RequestError as exc:
        print("\nRequest failed with network error:", file=sys.stderr)
        print(f"type: {type(exc).__name__}", file=sys.stderr)
        print(f"detail: {exc}", file=sys.stderr)
        if args.traceback:
            traceback.print_exc()
        return 3
    except Exception as exc:
        print("\nRequest failed with unexpected error:", file=sys.stderr)
        print(f"type: {type(exc).__name__}", file=sys.stderr)
        print(f"detail: {exc}", file=sys.stderr)
        if args.traceback:
            traceback.print_exc()
        return 4

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("\nError: response is not valid JSON.", file=sys.stderr)
        print(response.text, file=sys.stderr)
        return 5

    print("\n--- raw response json ---")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    extracted = _extract_text(data)
    if extracted:
        print("\n--- extracted answer ---")
        print(extracted)
    else:
        print("\nNote: could not extract a final answer text from the JSON payload.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
