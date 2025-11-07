import typer
from .commands import auth, backups, devices
from .commands.health import do_health

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.command("health")
def health():
    do_health()

app.add_typer(auth.app, name="login", help="Authenticate and store token")
app.add_typer(backups.app, name="backups", help="Backup and config operations")
app.add_typer(devices.app, name="devices", help="List and manage devices")
