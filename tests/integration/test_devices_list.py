import respx
import httpx
from typer.testing import CliRunner
from netpicker_cli.cli import app

runner = CliRunner()


@respx.mock
def test_devices_list_roundtrip(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    monkeypatch.setenv("NETPICKER_TENANT", "default")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    respx.get("https://sandbox.netpicker.io/api/v1/devices/default").mock(
        return_value=httpx.Response(200, json={"items": [
            {"ipaddress": "1.1.1.1", "name": "r1", "platform": "cisco_ios", "tags": ["lab"]}
        ]})
    )

    result = runner.invoke(app, ["devices", "list", "--json"])
    assert result.exit_code == 0
    assert '"ipaddress": "1.1.1.1"' in result.output
