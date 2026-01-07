import respx
import httpx
from netpicker_cli.utils.config import Settings

@respx.mock
def test_devices_list_roundtrip(capsys):
    s = Settings(base_url="https://sandbox.netpicker.io", tenant="default")
    # mock GET /devices/{tenant}
    respx.get("https://sandbox.netpicker.io/api/v1/devices/default").mock(
        return_value=httpx.Response(200, json=[{"ipaddress":"1.1.1.1","name":"r1","platform":"cisco_ios","tags":["lab"]}])
    )
    # import command and run
    from netpicker_cli.commands.devices import list_devices
    list_devices(tag=None, json_out=True)
    out = capsys.readouterr().out
    assert '"ipaddress": "1.1.1.1"' in out

