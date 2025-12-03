# src/netpicker_cli/utils/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Settings:
    base_url: str
    tenant: str
    timeout: float = 30.0
    insecure: bool = False
    token: Optional[str] = None

    def auth_headers(self) -> Dict[str, str]:
        """
        Build Authorization headers. Token is resolved in this order:
        1) Settings.token (if provided)
        2) NETPICKER_TOKEN env var
        3) OS keyring (if available)
        """
        token = self.token or os.environ.get("NETPICKER_TOKEN")

        if token is None:
            # Try keyring if available, but don't crash if it's missing.
            try:
                import keyring  # type: ignore
            except Exception:
                keyring = None

            if keyring:
                token = keyring.get_password("netpicker-cli", f"{self.base_url}:{self.tenant}")

        if not token:
            raise SystemExit("No token found. Run: netpicker login --base-url ... --token ...")

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }


def _env_bool(name: str, *, default: bool = False) -> bool:
    """
    Parse boolean-like env vars.
    True  if value in: 1, true, yes, on
    False if value in: 0, false, no, off
    Else: default
    """
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


def load_settings() -> Settings:
    # Normalize base_url by removing trailing slash (prevents double-slash URLs)
    base = os.environ.get("NETPICKER_BASE_URL", "https://sandbox.netpicker.io").rstrip("/")
    tenant = os.environ.get("NETPICKER_TENANT", "default")
    token = os.environ.get("NETPICKER_TOKEN")

    # Support both knobs:
    # - NETPICKER_INSECURE=1 -> insecure True (skip TLS verify)
    # - NETPICKER_VERIFY=0   -> insecure True (skip TLS verify)
    insecure_flag = _env_bool("NETPICKER_INSECURE", default=False)
    verify_enabled = _env_bool("NETPICKER_VERIFY", default=True)
    insecure = insecure_flag or (not verify_enabled)

    # Timeout parsing (seconds) with safe fallback
    try:
        timeout = float(os.environ.get("NETPICKER_TIMEOUT", "30"))
    except ValueError:
        timeout = 30.0

    return Settings(
        base_url=base,
        tenant=tenant,
        timeout=timeout,
        insecure=insecure,
        token=token,
    )


# --- persistence helpers used by commands/auth.py ---

def save_config(base_url: str, tenant: str, token: str | None) -> None:
    """
    Persist credentials. We store the token in the OS keyring and export
    base_url/tenant to the user's environment for future shells if desired.
    """
    try:
        import keyring  # type: ignore
    except Exception:
        keyring = None

    if token and keyring:
        keyring.set_password("netpicker-cli", f"{base_url}:{tenant}", token)
    # We don't modify dotfiles here; env vars are supported but optional.
    # Users can export NETPICKER_BASE_URL / NETPICKER_TENANT if they want.


def save_token(base_url: str, tenant: str, token: str) -> None:
    """Alias, kept for future use."""
    save_config(base_url, tenant, token)
