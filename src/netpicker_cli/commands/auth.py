import keyring
import typer
from ..utils.config import save_config

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.callback(invoke_without_command=True)
def login(
    base_url: str = typer.Option(..., "--base-url", envvar="NETPICKER_BASE_URL"),
    token: str = typer.Option(None, "--token", envvar="NETPICKER_TOKEN", help="Bearer token"),
    tenant: str = typer.Option("default", "--tenant", envvar="NETPICKER_TENANT"),
):
    """
    Store base URL and token securely (keyring).
    """
    if not token:
        token = typer.prompt("Enter API token", hide_input=True)
    save_config(base_url=base_url, tenant=tenant)
    keyring.set_password("netpicker-cli", f"{base_url}:{tenant}", token)
    typer.secho("✓ credentials saved", fg=typer.colors.GREEN)
