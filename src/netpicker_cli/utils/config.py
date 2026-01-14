# src/netpicker_cli/utils/config.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


# Config file location: ~/.config/netpicker/config.json
CONFIG_DIR = Path.home() / ".config" / "netpicker"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Settings:
    base_url: str
    tenant: str
    timeout: float = 30.0
    insecure: bool = False
    token: Optional[str] = None
    verbose: bool = False
    quiet: bool = False

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
                token = keyring.get_password("netpicker-cli", f"{self.base_url}:{self.tenant}")
            except Exception:
                # NoKeyringError, ImportError, or other keyring issues - gracefully continue
                keyring = None

        if not token:
            raise SystemExit("No token found. Run: netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>")

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


def _load_config_file() -> dict:
    """Load config from ~/.config/netpicker/config.json if it exists."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def load_settings() -> Settings:
    # Load from config file first, then override with env vars
    file_config = _load_config_file()
    
    # Environment variables take precedence over config file
    base = os.environ.get("NETPICKER_BASE_URL") or file_config.get("base_url")
    tenant = os.environ.get("NETPICKER_TENANT") or file_config.get("tenant")
    token = os.environ.get("NETPICKER_TOKEN")  # Token from env only (keyring handled in auth_headers)

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

    # Logging configuration
    verbose = _env_bool("NETPICKER_VERBOSE", default=False)
    quiet = _env_bool("NETPICKER_QUIET", default=False)

    return Settings(
        base_url=base,
        tenant=tenant,
        timeout=timeout,
        insecure=insecure,
        token=token,
        verbose=verbose,
        quiet=quiet,
    )


# --- persistence helpers used by commands/auth.py ---

def save_config(base_url: str, tenant: str, token: str | None) -> bool:
    """
    Persist credentials:
    - base_url and tenant are saved to ~/.config/netpicker/config.json
    - token is stored in the OS keyring (if available)
    
    Returns True if token saved to keyring, False if keyring unavailable.
    """
    # Always save base_url and tenant to config file
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_data = {
        "base_url": base_url,
        "tenant": tenant,
    }
    CONFIG_FILE.write_text(json.dumps(config_data, indent=2))
    
    # Try to save token to keyring
    keyring_saved = False
    if token:
        try:
            import keyring  # type: ignore
            keyring.set_password("netpicker-cli", f"{base_url}:{tenant}", token)
            keyring_saved = True
        except Exception:
            # NoKeyringError or other keyring issues - keyring not available
            keyring_saved = False
    
    return keyring_saved


def clear_config() -> bool:
    """
    Remove the config file (~/.config/netpicker/config.json).
    
    Returns True if file was deleted, False if it didn't exist.
    """
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        return True
    return False


def save_token(base_url: str, tenant: str, token: str) -> None:
    """Alias, kept for future use."""
    save_config(base_url, tenant, token)
