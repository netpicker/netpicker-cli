import respx
from httpx import Response
from netpicker_cli.api.client import ApiClient
from netpicker_cli.utils.config import Settings
from netpicker_cli.api.errors import NotFound

@respx.mock
def test_client_404_notfound():
    s = Settings(base_url="https://api", tenant="t", timeout=1.0, insecure=False, token="x")
    c = ApiClient(s)
    respx.get("https://api/miss").mock(return_value=Response(404, json={"detail":"nope"}))
    try:
        c.get("/miss")
    except NotFound:
        pass
    else:
        assert False, "expected NotFound"

@respx.mock
def test_client_retry_429(monkeypatch):
    s = Settings(base_url="https://api", tenant="t", timeout=1.0, insecure=False, token="x")
    c = ApiClient(s)
    calls = {"n":0}
    def resp(_):
        calls["n"]+=1
        return Response(429) if calls["n"]<2 else Response(200, json={"ok":True})
    respx.get("https://api/retry").mock(side_effect=resp)
    r = c.get("/retry").json()
    assert r["ok"] is True
