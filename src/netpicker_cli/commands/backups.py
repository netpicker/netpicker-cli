import sys
import json
import typer
from typing import Optional, Any, List
from tabulate import tabulate
from pathlib import Path
from ..utils.config import load_settings
from ..api.client import ApiClient, AsyncApiClient
import asyncio
from ..utils.files import atomic_write
import difflib
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.helpers import extract_items_from_response

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """
    Show available backup commands when no subcommand is provided.
    """
    if ctx.invoked_subcommand is None:
        typer.echo("Netpicker Backup Commands:")
        typer.echo("")
        typer.echo("Available commands:")
        typer.echo("  diff      Diff two configs for a device")
        typer.echo("  recent    List the most recent configuration backups across devices")
        typer.echo("  list      List configuration backups for a single device")
        typer.echo("  fetch     Fetch a device config blob and save it to disk")
        typer.echo("  search    Search configs across devices")
        typer.echo("  commands  Show backup command templates per platform")
        typer.echo("  upload    Upload a device config snapshot to Netpicker")
        typer.echo("  history   Show backup history for a device")
        typer.echo("")
        typer.echo("Examples:")
        typer.echo("  netpicker backups list 192.168.1.1")
        typer.echo("  netpicker backups fetch 192.168.1.1 --id <config-id>")
        typer.echo("  netpicker backups diff 192.168.1.1")
        typer.echo("  netpicker backups recent")
        typer.echo("")
        typer.echo("Use 'netpicker backups <command> --help' for more information about a specific command.")
        raise typer.Exit()


