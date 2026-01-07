import respx
from httpx import Response
from typer.testing import CliRunner
from netpicker_cli.cli import app

runner = CliRunner()

@respx.mock
def test_devices_list_table(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://api")
    monkeypatch.setenv("NETPICKER_TENANT", "t")
    monkeypatch.setenv("NETPICKER_TOKEN", "x")
    respx.get("https://api/api/v1/devices/t").mock(
        return_value=Response(200, json={"items":[
            {"ipaddress":"1.1.1.1","name":"r1","platform":"cisco_ios","tags":["lab","core"]},
            {"ipaddress":"2.2.2.2","name":"r2","platform":"arista_eos","tags":[]},
        ]})
    )
    r = runner.invoke(app, ["devices","list"])
    assert r.exit_code == 0
    assert "1.1.1.1" in r.stdout
    assert "r2" in r.stdout

@respx.mock
def test_devices_show_json(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://api")
    monkeypatch.setenv("NETPICKER_TENANT", "t")
    monkeypatch.setenv("NETPICKER_TOKEN", "x")
    respx.get("https://api/api/v1/devices/t/r1").mock(
        return_value=Response(200, json={"ipaddress":"r1","name":"R1","platform":"cisco_ios","tags":["lab"]})
    )
    r = runner.invoke(app, ["devices","show","r1","--json"])
    assert r.exit_code == 0
    assert '"platform": "cisco_ios"' in r.stdout
