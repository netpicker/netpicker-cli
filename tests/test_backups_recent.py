import respx
import httpx
from netpicker_cli.utils.config import Settings
from netpicker_cli.commands.backups import recent

@respx.mock
def test_backups_recent_json(capsys):
    s = Settings(base_url="https://sandbox.netpicker.io", tenant="default")
    # recent-configs returns either list or {items:[...]} — test list
    respx.get("https://sandbox.netpicker.io/api/v1/devices/default/recent-configs/").mock(
        return_value=httpx.Response(200, json=[
            {"id":"1","ipaddress":"1.1.1.1","name":"r1","upload_date":"2020-01-01T00:00:00","file_size":123}
        ])
    )
    recent(limit=1, json_out=True)
    out = capsys.readouterr().out
    assert '"id": "1"' in out
