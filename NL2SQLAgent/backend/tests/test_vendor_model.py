import os

import pytest

from vendor_model_client import get_vendor_model_from_config


@pytest.mark.integration
def test_vendor_model_smoke() -> None:
    api_key = os.getenv("VENDOR_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        pytest.skip("VENDOR_API_KEY is not configured")

    llm = get_vendor_model_from_config(
        os.getenv("VENDOR_BASE_URL", "https://cpa.ceastar.cn/v1"),
        os.getenv("VENDOR_MODEL", "gpt-5.3-codex"),
        api_key,
    )

    response = llm.invoke("请用一句话回复：模型接入测试成功。")
    content = getattr(response, "content", "")
    assert content
    assert "测试" in content or "成功" in content or len(content) > 0
