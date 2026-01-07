from netpicker_cli.utils.config import load_settings

def test_load_settings_env(monkeypatch):
    monkeypatch.setenv("NETPICKER_BASE_URL","https://api")
    monkeypatch.setenv("NETPICKER_TENANT","t")
    monkeypatch.setenv("NETPICKER_TOKEN","tok")
    # support either style
    monkeypatch.setenv("NETPICKER_INSECURE","1")
    monkeypatch.setenv("NETPICKER_VERIFY","0")

    s = load_settings()
    assert s.base_url == "https://api"
    assert s.tenant == "t"
    assert s.insecure is True
    assert "Authorization" in s.auth_headers()

