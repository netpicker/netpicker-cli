from __future__ import annotations
import os, json, pathlib
from dataclasses import dataclass

CONFIG_DIR = pathlib.Path(os.getenv("XDG_CONFIG_HOME", pathlib.Path.home()/".config"))/"netpicker"
CONFIG_FILE = CONFIG_DIR/"config.json"

@dataclass
class Settings:
    base_url: str
    tenant: str = "default"
    timeout: float = 30.0
    insecure: bool = False
    token: str | None = None  # not stored on disk; fetched from keyring

    def auth_headers(self) -> dict:
        import keyring
        t = self.token or keyring.get_password("netpicker-cli", f"{self.base_url}:{self.tenant}")
        if not t:
            raise SystemExit("No token found. Run: netpicker login --base-url ... --token ...")
        return {"Authorization": f"Bearer {t}"}

def save_config(*, base_url: str, tenant: str = "default"):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"base_url": base_url, "tenant": tenant}, indent=2))

def load_settings() -> Settings:
    if CONFIG_FILE.exists():
        d = json.loads(CONFIG_FILE.read_text())
        return Settings(base_url=d["base_url"], tenant=d.get("tenant","default"))
    # env fallback if file missing
    base = os.getenv("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    tenant = os.getenv("NETPICKER_TENANT", "default")
    return Settings(base_url=base, tenant=tenant)
