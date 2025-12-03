import respx
from httpx import Response
from typer.testing import CliRunner
from netpicker_cli.cli import app

runner = CliRunner()

@respx.mock
def test_backups_recent_table(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://api")
    monkeypatch.setenv("NETPICKER_TENANT", "t")
    monkeypatch.setenv("NETPICKER_TOKEN", "x")
    respx.get("https://api/api/v1/devices/t/recent-configs/").mock(
        return_value=Response(200, json={"items":[
            {"name":"r1","ipaddress":"r1","id":"2","upload_date":"2025-01-01","file_size":10},
            {"name":"r1","ipaddress":"r1","id":"1","upload_date":"2024-12-31","file_size":9},
        ]})
    )
    r = runner.invoke(app, ["backups","recent"])
    assert r.exit_code == 0
    assert "r1" in r.stdout

@respx.mock
def test_backups_diff_latest_two(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://api")
    monkeypatch.setenv("NETPICKER_TENANT", "t")
    monkeypatch.setenv("NETPICKER_TOKEN", "x")

    # list configs for device
    respx.get("https://api/api/v1/devices/t/r1/configs").mock(
        return_value=Response(200, json={"items":[
            {"id":"2","upload_date":"2025-01-01","file_size":5},
            {"id":"1","upload_date":"2024-12-31","file_size":5},
        ]})
    )

    # primary path your code uses: tenant-scoped download
    respx.get("https://api/api/v1/devices/t/r1/configs/1").mock(
        return_value=Response(200, content=b"host r1\nline A\n")
    )
    respx.get("https://api/api/v1/devices/t/r1/configs/2").mock(
        return_value=Response(200, content=b"host r1\nline B\n")
    )

    # keep the raw fallbacks too (harmless)
    respx.get("https://api/api/v1/configs/1/raw").mock(
        return_value=Response(200, content=b"host r1\nline A\n")
    )
    respx.get("https://api/api/v1/configs/2/raw").mock(
        return_value=Response(200, content=b"host r1\nline B\n")
    )

    r = runner.invoke(app, ["backups","diff","--ip","r1"])
    assert r.exit_code == 0
    assert "-line A" in r.stdout
    assert "+line B" in r.stdout
