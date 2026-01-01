import typer
from .commands import auth, backups, devices, compliance
from .commands.health import do_health
from .commands.whoami import whoami

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.command("health")
def health():
    do_health()

app.command("whoami")(whoami)

app.add_typer(auth.app, name="auth", help="Authentication commands")
app.add_typer(backups.app, name="backups", help="Backup and config operations")
app.add_typer(devices.app, name="devices", help="List and manage devices")
app.add_typer(compliance.app, name="compliance", help="Compliance checks and reports")
