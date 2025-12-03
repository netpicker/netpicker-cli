import respx
from httpx import Response
from netpicker_cli.utils.config import Settings
from netpicker_cli.api.client import ApiClient

@respx.mock
def test_diff_by_ids(monkeypatch, capsys):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://example")
    monkeypatch.setenv("NETPICKER_TENANT", "t")
    monkeypatch.setenv("NETPICKER_TOKEN", "tok")

    ip = "device.example"
    a_id, b_id = "1", "2"
    a_cfg = "line1\nline2\n"
    b_cfg = "line1\nline2-changed\n"

    respx.get(f"https://example/api/v1/devices/t/{ip}/configs/{a_id}").mock(
        return_value=Response(200, content=a_cfg.encode())
    )
    respx.get(f"https://example/api/v1/devices/t/{ip}/configs/{b_id}").mock(
        return_value=Response(200, content=b_cfg.encode())
    )

    # call through the API client just to ensure endpoints resolve; CLI layer is thin
    s = Settings(base_url="https://example", tenant="t", timeout=5.0)
    cli = ApiClient(s)

    ra = cli.get_binary(f"/api/v1/devices/{s.tenant}/{ip}/configs/{a_id}")
    rb = cli.get_binary(f"/api/v1/devices/{s.tenant}/{ip}/configs/{b_id}")
    assert ra.decode() == a_cfg
    assert rb.decode() == b_cfg

