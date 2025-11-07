import json
import typer
from tabulate import tabulate
from pathlib import Path
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..utils.files import atomic_write

app = typer.Typer(add_completion=False, no_args_is_help=True)

@app.command("recent")
def recent(
    limit: int = 10,
    json_out: bool = typer.Option(False, "--json", "--json-out", help="Output JSON instead of table"),
):
    s = load_settings()
    cli = ApiClient(s)
    data = cli.get(f"/api/v1/devices/{s.tenant}/recent-configs/", params={"limit": limit}).json()
    items = data.get("items", data if isinstance(data, list) else [])
    if json_out:
        typer.echo(json.dumps(items, indent=2)); return

    def _sz(it): return it.get("size") or it.get("file_size")
    def _ts(it): return it.get("created_at") or it.get("upload_date")
    def _err(it): return "ERR" if it.get("readout_error") else ""
    rows = [[it.get("name") or it.get("device"),
             it.get("ipaddress"),
             it.get("id") or it.get("config_id"),
             _ts(it), _sz(it), _err(it)] for it in items]
    typer.echo(tabulate(rows, headers=["device","ip","config_id","created_at","size","error"]))

@app.command("list")
def list_configs(
    ip: str = typer.Option(..., "--ip", help="Device IP/FQDN"),
    limit: int = 20,
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    s = load_settings(); cli = ApiClient(s)
    data = cli.get(f"/api/v1/devices/{s.tenant}/{ip}/configs", params={"limit": limit}).json()
    items = data.get("items", data if isinstance(data, list) else [])
    if json_out: typer.echo(json.dumps(items, indent=2)); return
    def _ts(it): return it.get("created_at") or it.get("upload_date")
    def _sz(it): return it.get("size") or it.get("file_size")
    rows = [[it.get("id"), _ts(it), _sz(it), it.get("digest") or it.get("hash")] for it in items]
    typer.echo(tabulate(rows, headers=["id","created_at","size","digest"]))

@app.command("fetch")
def fetch(
    ip: str = typer.Option(..., "--ip"),
    id: str = typer.Option(..., "--id"),
    output: Path = typer.Option(Path("."), "--output", "-o", help="Directory to save file"),
):
    s = load_settings(); cli = ApiClient(s)
    blob = cli.get_binary(f"/api/v1/devices/{s.tenant}/{ip}/configs/{id}")
    output.mkdir(parents=True, exist_ok=True)
    dest = output / f"{ip}-{id}.cfg"
    atomic_write(str(dest), blob)
    typer.secho(f"saved: {dest}", fg=typer.colors.GREEN)

@app.command("search")
def search_configs(
    q: str = typer.Option("", "--q", help="Search query (substring, case-insensitive)"),
    since: str = typer.Option("", "--since", help="ISO timestamp or server-supported relative"),
    limit: int = typer.Option(20, "--limit", help="Max results to return"),
    device: str = typer.Option("", "--device", help="Search only this device IP/FQDN"),
    scope: str = typer.Option("recent", "--scope", help="Fallback scope: recent|device"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Search configs across devices.
    Tries server endpoint: GET /devices/{tenant}/search-configs/
    Fallbacks:
      --device <ip>: GET /devices/{tenant}/{ip}/configs
      --scope recent: GET /devices/{tenant}/recent-configs/
    """
    s = load_settings(); cli = ApiClient(s)
    params = {}
    if q: params["q"] = q
    if since: params["since"] = since
    if limit: params["limit"] = str(limit)

    # 1) Try server-side search first (if any param supplied; some servers require q)
    try:
        # Note: some deployments may require "query" instead of "q" (adjust once API spec is confirmed)
        data = cli.get(f"/api/v1/devices/{s.tenant}/search-configs/", params=params).json()
        items = data.get("items", data if isinstance(data, list) else [])
    except Exception:
        # 2) Fallbacks
        q_lower = (q or "").lower()

        def _match(it: dict) -> bool:
            # fields likely available in both recent and per-device lists
            hay = " ".join(
                str(x)
                for x in [
                    it.get("name") or it.get("device"),
                    it.get("ipaddress"),
                    it.get("digest"),
                    it.get("os_version"),
                    it.get("readout_error") or "",
                ]
                if x is not None
            ).lower()
            return q_lower in hay if q_lower else True

        items = []
        if device or scope == "device":
            # search within a single device’s configs
            resp = cli.get(f"/api/v1/devices/{s.tenant}/{device}/configs", params={"limit": limit}).json()
            src = resp.get("items", resp if isinstance(resp, list) else [])
            for it in src:
                if _match(it):
                    items.append(it)
                    if len(items) >= limit:
                        break
        else:
            # search recent configs across all devices
            resp = cli.get(f"/api/v1/devices/{s.tenant}/recent-configs/", params={"limit": max(limit, 100)}).json()
            src = resp.get("items", resp if isinstance(resp, list) else [])
            for it in src:
                if _match(it):
                    items.append(it)
                    if len(items) >= limit:
                        break

    # Output
    if json_out:
        import json as _json
        typer.echo(_json.dumps(items, indent=2)); return

    from tabulate import tabulate
    def _sz(it): return it.get("size") or it.get("file_size")
    def _ts(it): return it.get("created_at") or it.get("upload_date")
    rows = [[it.get("name") or it.get("device"),
             it.get("ipaddress"),
             it.get("id") or it.get("config_id"),
             _ts(it),
             _sz(it)] for it in items]
    typer.echo(tabulate(rows, headers=["device","ip","config_id","created_at","size"]))

@app.command("commands")
def backup_commands(
    platform: str = typer.Option("", "--platform", help="Filter to a platform (e.g., cisco_ios)"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Show backup command templates per platform: GET /devices/{tenant}/platform-commands/
    """
    s = load_settings(); cli = ApiClient(s)
    data = cli.get(f"/api/v1/devices/{s.tenant}/platform-commands/").json()
    # data format may be dict[platform] -> list[str] or list of {platform, commands}
    if json_out:
        import json as _json
        typer.echo(_json.dumps(data, indent=2)); return

    rows = []
    # normalize a couple of likely shapes
    if isinstance(data, dict):
        for plat, cmds in data.items():
            if platform and plat != platform: continue
            for c in cmds or []:
                rows.append([plat, c])
    elif isinstance(data, list):
        for entry in data:
            plat = entry.get("platform") or entry.get("name")
            if platform and plat != platform: continue
            for c in entry.get("commands", []) or []:
                rows.append([plat, c])
    else:
        typer.echo("Unrecognized response shape"); return

    typer.echo(tabulate(rows, headers=["platform", "command"]))
