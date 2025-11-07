from typing import Optional, List
import json
import typer
from tabulate import tabulate
from ..utils.config import load_settings
from ..api.client import ApiClient

app = typer.Typer(add_completion=False, no_args_is_help=True)

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
        # Try server-side filter first
        try:
            resp = cli.post(f"/api/v1/devices/{s.tenant}/by_tags", json={"tags": [tag]}).json()
            items = resp.get("items", resp if isinstance(resp, list) else [])
        except Exception:
            # Fallback: fetch all and filter locally
            resp = cli.get(f"/api/v1/devices/{s.tenant}").json()
            all_items = resp.get("items", resp if isinstance(resp, list) else [])
            items = _filter_by_tag(all_items, tag)
    else:
        resp = cli.get(f"/api/v1/devices/{s.tenant}").json()
        items = resp.get("items", resp if isinstance(resp, list) else [])

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
