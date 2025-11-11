from typing import Optional, List
import json
import typer
from tabulate import tabulate
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound

app = typer.Typer(add_completion=False, no_args_is_help=True)

def _as_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", [])
    return []

    if tag:
        try:
            resp = cli.post(f"/api/v1/devices/{s.tenant}/by_tags", json={"tags": [tag]}).json()
            items = _as_items(resp)
        except Exception:
            resp = cli.get(f"/api/v1/devices/{s.tenant}").json()
            all_items = _as_items(resp)
            items = _filter_by_tag(all_items, tag)
    else:
        resp = cli.get(f"/api/v1/devices/{s.tenant}").json()
        items = _as_items(resp)

def _filter_by_tag(items: List[dict], tag: str) -> List[dict]:
    t = tag.lower()
    out = []
    for it in items:
        tags = it.get("tags") or []
        # tags may be list or comma string depending on API; normalize to list of strings
        if isinstance(tags, str):
            tags = [x.strip() for x in tags.split(",") if x.strip()]
        if any(t == str(x).lower() for x in tags):
            out.append(it)
    return out

@app.command("list")
def list_devices(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    s = load_settings()
    cli = ApiClient(s)

    items: List[dict] = []

    if tag:
        try:
            resp = cli.post(f"/api/v1/devices/{s.tenant}/by_tags", json={"tags": [tag]}).json()
            items = _as_items(resp)
        except Exception:
            resp = cli.get(f"/api/v1/devices/{s.tenant}").json()
            all_items = _as_items(resp)
            items = _filter_by_tag(all_items, tag)
    else:
        resp = cli.get(f"/api/v1/devices/{s.tenant}").json()
        items = _as_items(resp)

    if json_out:
        typer.echo(json.dumps(items, indent=2))
        return

    rows = [
        [
            it.get("ipaddress"),
            it.get("name"),
            it.get("platform"),
            ",".join(it.get("tags") or []) if isinstance(it.get("tags"), list) else (it.get("tags") or ""),
        ]
        for it in items
    ]
    typer.echo(tabulate(rows, headers=["ipaddress", "name", "platform", "tags"]))

@app.command("show")
def show_device(
    ip: str = typer.Argument(..., help="Device IP/FQDN"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    s = load_settings(); cli = ApiClient(s)
    resp = cli.get(f"/api/v1/devices/{s.tenant}/{ip}").json()
    if json_out:
        import json as _json
        typer.echo(_json.dumps(resp, indent=2)); return
    from tabulate import tabulate
    row = [
        resp.get("ipaddress"),
        resp.get("name"),
        resp.get("platform"),
        ",".join(resp.get("tags", [])) if isinstance(resp.get("tags"), list) else (resp.get("tags") or ""),
        resp.get("status") or resp.get("state"),
    ]
    typer.echo(tabulate([row], headers=["ipaddress", "name", "platform", "tags", "status"]))

@app.command("create")
def create_device(
    ip: str = typer.Argument(..., help="IP or hostname"),
    name: str = typer.Option("", "--name", help="Friendly name"),
    platform: str = typer.Option("", "--platform", help="Netmiko platform (e.g., cisco_ios)"),
    port: int = typer.Option(22, "--port", help="SSH port"),
    vault: str = typer.Option("", "--vault", help="Vault/credential profile name"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """Create a device."""
    s = load_settings()
    cli = ApiClient(s)

    payload = {
        "ipaddress": ip,
        "name": name or None,
        "platform": platform or None,
        "port": port,
        "vault": vault or None,
        "tags": [t.strip() for t in tags.split(",")] if tags else [],
    }
    # drop Nones
    payload = {k: v for k, v in payload.items() if v not in (None, "", [])}

    data = cli.post(f"/api/v1/devices/{s.tenant}", json=payload).json()
    if json_out:
        import json as _json
        print(_json.dumps(data, indent=2))
    else:
        from tabulate import tabulate
        item = data if isinstance(data, dict) else {}
        print(tabulate([[
            item.get("ipaddress",""),
            item.get("name",""),
            item.get("platform",""),
            ",".join(item.get("tags",[]) or []),
        ]], headers=["ipaddress","name","platform","tags"]))

@app.command("delete")
def delete_device(
    ip: str = typer.Argument(..., help="Device IP or hostname"),
    force: bool = typer.Option(False, "--force", "-f", help="Do not ask for confirmation"),
):
    """
    Delete a device: DELETE /api/v1/devices/{tenant}/{ip}
    """
    s = load_settings()
    cli = ApiClient(s)

    if not force:
        ok = typer.confirm(f"Delete device '{ip}' from tenant '{s.tenant}'?", default=False)
        if not ok:
            typer.echo("aborted.")
            raise typer.Exit(code=0)

    try:
        r = cli.delete(f"/api/v1/devices/{s.tenant}/{ip}")
        # _request already raised for 4xx/5xx; 204/200 both acceptable
        typer.echo("deleted")
    except NotFound:
        typer.echo("not found")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"error: {e}")
        raise typer.Exit(code=1)
