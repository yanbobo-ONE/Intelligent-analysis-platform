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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Direct OpenAI-compatible API test.")
    parser.add_argument("--base-url", default=os.getenv("VENDOR_BASE_URL", DEFAULT_BASE_URL), help="API base URL")
    parser.add_argument("--model", default=os.getenv("VENDOR_MODEL", DEFAULT_MODEL_NAME), help="Model name")
    parser.add_argument("--prompt", default=os.getenv("VENDOR_TEST_PROMPT", DEFAULT_PROMPT), help="Prompt to send")
    parser.add_argument("--api-key", default=os.getenv("VENDOR_API_KEY") or os.getenv("DASHSCOPE_API_KEY"), help="API key to use")
    parser.add_argument("--traceback", action="store_true", help="Print full traceback on failure")
    return parser


def _print_env_status(name: str, value: str | None) -> None:
    if value:
        if name == "API_KEY":
            print(f"{name}: set (length={len(value)})")
        else:
            print(f"{name}: {value}")
    else:
        print(f"{name}: missing")


def _extract_text(payload: dict[str, Any]) -> str:
    output = payload.get("output") or {}
    if isinstance(output, dict):
        for key in ("text", "content", "message"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> int:
    args = _build_parser().parse_args()
    api_key = (args.api_key or "").strip()
    base_url = (args.base_url or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model_name = (args.model or DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME
    prompt = args.prompt or DEFAULT_PROMPT

    print("=== DIRECT REQUEST TEST ===")
    _print_env_status("API_KEY", api_key)
    _print_env_status("BASE_URL", base_url)
    _print_env_status("MODEL", model_name)
    _print_env_status("PROMPT", prompt)

    if not api_key:
        print("\nError: missing API key. Set VENDOR_API_KEY / DASHSCOPE_API_KEY or pass --api-key.", file=sys.stderr)
        return 1

    url = base_url.rstrip("/") + "/responses"
    body = {
        "model": model_name,
        "input": prompt,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
            try:
                payload = response.json()
            except Exception:
                print("\nResponse was not JSON:", file=sys.stderr)
                print(response.text, file=sys.stderr)
                return 5
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

    print("\n--- response ---")
    print(_extract_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
