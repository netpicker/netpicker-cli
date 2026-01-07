# src/netpicker_cli/commands/auth.py
from __future__ import annotations
from typing import Optional
import typer

from ..utils.config import save_config

app = typer.Typer(add_completion=False, no_args_is_help=True)

def _normalize_base_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return u
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u.rstrip("/")

@app.command("login")
def login(
    base_url: str = typer.Option(..., "--base-url", help="API base URL (e.g., https://dev.netpicker.io)"),
    tenant: str = typer.Option(..., "--tenant", help="Tenant name (e.g., default)"),
    token: Optional[str] = typer.Option(None, "--token", help="Bearer token"),
) -> None:
    """
    Save credentials to the OS keyring and remember base_url/tenant for this CLI.
    """
    if not token:
        token = typer.prompt("Enter API token", hide_input=True)

    base_url = _normalize_base_url(base_url)
    if not base_url:
        raise typer.BadParameter("Base URL cannot be empty")

    # Persist everything (token goes into keyring inside save_config)
    save_config(base_url=base_url, tenant=tenant, token=token)

    typer.secho("✓ credentials saved", fg=typer.colors.GREEN)
    typer.echo(f"Base URL: {base_url}")
    typer.echo(f"Tenant  : {tenant}")
    typer.echo("Tip: run `netpicker whoami` to verify.")

@app.command("logout")
def logout(
    base_url: str = typer.Option(..., "--base-url", help="API base URL used when logging in"),
    tenant: str = typer.Option(..., "--tenant", help="Tenant used when logging in"),
) -> None:
    """
    Remove the saved token from keyring for the given base_url + tenant.
    """
    import keyring
    base_url = _normalize_base_url(base_url)
    key = f"{base_url}:{tenant}"
    keyring.delete_password("netpicker-cli", key)
    typer.secho("✓ token removed from keyring", fg=typer.colors.GREEN)
