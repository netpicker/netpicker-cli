import respx
import httpx
from typer.testing import CliRunner
from netpicker_cli.cli import app

runner = CliRunner()


@respx.mock
def test_devices_delete_ok(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    monkeypatch.setenv("NETPICKER_TENANT", "default")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    respx.delete("https://sandbox.netpicker.io/api/v1/devices/default/1.2.3.4").mock(
        return_value=httpx.Response(204)
    )

    result = runner.invoke(app, ["devices", "delete", "1.2.3.4", "--force"])
    assert result.exit_code == 0
    assert "deleted" in result.output


@respx.mock
def test_devices_delete_not_found(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    monkeypatch.setenv("NETPICKER_TENANT", "default")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    respx.delete("https://sandbox.netpicker.io/api/v1/devices/default/9.9.9.9").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )

    result = runner.invoke(app, ["devices", "delete", "9.9.9.9", "--force"])
    assert result.exit_code == 1
    assert "not found" in result.output
