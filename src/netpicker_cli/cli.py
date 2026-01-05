import typer
from .commands import auth, backups, devices, compliance, compliance_policy, automation
from .commands.health import do_health
from .commands.whoami import whoami

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.command("health", help="Check system health and connectivity")
def health():
    do_health()

app.command("whoami", help="Display current user information")(whoami)

app.add_typer(auth.app, name="auth", help="Authentication commands")
app.add_typer(backups.app, name="backups", help="Backup and config operations")
app.add_typer(devices.app, name="devices", help="List and manage devices")
app.add_typer(compliance.app, name="compliance", help="Compliance checks and reports")
app.add_typer(compliance_policy.app, name="policy", help="Compliance policy management")
app.add_typer(automation.app, name="automation", help="Automation commands")
