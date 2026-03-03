import respx
import httpx
from typer.testing import CliRunner
from netpicker_cli.cli import app

runner = CliRunner()


@respx.mock
def test_backups_recent_json(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    monkeypatch.setenv("NETPICKER_TENANT", "default")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    respx.get("https://sandbox.netpicker.io/api/v1/devices/default/recent-configs/").mock(
        return_value=httpx.Response(200, json=[
            {"id": "1", "ipaddress": "1.1.1.1", "name": "r1",
             "upload_date": "2020-01-01T00:00:00", "file_size": 123}
        ])
    )

    result = runner.invoke(app, ["backups", "recent", "--json"])
    assert result.exit_code == 0
    assert '"id": "1"' in result.output
