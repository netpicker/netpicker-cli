# src/netpicker_cli/commands/auth.py
from __future__ import annotations
from typing import Optional
import typer

from ..utils.config import save_config
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

        # Persist credentials
        save_config(base_url=self.base_url, tenant=self.tenant, token=self.token)

        return {
            "base_url": self.base_url,
            "tenant": self.tenant,
        }

    def format_output(self, result: dict[str, str]) -> None:
        """Format and display login results."""
        typer.secho("✓ credentials saved", fg=typer.colors.GREEN)
        typer.echo(f"Base URL: {result['base_url']}")
        typer.echo(f"Tenant  : {result['tenant']}")
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

    def __init__(self, base_url: str, tenant: str, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.tenant = tenant

    def validate_args(self) -> None:
        """Validate logout arguments."""
        if not self.base_url.strip():
            raise typer.BadParameter("Base URL cannot be empty")

    def execute(self) -> dict[str, str]:
        """Execute logout logic."""
        import keyring

        self.base_url = self._normalize_base_url(self.base_url)
        key = f"{self.base_url}:{self.tenant}"
        keyring.delete_password("netpicker-cli", key)

        return {
            "base_url": self.base_url,
            "tenant": self.tenant,
        }

    def format_output(self, result: dict[str, str]) -> None:
        """Format and display logout results."""
        typer.secho("✓ token removed from keyring", fg=typer.colors.GREEN)

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
    base_url: str = typer.Option(..., "--base-url", help="API base URL (e.g., https://dev.netpicker.io)"),
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
    base_url: str = typer.Option(..., "--base-url", help="API base URL used when logging in"),
    tenant: str = typer.Option(..., "--tenant", help="Tenant used when logging in"),
) -> None:
    """
    Remove the saved token from keyring for the given base_url + tenant.
    """
    cmd = LogoutCommand(base_url=base_url, tenant=tenant)
    cmd.run()
