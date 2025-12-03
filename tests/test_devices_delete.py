import respx
import httpx
from netpicker_cli.commands.devices import delete_device

@respx.mock
def test_devices_delete_ok(monkeypatch, capsys):
    # make settings env-driven for load_settings()
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    monkeypatch.setenv("NETPICKER_TENANT", "default")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    # mock DELETE 204
    respx.delete("https://sandbox.netpicker.io/api/v1/devices/default/1.2.3.4").mock(
        return_value=httpx.Response(204)
    )

    # avoid interactive confirm (simulate --force)
    delete_device.callback  # silence pyright
    # call with force=True by bypassing Typer (we’re calling the function directly)
    delete_device.__wrapped__("1.2.3.4", force=True)  # type: ignore

    out = capsys.readouterr().out.strip()
    assert out == "deleted"

@respx.mock
def test_devices_delete_not_found(monkeypatch, capsys):
    monkeypatch.setenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    monkeypatch.setenv("NETPICKER_TENANT", "default")
    monkeypatch.setenv("NETPICKER_TOKEN", "testtoken")

    respx.delete("https://sandbox.netpicker.io/api/v1/devices/default/9.9.9.9").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )

    try:
        delete_device.__wrapped__("9.9.9.9", force=True)  # type: ignore
    except SystemExit as e:
        assert e.code == 1

    out = capsys.readouterr().out.strip()
    assert out == "not found"
