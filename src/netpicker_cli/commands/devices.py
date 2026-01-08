from typing import Optional, List, Any
import json
import typer
from tabulate import tabulate
from ..utils.config import load_settings
from ..utils.logging import get_logger, output_message
from ..api.client import ApiClient, AsyncApiClient
import asyncio
from ..api.errors import ApiError, NotFound
from ..utils.validation import validate_tag, validate_limit, validate_offset
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.helpers import extract_items_from_response, filter_items_by_tag, format_tags_for_display
from ..utils.cache import get_session_cache

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """
    Show available device commands when no subcommand is provided.
    """
    if ctx.invoked_subcommand is None:
        output_message("Netpicker Device Commands:")
        output_message("")
        output_message("Available commands:")
        output_message("  list     List devices with optional filtering")
        output_message("  show     Show a single device's details")
        output_message("  create   Create a new device")
        output_message("  delete   Delete a device")
        output_message("")
        output_message("Examples:")
        output_message("  netpicker devices list")
        output_message("  netpicker devices list --tag production")
        output_message("  netpicker devices show 192.168.1.1")
        output_message("  netpicker devices create 192.168.1.1 --name router01 --platform cisco_ios")
        output_message("")
        output_message("Use 'netpicker devices <command> --help' for more information about a specific command.")
        raise typer.Exit()


