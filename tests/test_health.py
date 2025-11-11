import respx
from httpx import Response

def test_health_ok(monkeypatch):
    # make load_settings() happy
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://example")
    monkeypatch.setenv("NETPICKER_TENANT", "t")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    respx.get("https://example/api/v1/status").mock(return_value=Response(200, json={"ok": True}))

    from netpicker_cli.api.client import ApiClient
    from netpicker_cli.utils.config import load_settings

    cli = ApiClient(load_settings())
    r = cli.get("/api/v1/status").json()
    assert r["ok"] is True
