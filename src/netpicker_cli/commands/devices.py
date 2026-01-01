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

# 🧹 (removed the unreachable "if tag: ... else: ..." block that was here)

def _filter_by_tag(items: List[dict], tag: str) -> List[dict]:
    t = tag.lower()
    out = []
    for it in items:
        tags = it.get("tags") or []
        if isinstance(tags, str):
            tags = [x.strip() for x in tags.split(",") if x.strip()]
        if any(t == str(x).lower() for x in tags):
            out.append(it)
    return out

@app.command("list")
def list_devices(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
    limit: int = typer.Option(50, "--limit", help="Page size"),
    offset: int = typer.Option(0, "--offset", help="Start offset"),
    all_: bool = typer.Option(False, "--all", help="Fetch all pages"),
):
    """
    List devices. Supports server pagination via limit/offset and --all to fetch everything.
    """
    s = load_settings()
    cli = ApiClient(s)

    # enforce server maximum page size
    if limit > 1000:
        typer.echo("limit capped to 1000 (server maximum)")
        limit = 1000

    def page_fetch(page: int, size: int) -> dict | list:
        return cli.get(f"/api/v1/devices/{s.tenant}", params={"size": size, "page": page}).json()

    def extract_items(payload) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("items", [])
        return []

    collected: list[dict] = []

    # translate offset->page (server expects 1-based `page` and `size`)
    page = (offset // limit) + 1

    if tag:
        # Prefer server-side tag filter
        try:
            resp = cli.post(
                f"/api/v1/devices/{s.tenant}/by_tags",
                json={"tags": [tag], "size": limit, "page": page},
            ).json()
            items = extract_items(resp)
            if all_:
                # try to keep pulling while pages look full
                while True:
                    collected.extend(items)
                    if len(items) < limit:
                        break
                    page += 1
                    resp = cli.post(
                        f"/api/v1/devices/{s.tenant}/by_tags",
                        json={"tags": [tag], "size": limit, "page": page},
                    ).json()
                    items = extract_items(resp)
            else:
                collected = items
        except Exception:
            # fallback: client-side tag filter on paged list
            payload = page_fetch(page, limit)
            items = extract_items(payload)

            def _filter_by_tag_local(things: list[dict]) -> list[dict]:
                t = tag.lower()
                out = []
                for it in things:
                    tags = it.get("tags") or []
                    if isinstance(tags, str):
                        tags = [x.strip() for x in tags.split(",") if x.strip()]
                    if any(str(x).lower() == t for x in tags):
                        out.append(it)
                return out

            if all_:
                while True:
                    collected.extend(_filter_by_tag_local(items))
                    if len(items) < limit:
                        break
                    page += 1
                    payload = page_fetch(page, limit)
                    items = extract_items(payload)
            else:
                collected = _filter_by_tag_local(items)
    else:
        # no tag: straight pagination
        payload = page_fetch(page, limit)
        items = extract_items(payload)

        if all_:
            while True:
                collected.extend(items)
                # stop when the page isn’t full (simple heuristic)
                if len(items) < limit:
                    break
                page += 1
                payload = page_fetch(page, limit)
                items = extract_items(payload)
        else:
            collected = items

    if json_out:
        typer.echo(json.dumps(collected, indent=2))
        return

    rows = [
        [
            it.get("ipaddress"),
            it.get("name"),
            it.get("platform"),
            ",".join(it.get("tags") or []) if isinstance(it.get("tags"), list) else (it.get("tags") or ""),
        ]
        for it in collected
    ]
    typer.echo(tabulate(rows, headers=["ipaddress", "name", "platform", "tags"]))

@app.command("show")
def show_device(
    ip: str = typer.Argument(..., help="Device IP/FQDN"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Show a single device's details.

    Behavior:
    - Loads CLI settings and creates an API client.
    - Calls GET /api/v1/devices/{tenant}/{ip} to retrieve the device.
    - If `--json` is provided, prints the raw JSON response.
    - Otherwise prints a table row with: ipaddress, name, platform, tags, status (uses
      the `status` field or falls back to `state`).
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        resp = cli.get(f"/api/v1/devices/{s.tenant}/{ip}").json()
    except NotFound:
        typer.echo(f"device '{ip}' not found in tenant '{s.tenant}'")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo("Unexpected error while contacting the server:")
        typer.echo(str(e))
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(resp, indent=2))
        return
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
    name: str = typer.Option(..., "--name", help="Friendly name"),
    platform: str = typer.Option(..., "--platform", help="Netmiko platform (e.g., cisco_ios)"),
    port: int = typer.Option(22, "--port", help="SSH port"),
    vault: str = typer.Option(..., "--vault", help="Vault/credential profile name"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
):
    """
    Create a new device.

    Behavior:
    - Loads CLI settings and creates an API client.
    - Constructs a JSON payload from provided options (`ipaddress`, `name`,
            `platform`, `port`, `vault`, `tags`) and POSTs it to
            `/api/v1/devices/{tenant}`. Required fields: `ip`, `name`, `platform`, and `vault` (supply via positional `IP` and `--name`, `--platform`, `--vault`).
    - If `--json` is passed, prints the server JSON response; otherwise
      prints a one-row table with `ipaddress`, `name`, `platform`, and `tags`.
    """
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
    payload = {k: v for k, v in payload.items() if v not in (None, "", [])}
    data = cli.post(f"/api/v1/devices/{s.tenant}", json=payload).json()
    if json_out:
        typer.echo(json.dumps(data, indent=2))
    else:
        item = data if isinstance(data, dict) else {}
        typer.echo(tabulate([[
            item.get("ipaddress", ""),
            item.get("name", ""),
            item.get("platform", ""),
            ",".join(item.get("tags", []) or []),
        ]], headers=["ipaddress", "name", "platform", "tags"]))

# ---- Delete wiring for tests expecting .callback / .__wrapped__

def _delete_device(ip: str, force: bool) -> int:
    """
    Delete a device.

    Behavior:
    - Loads CLI settings and creates an API client.
    - If `force` is False, prompts the user to confirm deletion.
    - Calls DELETE `/api/v1/devices/{tenant}/{ip}`. On success prints "deleted"
      and returns 0. If the device is not found prints "not found" and
      returns 1. On other API errors prints an error message and returns 1.
    """
    s = load_settings()
    cli = ApiClient(s)

    if not force:
        if not typer.confirm(f"Delete device '{ip}' from tenant '{s.tenant}'?", default=False):
            typer.echo("aborted.")
            return 0

    try:
        cli.delete(f"/api/v1/devices/{s.tenant}/{ip}")
        typer.echo("deleted")
        return 0
    except NotFound:
        typer.echo("not found")
        return 1
    except ApiError as e:
        typer.echo(f"error: {e}")
        return 1

@app.command("delete")
def delete_device(
    ip: str = typer.Argument(..., help="Device IP or hostname"),
    force: bool = typer.Option(False, "--force", "-f", help="Do not ask for confirmation"),
):
    """
    Delete a device.

    Wrapper command that invokes the internal `_delete_device` helper which
    performs optional confirmation and calls the API to delete the device.
    On completion it exits with the helper's exit code.
    """
    raise typer.Exit(code=_delete_device(ip, force))

# Expose attributes some tests look for
# keep the internal helper available for tests by name; avoid setting
# `__wrapped__` which Click/Typer may inspect and use for the CLI signature.
_delete_helper = _delete_device
