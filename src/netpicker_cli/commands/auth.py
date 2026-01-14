# src/netpicker_cli/commands/auth.py
from __future__ import annotations
from typing import Optional
import typer

from ..utils.config import save_config, clear_config
from ..utils.command_base import TyperCommand

app = typer.Typer(add_completion=False, no_args_is_help=True)


class LoginCommand(TyperCommand):
    """Command for user authentication and credential storage."""

    def __init__(self, base_url: str, tenant: str, token: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.tenant = tenant
        self.token = token

    def validate_args(self) -> None:
        """Validate login arguments."""
        if not self.base_url.strip():
            raise typer.BadParameter("Base URL cannot be empty")

    def execute(self) -> dict[str, str]:
        """Execute login logic and return credentials info."""
        if not self.token:
            self.token = typer.prompt("Enter API token", hide_input=True)

        # Normalize base URL
        self.base_url = self._normalize_base_url(self.base_url)

        # Persist credentials (returns True if saved to keyring)
        keyring_saved = save_config(base_url=self.base_url, tenant=self.tenant, token=self.token)

        return {
            "base_url": self.base_url,
            "tenant": self.tenant,
            "keyring_saved": keyring_saved,
        }

    def format_output(self, result: dict[str, str]) -> None:
        """Format and display login results."""
        typer.secho("✓ config saved", fg=typer.colors.GREEN)
        typer.echo(f"  Base URL: {result['base_url']}")
        typer.echo(f"  Tenant  : {result['tenant']}")
        typer.echo("")
        
        if result.get("keyring_saved"):
            typer.secho("✓ token saved to keyring", fg=typer.colors.GREEN)
        else:
            typer.secho("⚠ keyring not available - set token via environment variable:", fg=typer.colors.YELLOW)
            typer.echo(f"  export NETPICKER_TOKEN=\"<your-token>\"")
            typer.echo("")
        typer.echo("Tip: run `netpicker whoami` to verify.")

    @staticmethod
    def _normalize_base_url(u: str) -> str:
        u = (u or "").strip()
        if not u:
            return u
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        return u.rstrip("/")


class LogoutCommand(TyperCommand):
    """Command for removing stored authentication credentials."""

    def __init__(self, base_url: Optional[str] = None, tenant: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.tenant = tenant

    def validate_args(self) -> None:
        """Validate logout arguments."""
        # base_url and tenant are optional now - if not provided, we just clear the config file
        pass

    def execute(self) -> dict[str, str]:
        """Execute logout logic."""
        removed_keyring = False
        removed_config = False
        
        # If base_url and tenant provided, try to remove from keyring
        if self.base_url and self.tenant:
            self.base_url = self._normalize_base_url(self.base_url)
            try:
                import keyring
                key = f"{self.base_url}:{self.tenant}"
                keyring.delete_password("netpicker-cli", key)
                removed_keyring = True
            except Exception:
                # Keyring not available or password doesn't exist
                pass
        
        # Always clear the config file
        removed_config = clear_config()

        return {
            "base_url": self.base_url or "",
            "tenant": self.tenant or "",
            "removed_keyring": removed_keyring,
            "removed_config": removed_config,
        }

    def format_output(self, result: dict[str, str]) -> None:
        """Format and display logout results."""
        if result.get("removed_keyring"):
            typer.secho("✓ token removed from keyring", fg=typer.colors.GREEN)
        if result.get("removed_config"):
            typer.secho("✓ config file cleared", fg=typer.colors.GREEN)
        if not result.get("removed_keyring") and not result.get("removed_config"):
            typer.echo("Nothing to clear")

    @staticmethod
    def _normalize_base_url(u: str) -> str:
        u = (u or "").strip()
        if not u:
            return u
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        return u.rstrip("/")


@app.command("login")
def login(
    base_url: str = typer.Option(..., "--base-url", help="API base URL (e.g., https://sandbox.netpicker.io)"),
    tenant: str = typer.Option(..., "--tenant", help="Tenant name (e.g., default)"),
    token: Optional[str] = typer.Option(None, "--token", help="Bearer token"),
) -> None:
    """
    Save credentials to the OS keyring and remember base_url/tenant for this CLI.
    """
    cmd = LoginCommand(base_url=base_url, tenant=tenant, token=token)
    cmd.run()


@app.command("logout")
def logout(
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API base URL (optional, for keyring cleanup)"),
    tenant: Optional[str] = typer.Option(None, "--tenant", help="Tenant name (optional, for keyring cleanup)"),
) -> None:
    """
    Remove saved credentials. Clears the config file and optionally removes token from keyring.
    
    If --base-url and --tenant are provided, also removes the token from the OS keyring.
    """
    cmd = LogoutCommand(base_url=base_url, tenant=tenant)
    cmd.run()
