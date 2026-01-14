import typer
from .commands import auth, backups, devices, compliance, compliance_policy, automation
from .commands.health import do_health
from .commands.whoami import whoami
from .utils.logging import setup_logging

app = typer.Typer(add_completion=False, no_args_is_help=True)

# Global options
@app.callback()
def main_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output"),
):
    """
    NetPicker CLI - Network device management and automation.

    Use --verbose/-v for detailed debug output.
    Use --quiet/-q to suppress informational messages.
    """
    # Set up logging based on flags
    logger = setup_logging(verbose=verbose, quiet=quiet)

    # Store logging config in context for commands to access
    ctx.obj = {
        "verbose": verbose,
        "quiet": quiet,
        "logger": logger
    }

@app.command("health", help="Check system health and connectivity")
def health(ctx: typer.Context):
    do_health()

app.command("whoami", help="Display current user information")(whoami)

app.add_typer(auth.app, name="auth", help="Authentication commands")
app.add_typer(backups.app, name="backups", help="Backup and config operations")
app.add_typer(devices.app, name="devices", help="List and manage devices")
app.add_typer(compliance.app, name="compliance", help="Compliance checks and reports")
app.add_typer(compliance_policy.app, name="policy", help="Compliance policy management")
app.add_typer(automation.app, name="automation", help="Automation commands")
