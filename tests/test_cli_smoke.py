from typer.testing import CliRunner
from netpicker_cli.cli import app

runner = CliRunner()

def test_cli_help():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "devices" in r.stdout
    assert "backups" in r.stdout
    assert "health" in r.stdout