@app.command("diff")
def diff_configs(
    ip: str = typer.Argument(..., help="Device IP/hostname"),
    id_a: str = typer.Option("", "--id-a", help="(Optional) older config id"),
    id_b: str = typer.Option("", "--id-b", help="(Optional) newer config id"),
    context: int = typer.Option(3, "--context", help="Unified diff context lines"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON with diff lines"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Diff two configs for a device.
    - If --id-a/--id-b are omitted: diff the two most recent configs.
    - If --id-a/--id-b are provided: both must be present.
    """
    s = load_settings()
    cli = ApiClient(s)

    def download(cfg_id: str) -> str:
        blob = cli.get_binary(f"/api/v1/devices/{s.tenant}/{ip}/configs/{cfg_id}")
        return blob.decode("utf-8", errors="replace")

    # Resolve IDs if not supplied
    if not id_a or not id_b:
        data = cli.get(f"/api/v1/devices/{s.tenant}/{ip}/configs", params={"limit": 2}).json()
        items = extract_items_from_response(data)
        if len(items) < 2:
            typer.secho("Not enough configs to diff (need at least 2).", fg=typer.colors.RED)
            raise typer.Exit(code=2)

        # Oldest -> newest (fallback if timestamps odd)
        def _ts(it): return it.get("created_at") or it.get("upload_date") or ""
        try:
            items = sorted(items[:2], key=_ts)
        except Exception:
            items = items[:2]

        id_a = str(items[0].get("id") or items[0].get("config_id"))
        id_b = str(items[1].get("id") or items[1].get("config_id"))
    else:
        # both ids provided: sanity check
        if not (id_a.strip() and id_b.strip()):
            typer.secho("Both --id-a and --id-b must be provided (or omit both).", fg=typer.colors.RED)
            raise typer.Exit(code=3)

    # Fetch and diff
    a_text = download(id_a).splitlines()
    b_text = download(id_b).splitlines()

    a_name = f"{ip}-{id_a}"
    b_name = f"{ip}-{id_b}"
    diff_lines = list(difflib.unified_diff(a_text, b_text, fromfile=a_name, tofile=b_name, n=context))

    if json_out:
        format = "json"

    if format == "json":
        formatter = OutputFormatter(format=format, output_file=output_file)
        formatter.output({"id_a": id_a, "id_b": id_b, "diff": diff_lines})
    elif format == "table":
        # Table format is the traditional colored diff output
        # If output_file is specified, we write the plain text without colors
        if output_file:
            content = "\n".join(diff_lines) + "\n"
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                f.write(content)
        else:
            for line in diff_lines:
                if line.startswith("+") and not line.startswith("+++"):
                    typer.secho(line, fg=typer.colors.GREEN)
                elif line.startswith("-") and not line.startswith("---"):
                    typer.secho(line, fg=typer.colors.RED)
                else:
                    typer.echo(line)
    elif format in ["csv", "yaml"]:
        formatter = OutputFormatter(format=format, output_file=output_file)
        # For CSV/YAML, a diff list isn't very helpful but we can provide it
        formatter.output({"id_a": id_a, "id_b": id_b, "diff": diff_lines})

@app.command("recent")
def recent(
    limit: int = 10,
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON instead of table"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    List the most recent configuration backups across devices.

    Calls GET /api/v1/devices/{tenant}/recent-configs/ with optional
    `limit` and prints a table of `device`, `ip`, `config_id`, `created_at`,
    `size`, and `error`. Use `--json` to output raw JSON.
    """
    s = load_settings()
    cli = ApiClient(s)
    data = cli.get(f"/api/v1/devices/{s.tenant}/recent-configs/", params={"limit": limit}).json()
    items = extract_items_from_response(data)
    
    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["device", "ip", "config_id", "created_at", "size", "error"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        def _sz(it): return it.get("size") or it.get("file_size")
        def _ts(it): return it.get("created_at") or it.get("upload_date")
        def _err(it): return "ERR" if it.get("readout_error") else ""
        
        rows = []
        for it in items:
            rows.append({
                "device": it.get("name") or it.get("device"),
                "ip": it.get("ipaddress"),
                "config_id": it.get("id") or it.get("config_id"),
                "created_at": _ts(it),
                "size": _sz(it),
                "error": _err(it)
            })
        formatter.output(rows, headers=headers)
    else:
        formatter.output(items)

@app.command("list")
def list_configs(
    ip: str = typer.Argument(..., help="Device IP/FQDN"),
    limit: int = 20,
    page: int = typer.Option(1, "--page", help="Page number (1-based)"),
    size: int = typer.Option(50, "--size", help="Page size"),
    all_: bool = typer.Option(False, "--all", help="Fetch all pages"),
    parallel: int = typer.Option(0, "--parallel", "-p", help="Enable parallel fetch with given concurrency (0=disabled)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    List configuration backups for a single device.

    Calls GET /api/v1/devices/{tenant}/{ip}/configs with pagination support.
    Use --all to fetch all pages, --parallel for concurrent fetching.
    """
    s = load_settings()
    cli = ApiClient(s)

    def _fetch(p):
        params = {"size": size, "page": p}
        return cli.get(f"/api/v1/devices/{s.tenant}/{ip}/configs", params=params).json()

    try:
        if all_ and parallel and parallel > 0:
            async def _fetch_all():
                async_client = AsyncApiClient(s)
                all_items = []
                cur = page
                stop = False
                try:
                    while not stop:
                        batch_pages = [cur + i for i in range(parallel)]
                        tasks = [async_client.get(f"/api/v1/devices/{s.tenant}/{ip}/configs", params={"size": size, "page": p}) for p in batch_pages]
                        responses = await asyncio.gather(*tasks, return_exceptions=True)
                        for resp in responses:
                            if isinstance(resp, Exception):
                                items = []
                            else:
                                data = resp.json()
                                items = extract_items_from_response(data)
                            if len(items) < size:
                                stop = True
                            all_items.extend(items)
                        cur += parallel
                finally:
                    await async_client.close()
                return all_items

            items = asyncio.run(_fetch_all())
        elif all_:
            cur = page
            all_items = []
            while True:
                data = _fetch(cur)
                items = extract_items_from_response(data)
                all_items.extend(items)
                if len(items) < size:
                    break
                cur += 1
            items = all_items
        else:
            data = _fetch(page)
            items = extract_items_from_response(data)
    except Exception as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["id", "created_at", "size", "digest"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        def _ts(it): return it.get("created_at") or it.get("upload_date")
        def _sz(it): return it.get("size") or it.get("file_size")
        rows = [
            {
                "id": it.get("id"),
                "created_at": _ts(it),
                "size": _sz(it),
                "digest": it.get("digest") or it.get("hash")
            }
            for it in items
        ]
        formatter.output(rows, headers=headers)
    else:
        formatter.output(items)


@app.command("fetch")
def fetch(
    ip: str = typer.Argument(..., help="Device IP/hostname"),
    id: str = typer.Option(..., "--id"),
    output: Path = typer.Option(Path("."), "--output", "-o", help="Directory to save file"),
):
    """
    Fetch a device config blob and save it to disk.

    Calls GET /api/v1/devices/{tenant}/{ip}/configs/{id} and writes the
    binary content to `<output>/<ip>-<id>.cfg`. Use `--output` to change the
    destination directory (defaults to current directory).
    """
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
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
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
    if q: params["search_string"] = q
    if since: params["since"] = since
    if limit: params["limit"] = str(limit)

    # 1) Try server-side search first (if any param supplied; some servers require search_string)
    try:
        data = cli.get(f"/api/v1/devices/{s.tenant}/search-configs/", params=params).json()
        # API returns {"results": [...], "debug_logs": [...]}
        search_results = data.get("results", [])
        
        # Convert search results to the expected format for display
        items = []
        for result in search_results:
            device = result.get("device", {})
            matches = result.get("matches", [])
            for match in matches:
                items.append({
                    "device": device.get("name", ""),
                    "ip": device.get("ipaddress", ""),
                    "line_number": match.get("line_number", 0),
                    "content": match.get("content", ""),
                    "config_id": "",  # Not provided in search results
                    "created_at": "",  # Not provided in search results
                    "size": 0  # Not provided in search results
                })
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
            src = extract_items_from_response(resp)
            for it in src:
                if _match(it):
                    items.append(it)
                    if len(items) >= limit:
                        break
        else:
            # search recent configs across all devices
            resp = cli.get(f"/api/v1/devices/{s.tenant}/recent-configs/", params={"limit": max(limit, 100)}).json()
            src = extract_items_from_response(resp)
            for it in src:
                if _match(it):
                    items.append(it)
                    if len(items) >= limit:
                        break

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    
    # Check if we have search results (with line_number and content) or regular config metadata
    is_search_results = items and "line_number" in items[0]
    
    if is_search_results:
        headers = ["device", "ip", "line_number", "content"]
        if format in [OutputFormat.TABLE, OutputFormat.CSV]:
            rows = [
                {
                    "device": it.get("device", ""),
                    "ip": it.get("ip", ""),
                    "line_number": it.get("line_number", 0),
                    "content": it.get("content", "")
                }
                for it in items
            ]
            formatter.output(rows, headers=headers)
        else:
            formatter.output(items)
    else:
        headers = ["device", "ip", "config_id", "created_at", "size"]
        if format in [OutputFormat.TABLE, OutputFormat.CSV]:
            def _ts(it): return it.get("created_at") or it.get("upload_date")
            def _sz(it): return it.get("size") or it.get("file_size")
            rows = [
                {
                    "device": it.get("name") or it.get("device"),
                    "ip": it.get("ipaddress"),
                    "config_id": it.get("id") or it.get("config_id"),
                    "created_at": _ts(it),
                    "size": _sz(it)
                }
                for it in items
            ]
            formatter.output(rows, headers=headers)
        else:
            formatter.output(items)

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

@app.command("upload")
def upload_config(
    ip: str = typer.Argument(..., help="Device IP/hostname"),
    file: str = typer.Option("-", "-f", "--file", help="Config file path or '-' for stdin"),
    changed: bool = typer.Option(False, "--changed", help="Mark as changed (for pipelines)"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """Upload a device config snapshot to Netpicker."""
    s = load_settings()
    cli = ApiClient(s)

    if file == "-":
        content = sys.stdin.read()
    else:
        with open(file, "r", encoding="utf-8") as fh:
            content = fh.read()

    payload = {
        "content": content,
        "changed": changed,
    }
    data = cli.post(f"/api/v1/devices/{s.tenant}/{ip}/configs", json=payload).json()
    if json_out:
        import json as _json
        print(_json.dumps(data, indent=2))
    else:
        from tabulate import tabulate
        cfg = (data or {}).get("config", {})
        print(tabulate([[
            cfg.get("id",""),
            cfg.get("upload_date",""),
            cfg.get("file_size",""),
            cfg.get("digest",""),
            data.get("changed",""),
        ]], headers=["id","created_at","size","digest","changed"]))

@app.command("history")
def history(
    ip: str = typer.Argument(..., help="Device IP/hostname"),
    limit: int = typer.Option(20, "--limit", help="Max items"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Show backup history for a device.

    Example:
      netpicker backups history 192.168.1.1

      netpicker backups history 192.168.1.1 --json
    """
    s = load_settings()
    cli = ApiClient(s)
    data = cli.get(f"/api/v1/devices/{s.tenant}/{ip}/config/history", params={"limit": limit}).json()
    # API may return either a dict with an "items" key or a bare list.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("items", [])
    else:
        items = []
    if json_out:
        import json as _json
        print(_json.dumps(items, indent=2))
    else:
        from tabulate import tabulate
        if not items:
            typer.echo("No history entries returned for this device.")
            return

        def _get_created_at(it):
            return it.get("timestamp") or it.get("upload_date") or it.get("created_at") or ""

        def _get_id(it):
            return it.get("id") or it.get("commit") or it.get("object") or it.get("config_id") or ""

        def _get_size(it):
            return it.get("size") or it.get("file_size") or ""

        def _get_digest(it):
            return it.get("digest") or it.get("hash") or it.get("commit") or ""

        def _get_os(it):
            return (it.get("data") or {}).get("variables", {}).get("os_version", "")

        rows = []
        for it in items:
            rows.append([
                _get_id(it),
                _get_created_at(it),
                _get_size(it),
                _get_digest(it),
                _get_os(it),
            ])
        print(tabulate(rows, headers=["id","created_at","size","digest","os_version"]))
