import json
import typer
from tabulate import tabulate
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("list-policies")
def list_policies(json_out: bool = typer.Option(False, "--json", "--json-out")):
    """
    List compliance policies available on the server.

    Calls GET /api/v1/compliance/{tenant}/policies and prints a compact
    table of policy id and name. Use `--json` to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    try:
        data = cli.get(f"/api/v1/compliance/{s.tenant}/policies").json()
    except NotFound:
        typer.echo("No compliance policies found for this tenant.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(data, indent=2))
        return

    items = data if isinstance(data, list) else data.get("items", [])
    rows = [[it.get("id"), it.get("name") or it.get("title") or ""] for it in items]
    typer.echo(tabulate(rows, headers=["id", "name"]))


@app.command("check")
def run_check(
    ip: str = typer.Argument(..., help="Device IP/FQDN"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Run compliance checks for a device.

    Calls POST /api/v1/compliance/{tenant}/devices/{ip}/run and prints the
    server response. Use `--json` to output raw JSON.
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        data = cli.post(f"/api/v1/compliance/{s.tenant}/devices/{ip}/run").json()
    except NotFound:
        typer.echo(f"device '{ip}' not found for tenant '{s.tenant}'")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(data, indent=2))
        return

    # Try to present a simple summary
    report = data.get("report") if isinstance(data, dict) else None
    if report:
        initiated = report.get("initiated")
        finalized = report.get("finalized")
        compliant = report.get("is_compliant")
        typer.echo(f"initiated: {initiated}  finalized: {finalized}  compliant: {compliant}")
    else:
        typer.echo(str(data))


@app.command("report")
def show_report(
    ip: str = typer.Argument(..., help="Device IP/FQDN"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Show the latest compliance report for a device.

    Calls GET /api/v1/compliance/{tenant}/devices/{ip}/report and prints a
    short summary. Use `--json` to output the full report.
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        data = cli.get(f"/api/v1/compliance/{s.tenant}/devices/{ip}/report").json()
    except NotFound:
        typer.echo(f"device '{ip}' not found for tenant '{s.tenant}'")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(data, indent=2))
        return

    rpt = data if isinstance(data, dict) else {}
    summary = rpt.get("summary") or {}
    typer.echo(tabulate([[rpt.get("initiated"), rpt.get("finalized"), rpt.get("is_compliant"), summary]], headers=["initiated","finalized","is_compliant","summary"]))
