import os
from dataclasses import dataclass

@dataclass
class Settings:
    base_url: str
    tenant: str
    timeout: float = 30.0
    insecure: bool = False
    token: str | None = None

    def auth_headers(self) -> dict:
        import keyring
        t = self.token or os.environ.get("NETPICKER_TOKEN") or keyring.get_password(
            "netpicker-cli", f"{self.base_url}:{self.tenant}"
        )
        if not t:
            raise SystemExit("No token found. Run: netpicker login --base-url ... --token ...")
        return {"Authorization": f"Bearer {t}"}

def load_settings() -> Settings:
    base = os.environ.get("NETPICKER_BASE_URL", "https://sandbox.netpicker.io")
    tenant = os.environ.get("NETPICKER_TENANT", "default")
    token = os.environ.get("NETPICKER_TOKEN")
    insecure = os.environ.get("NETPICKER_INSECURE", "false").lower() == "true"
    timeout = float(os.environ.get("NETPICKER_TIMEOUT", "30"))
    return Settings(base_url=base, tenant=tenant, timeout=timeout, insecure=insecure, token=token)

# --- persistence helpers used by commands/auth.py ---

def save_config(base_url: str, tenant: str, token: str | None) -> None:
    """
    Persist credentials. We store the token in the OS keyring and export
    base_url/tenant to the user's environment for future shells if desired.
    """
    import keyring
    if token:
        keyring.set_password("netpicker-cli", f"{base_url}:{tenant}", token)
    # We don't modify dotfiles here; env vars are supported but optional.
    # Users can export NETPICKER_BASE_URL / NETPICKER_TENANT if they want.

def save_token(base_url: str, tenant: str, token: str) -> None:
    """Alias, kept for future use."""
    save_config(base_url, tenant, token)
