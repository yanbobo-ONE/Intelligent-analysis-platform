from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version() -> None:
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "0.1.0"}


def test_vendor_model_configuration_defaults(monkeypatch) -> None:
    from app import vendor_model_client

    monkeypatch.delenv("VENDOR_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("VENDOR_BASE_URL", "https://cpa.ceastar.cn/v1")
    monkeypatch.setenv("VENDOR_MODEL", "gpt-5.3-codex")

    vendor_model_client.get_vendor_model.cache_clear()
    vendor_model_client.get_vendor_model_from_config.cache_clear()

    try:
        vendor_model_client.get_vendor_model()
    except RuntimeError as exc:
        assert "VENDOR_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when API key is missing")