@app.command("list")
def list_devices(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
    limit: int = typer.Option(50, "--limit", help="Page size"),
    offset: int = typer.Option(0, "--offset", help="Start offset"),
    all_: bool = typer.Option(False, "--all", help="Fetch all pages"),
    parallel: int = typer.Option(0, "--parallel", "-p", help="Enable parallel fetch with given concurrency (0=disabled)"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache and fetch fresh data"),
):
    """
    List devices. Supports server pagination via limit/offset and --all to fetch everything.
    Cache is used for simple queries (no filters, default pagination) unless --no-cache is used.
    """
    # Validate inputs
    if tag:
        validate_tag(tag)
    validate_limit(limit)
    validate_offset(offset)

    s = load_settings()
    cli = ApiClient(s)

    # enforce server maximum page size
    if limit > 1000:
        typer.echo("limit capped to 1000 (server maximum)")
        limit = 1000

    def page_fetch(page: int, size: int) -> dict | list:
        return cli.get(f"/api/v1/devices/{s.tenant}", params={"size": size, "page": page}).json()

    collected: list[dict] = []

    # translate offset->page (server expects 1-based `page` and `size`)
    page = (offset // limit) + 1
    
    # Determine if we can use cache: only for simple queries (no tag, no offset, no --all, no custom limit)
    use_cache = not no_cache and not tag and offset == 0 and not all_ and limit == 50

    if tag:
        # Prefer server-side tag filter
        try:
            # If user requested parallel fetching for all pages, use AsyncApiClient
            if all_ and parallel and parallel > 0:
                async def _fetch_all_by_tags():
                    async_client = AsyncApiClient(s)
                    results: list[dict] = []
                    cur_page = page
                    stop = False
                    try:
                        while not stop:
                            # build a batch of pages
                            batch_pages = [cur_page + i for i in range(parallel)]
                            tasks = [async_client.post(f"/api/v1/devices/{s.tenant}/by_tags", json={"tags": [tag], "size": limit, "page": p}) for p in batch_pages]
                            responses = await asyncio.gather(*tasks, return_exceptions=True)
                            for resp in responses:
                                if isinstance(resp, Exception):
                                    items = []
                                else:
                                    items = extract_items_from_response(resp.json())
                                results.extend(items)
                                if len(items) < limit:
                                    stop = True
                                    break
                            cur_page += parallel
                    finally:
                        await async_client.close()
                    return results

                collected = asyncio.run(_fetch_all_by_tags())
            else:
                resp = cli.post(
                    f"/api/v1/devices/{s.tenant}/by_tags",
                    json={"tags": [tag], "size": limit, "page": page},
                ).json()
                items = extract_items_from_response(resp)
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
                        items = extract_items_from_response(resp)
                else:
                    collected = items
        except Exception:
            # fallback: client-side tag filter on paged list
            payload = page_fetch(page, limit)
            items = extract_items_from_response(payload)
            filtered = filter_items_by_tag(items, tag)

            if all_:
                while True:
                    collected.extend(filtered)
                    if len(items) < limit:
                        break
                    page += 1
                    payload = page_fetch(page, limit)
                    items = extract_items_from_response(payload)
                    filtered = filter_items_by_tag(items, tag)
            else:
                collected = filtered
    else:
        # no tag: straight pagination
        try:
            if all_ and parallel and parallel > 0:
                async def _fetch_all_pages():
                    async_client = AsyncApiClient(s)
                    results: list[dict] = []
                    cur_page = page
                    stop = False
                    try:
                        while not stop:
                            batch_pages = [cur_page + i for i in range(parallel)]
                            tasks = [async_client.get(f"/api/v1/devices/{s.tenant}", params={"size": limit, "page": p}) for p in batch_pages]
                            responses = await asyncio.gather(*tasks, return_exceptions=True)
                            for resp in responses:
                                if isinstance(resp, Exception):
                                    items = []
                                else:
                                    items = extract_items_from_response(resp.json())
                                results.extend(items)
                                if len(items) < limit:
                                    stop = True
                                    break
                            cur_page += parallel
                    finally:
                        await async_client.close()
                    return results

                collected = asyncio.run(_fetch_all_pages())
            else:
                # Use cache for simple queries only (default page size, no offset, no --all)
                if use_cache:
                    cache_key = f"devices:{s.tenant}:default"
                    with get_session_cache(use_cache=True) as cache:
                        payload = cache.get(cache_key, lambda: page_fetch(page, limit))
                else:
                    payload = page_fetch(page, limit)
                
                items = extract_items_from_response(payload)

                if all_:
                    while True:
                        collected.extend(items)
                        # stop when the page isn't full (simple heuristic)
                        if len(items) < limit:
                            break
                        page += 1
                        payload = page_fetch(page, limit)
                        items = extract_items_from_response(payload)
                else:
                    collected = items
        except Exception:
            # Fallback: sequential pagination if async path fails
            if use_cache:
                cache_key = f"devices:{s.tenant}:default"
                with get_session_cache(use_cache=True) as cache:
                    payload = cache.get(cache_key, lambda: page_fetch(page, limit))
            else:
                payload = page_fetch(page, limit)
            items = extract_items_from_response(payload)
            collected = items

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["ipaddress", "name", "platform", "tags"]
    
    # Map data for table/csv formats to match original headers
    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        rows = [
            {
                "ipaddress": it.get("ipaddress"),
                "name": it.get("name"),
                "platform": it.get("platform"),
                "tags": format_tags_for_display(it.get("tags")),
            }
            for it in collected
        ]
        formatter.output(rows, headers=headers)
    else:
        # For JSON/YAML, output the full objects
        formatter.output(collected)

@app.command("show")
def show_device(
    ip: str = typer.Argument(..., help="Device IP/FQDN"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
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
        output_message(f"device '{ip}' not found in tenant '{s.tenant}'", "error")
        raise typer.Exit(code=1)
    except ApiError as e:
        output_message(f"API error: {e}", "error")
        raise typer.Exit(code=1)
    except Exception as e:
        output_message("Unexpected error while contacting the server:", "error")
        output_message(str(e), "error")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["ipaddress", "name", "platform", "tags", "status"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        row = {
            "ipaddress": resp.get("ipaddress"),
            "name": resp.get("name"),
            "platform": resp.get("platform"),
            "tags": format_tags_for_display(resp.get("tags")),
            "status": resp.get("status") or resp.get("state"),
        }
        formatter.output([row], headers=headers)
    else:
        formatter.output(resp)

@app.command("create")
def create_device(
    ip: str = typer.Argument(..., help="IP or hostname"),
    name: str = typer.Option(..., "--name", help="Friendly name"),
    platform: str = typer.Option(..., "--platform", help="Netmiko platform (e.g., cisco_ios)"),
    port: int = typer.Option(22, "--port", help="SSH port"),
    vault: str = typer.Option(..., "--vault", help="Vault/credential profile name"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
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
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["ipaddress", "name", "platform", "tags"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        item = data if isinstance(data, dict) else {}
        row = {
            "ipaddress": item.get("ipaddress", ""),
            "name": item.get("name", ""),
            "platform": item.get("platform", ""),
            "tags": ",".join(item.get("tags", []) or []),
        }
        formatter.output([row], headers=headers)
    else:
        formatter.output(data)

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
