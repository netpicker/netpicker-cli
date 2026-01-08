import json
import typer
from typing import List, Optional
from tabulate import tabulate
from ..utils.config import load_settings
from ..api.client import ApiClient, AsyncApiClient
import asyncio
from ..api.errors import ApiError
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.helpers import extract_items_from_response, safe_dict_get
from inspect import iscoroutinefunction, isawaitable
import threading as _threading

# Optional callbacks for completion hooks
on_success = None  # type: ignore[assignment]
on_failure = None  # type: ignore[assignment]

def _invoke_callback(cb, *args, **kwargs) -> None:
    """Invoke a callback if provided, supporting sync or async callables."""
    if cb is None:
        return
    try:
        def _run_coro(coro):
            import asyncio as _asyncio
            try:
                _asyncio.get_running_loop()
                t = _threading.Thread(target=lambda: _asyncio.run(coro))
                t.start(); t.join()
            except RuntimeError:
                _asyncio.run(coro)

        if iscoroutinefunction(cb):
            _run_coro(cb(*args, **kwargs))
        else:
            result = cb(*args, **kwargs)
            if isawaitable(result):
                _run_coro(result)
    except Exception:
        # Swallow callback exceptions to avoid breaking primary command flow
        pass
from ..utils.output import OutputFormatter, OutputFormat

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """
    Show available compliance commands when no subcommand is provided.
    """
    if ctx.invoked_subcommand is None:
        typer.echo("Netpicker Compliance Commands:")
        typer.echo("")
        typer.echo("Available commands:")
        typer.echo("  overview        Get compliance overview for the tenant")
        typer.echo("  report-tenant   Get compliance report for the tenant")
        typer.echo("  devices         Get policy devices list for the tenant")
        typer.echo("  export          Export the tenant compliance report")
        typer.echo("  status          Get compliance status for a device")
        typer.echo("  failures        Get compliance failures for the tenant")
        typer.echo("  log             Log compliance for a config id")
        typer.echo("  report-config   Report compliance for a specific config id")
        typer.echo("")
        typer.echo("Examples:")
        typer.echo("  netpicker compliance overview")
        typer.echo("  netpicker compliance report-tenant")
        typer.echo("  netpicker compliance devices")
        typer.echo("  netpicker compliance status 192.168.1.1")
        typer.echo("")
        typer.echo("Use 'netpicker compliance <command> --help' for more information about a specific command.")
        raise typer.Exit()





@app.command("overview")
def overview(
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get compliance overview for the tenant.

    Calls GET /api/v1/compliance/{tenant}/overview.
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        data = cli.get(f"/api/v1/compliance/{s.tenant}/overview").json()
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        if not isinstance(data, dict):
            typer.echo(str(data))
            return

        devices = data.get("devices", {}) or {}
        policies = data.get("policies", {}) or {}

        rows = []
        for k, v in devices.items():
            rows.append({"category": "device", "severity": k, "count": v})
        for k, v in policies.items():
            rows.append({"category": "policy", "status": k, "count": v})

        formatter.output(rows, headers=["category", "severity", "status", "count"])
    else:
        formatter.output(data)


@app.command("report-tenant")
def tenant_report(
    policy: List[str] = typer.Option(None, "--policy", "-p", help="Filter by policy (repeatable)"),
    ruleset: Optional[str] = typer.Option(None, "--ruleset", help="Filter by ruleset"),
    rule: Optional[str] = typer.Option(None, "--rule", help="Filter by rule"),
    outcome: List[str] = typer.Option(None, "--outcome", help="Filter by outcome (repeatable)"),
    tags: List[str] = typer.Option(None, "--tag", help="Filter by tag (repeatable)"),
    ipaddress: Optional[str] = typer.Option(None, "--ipaddress", help="Filter by ipaddress"),
    ipaddresses: List[str] = typer.Option(None, "--ipaddresses", help="Filter by multiple ipaddresses"),
    q: Optional[str] = typer.Option(None, "--q", help="Free-text query"),
    ordering: List[str] = typer.Option(None, "--ordering", help="Ordering fields (repeatable)"),
    page: int = typer.Option(1, "--page", help="Page number (1-based)"),
    size: int = typer.Option(50, "--size", help="Page size (max 1000)"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    parallel: int = typer.Option(0, "--parallel", help="Enable parallel fetch with given concurrency (0=disabled)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get compliance report for the tenant.

    Supports filtering by policy, ruleset, rule, outcome, tags, ipaddress, free-text `q`, ordering,
    and pagination via `--page` and `--size` (max 1000). Use `--all` to retrieve all pages.
    """
    s = load_settings()
    cli = ApiClient(s)

    if size > 1000:
        typer.echo("size capped to 1000")
        size = 1000

    def _fetch(p):
        params = {}
        if policy:
            params["policy"] = policy
        if ruleset:
            params["ruleset"] = ruleset
        if rule:
            params["rule"] = rule
        if outcome:
            params["outcome"] = outcome
        if tags:
            params["tags"] = tags
        if ipaddress:
            params["ipaddress"] = ipaddress
        if ipaddresses:
            params["ipaddresses"] = ipaddresses
        if q:
            params["q"] = q
        if ordering:
            params["ordering"] = ordering
        params["page"] = p
        params["size"] = size
        return cli.get(f"/api/v1/compliance/{s.tenant}/report", params=params).json()

    try:
        if all_pages and parallel and parallel > 0:
            async def _fetch_all():
                async_client = AsyncApiClient(s)
                all_items = []
                cur = 1
                stop = False
                try:
                    while not stop:
                        batch_pages = [cur + i for i in range(parallel)]
                        tasks = []
                        for p in batch_pages:
                            params = {}
                            if policy: params["policy"] = policy
                            if ruleset: params["ruleset"] = ruleset
                            if rule: params["rule"] = rule
                            if outcome: params["outcome"] = outcome
                            if tags: params["tags"] = tags
                            if ipaddress: params["ipaddress"] = ipaddress
                            if ipaddresses: params["ipaddresses"] = ipaddresses
                            if q: params["q"] = q
                            if ordering: params["ordering"] = ordering
                            params["page"] = p
                            params["size"] = size
                            tasks.append(async_client.get(f"/api/v1/compliance/{s.tenant}/report", params=params))
                        responses = await asyncio.gather(*tasks, return_exceptions=True)
                        for resp in responses:
                            if isinstance(resp, Exception):
                                items = []
                            else:
                                data = resp.json()
                                items = extract_items_from_response(data)
                            if not items:
                                stop = True
                                break
                            all_items.extend(items)
                            if isinstance(data, dict):
                                pages = data.get("pages")
                                if pages and cur >= pages:
                                    stop = True
                                    break
                        cur += parallel
                finally:
                    await async_client.close()
                return {"items": all_items, "total": len(all_items)}

            result = asyncio.run(_fetch_all())
        elif all_pages:
            cur = 1
            all_items = []
            while True:
                data = _fetch(cur)
                items = extract_items_from_response(data)
                if not items:
                    break
                all_items.extend(items)
                pages = safe_dict_get(data, "pages", None)
                if pages and cur >= pages:
                    break
                cur += 1
            result = {"items": all_items, "total": len(all_items)}
        else:
            result = _fetch(page)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    items = result.get("items", []) if isinstance(result, dict) else result
    if not items:
        typer.echo("No report entries")
        return

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["id", "ip", "name", "policy", "rule", "outcome", "exec_at"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        rows = []
        for it in items:
            rows.append({
                "id": it.get("id"),
                "ip": it.get("ipaddress"),
                "name": it.get("name"),
                "policy": it.get("policy"),
                "rule": it.get("rule"),
                "outcome": it.get("outcome"),
                "exec_at": it.get("exec_at"),
            })
        formatter.output(rows, headers=headers)
    else:
        formatter.output(items)


@app.command("devices")
def policy_devices(
    policy: List[str] = typer.Option(None, "--policy", "-p", help="Filter by policy (repeatable)"),
    ruleset: Optional[str] = typer.Option(None, "--ruleset", help="Filter by ruleset"),
    rule: Optional[str] = typer.Option(None, "--rule", help="Filter by rule"),
    outcome: List[str] = typer.Option(None, "--outcome", help="Filter by outcome (repeatable)"),
    tags: List[str] = typer.Option(None, "--tag", help="Filter by tag (repeatable)"),
    ipaddress: Optional[str] = typer.Option(None, "--ipaddress", help="Filter by ipaddress"),
    ipaddresses: List[str] = typer.Option(None, "--ipaddresses", help="Filter by multiple ipaddresses"),
    q: Optional[str] = typer.Option(None, "--q", help="Free-text query"),
    ordering: List[str] = typer.Option(None, "--ordering", help="Ordering fields (repeatable)"),
    page: int = typer.Option(1, "--page", help="Page number (1-based)"),
    size: int = typer.Option(50, "--size", help="Page size (max 1000)"),
    all_pages: bool = typer.Option(False, "--all", help="Fetch all pages"),
    parallel: int = typer.Option(0, "--parallel", help="Enable parallel fetch with given concurrency (0=disabled)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get policy devices list for the tenant.

    Supports the same filters as the tenant report endpoint and pagination.
    """
    s = load_settings()
    cli = ApiClient(s)

    if size > 1000:
        typer.echo("size capped to 1000")
        size = 1000

    def _fetch(p):
        params = {}
        if policy:
            params["policy"] = policy
        if ruleset:
            params["ruleset"] = ruleset
        if rule:
            params["rule"] = rule
        if outcome:
            params["outcome"] = outcome
        if tags:
            params["tags"] = tags
        if ipaddress:
            params["ipaddress"] = ipaddress
        if ipaddresses:
            params["ipaddresses"] = ipaddresses
        if q:
            params["q"] = q
        if ordering:
            params["ordering"] = ordering
        params["page"] = p
        params["size"] = size
        return cli.get(f"/api/v1/compliance/{s.tenant}/devices", params=params).json()

    try:
        if all_pages and parallel and parallel > 0:
            async def _fetch_all():
                async_client = AsyncApiClient(s)
                all_items = []
                cur = 1
                stop = False
                try:
                    while not stop:
                        batch_pages = [cur + i for i in range(parallel)]
                        tasks = []
                        for p in batch_pages:
                            params = {}
                            if policy: params["policy"] = policy
                            if ruleset: params["ruleset"] = ruleset
                            if rule: params["rule"] = rule
                            if outcome: params["outcome"] = outcome
                            if tags: params["tags"] = tags
                            if ipaddress: params["ipaddress"] = ipaddress
                            if ipaddresses: params["ipaddresses"] = ipaddresses
                            if q: params["q"] = q
                            if ordering: params["ordering"] = ordering
                            params["page"] = p
                            params["size"] = size
                            tasks.append(async_client.get(f"/api/v1/compliance/{s.tenant}/devices", params=params))
                        responses = await asyncio.gather(*tasks, return_exceptions=True)
                        for resp in responses:
                            if isinstance(resp, Exception):
                                items = []
                            else:
                                data = resp.json()
                                items = extract_items_from_response(data)
                            if not items:
                                stop = True
                                break
                            all_items.extend(items)
                            if isinstance(data, dict):
                                pages = data.get("pages")
                                if pages and cur >= pages:
                                    stop = True
                                    break
                        cur += parallel
                finally:
                    await async_client.close()
                return all_items

            items = asyncio.run(_fetch_all())
        elif all_pages:
            cur = 1
            all_items = []
            while True:
                data = _fetch(cur)
                items = extract_items_from_response(data)
                if not items:
                    break
                all_items.extend(items)
                pages = safe_dict_get(data, "pages", None)
                if pages and cur >= pages:
                    break
                cur += 1
            items = all_items
        else:
            data = _fetch(page)
            items = extract_items_from_response(data)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["ip", "name", "summary"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        rows: list[dict] = []
        for it in items:
            summary = it.get("summary") or {}
            if isinstance(summary, dict):
                summary_str = ", ".join([f"{k}:{v}" for k, v in summary.items()])
            else:
                summary_str = str(summary)
            rows.append({
                "ip": it.get("ipaddress"),
                "name": it.get("name"),
                "summary": summary_str,
            })
        formatter.output(rows, headers=headers)
    else:
        formatter.output(items)


@app.command("export")
def export_report(
    policy: List[str] = typer.Option(None, "--policy", "-p", help="Filter by policy (repeatable)"),
    ruleset: Optional[str] = typer.Option(None, "--ruleset", help="Filter by ruleset"),
    rule: Optional[str] = typer.Option(None, "--rule", help="Filter by rule"),
    outcome: List[str] = typer.Option(None, "--outcome", help="Filter by outcome (repeatable)"),
    tags: List[str] = typer.Option(None, "--tag", help="Filter by tag (repeatable)"),
    ipaddress: Optional[str] = typer.Option(None, "--ipaddress", help="Filter by ipaddress"),
    ipaddresses: List[str] = typer.Option(None, "--ipaddresses", help="Filter by multiple ipaddresses"),
    q: Optional[str] = typer.Option(None, "--q", help="Free-text query"),
    ordering: List[str] = typer.Option(None, "--ordering", help="Ordering fields (repeatable)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Export the tenant compliance report.

    Supports the same filters as the report endpoint. Returns a string (or JSON) suitable for saving.
    """
    s = load_settings()
    cli = ApiClient(s)

    params = {}
    if policy:
        params["policy"] = policy
    if ruleset:
        params["ruleset"] = ruleset
    if rule:
        params["rule"] = rule
    if outcome:
        params["outcome"] = outcome
    if tags:
        params["tags"] = tags
    if ipaddress:
        params["ipaddress"] = ipaddress
    if ipaddresses:
        params["ipaddresses"] = ipaddresses
    if q:
        params["q"] = q
    if ordering:
        params["ordering"] = ordering

    try:
        resp = cli.get(f"/api/v1/compliance/{s.tenant}/export", params=params)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    # Safely parse JSON, fall back to text when response is plain string
    is_json = True
    try:
        data = resp.json()
    except Exception:
        data = resp.text
        is_json = False

    if json_out:
        format = "json"

    if is_json:
        formatter = OutputFormatter(format=format, output_file=output_file)
        formatter.output(data)
    else:
        # plain text export; honor --output if provided
        if output_file:
            from pathlib import Path as _Path
            p = _Path(output_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(str(data))
        else:
            typer.echo(str(data))


@app.command("status")
def device_status(
    ipaddress: str = typer.Argument(..., help="Device IP/FQDN"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get compliance status for a device.

    Calls GET /api/v1/compliance/{tenant}/status/{ipaddress}.
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        resp = cli.get(f"/api/v1/compliance/{s.tenant}/status/{ipaddress}")
    except ApiError as e:
        typer.echo(f"API error: {e}")
        _invoke_callback(on_failure, e)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        _invoke_callback(on_failure, e)
        raise typer.Exit(code=1)

    # parse JSON safely
    is_json = True
    try:
        data = resp.json()
    except Exception:
        data = resp.text
        is_json = False

    if json_out:
        format = "json"

    if not is_json:
        # treat as plain text result
        if output_file:
            from pathlib import Path as _Path
            p = _Path(output_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(str(data))
        else:
            typer.echo(str(data))
        _invoke_callback(on_success, data)
        return

    if not isinstance(data, dict):
        formatter = OutputFormatter(format=format, output_file=output_file)
        formatter.output(data)
        _invoke_callback(on_success, data)
        return

    ip = data.get("ipaddress") or ipaddress
    executed = data.get("executed") or data.get("executed_at") or data.get("timestamp")
    summary = data.get("summary") or {}

    formatter = OutputFormatter(format=format, output_file=output_file)

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        rows: list[dict] = [
            {"section": "meta", "key": "ipaddress", "value": ip},
            {"section": "meta", "key": "executed", "value": executed},
        ]
        if isinstance(summary, dict) and summary:
            for k, v in summary.items():
                rows.append({"section": "summary", "key": k, "value": v})
        headers = ["section", "key", "value"]
        formatter.output(rows, headers=headers)
        _invoke_callback(on_success, {
            "ipaddress": ip,
            "executed": executed,
            "summary": summary,
        })
    else:
        formatter.output(data)
        _invoke_callback(on_success, data)


@app.command("failures")
def failures(
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get compliance failures for the tenant.

    Calls GET /api/v1/compliance/{tenant}/failures.
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        resp = cli.get(f"/api/v1/compliance/{s.tenant}/failures")
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    # safe parse
    try:
        data = resp.json()
        is_json = True
    except Exception:
        data = resp.text
        is_json = False

    if json_out:
        format = "json"

    items = data if isinstance(data, list) else (data.get("items", []) if isinstance(data, dict) else [])
    if not items:
        typer.echo("No failures")
        return

    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["ip", "executed", "summary"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        rows = []
        for it in items:
            ip = it.get("ipaddress")
            executed = it.get("executed") or it.get("executed_at")
            summary = it.get("summary") or {}
            if isinstance(summary, dict):
                summary_str = ", ".join([f"{k}:{v}" for k, v in summary.items()])
            else:
                summary_str = str(summary)
            rows.append({"ip": ip, "executed": executed, "summary": summary_str})
        formatter.output(rows, headers=headers)
    else:
        formatter.output(items)


@app.command("log")
def log_compliance(
    config_id: str = typer.Argument(..., help="Config id"),
    body: Optional[str] = typer.Option(None, "--body", help="JSON string or @file.json to send as request body"),
    example: bool = typer.Option(False, "--example", help="Print a sample payload JSON and exit"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Log compliance for a config id.

    Calls POST /api/v1/compliance/{tenant}/log/{config_id}.

    By default this will send an empty JSON object as the request body. Use
    `--body '{"key": "value"}'` or `--body @file.json` to provide a body.
    """
    s = load_settings(); cli = ApiClient(s)

    if example:
        sample = {
            "outcome": "SUCCESS",
            "rule_name": "rule_1_01_install_the_latest_firmware",
            "rule_id": "cis_wlc_1_wireless_lan_controller/rule_1_01",
            "exec_at": "2026-01-01T12:26:48.363Z",
            "exec_ns": 0,
            "commit": "498c6e87fa8233cdde380cab699265130fa6a456",
            "excinfo": {"message": "", "tb": {}},
            "passinfo": {"passed": []},
            "cli_log": [],
            "policy": "cis_wlc_1_wireless_lan_controller",
        }
        typer.echo(json.dumps(sample, indent=2))
        return

    payload = {}
    if body:
        try:
            if body.startswith("@"):
                path = body[1:]
                with open(path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            else:
                payload = json.loads(body)
        except Exception as e:
            typer.echo(f"Invalid --body payload: {e}")
            raise typer.Exit(code=2)

    try:
        resp = cli.post(f"/api/v1/compliance/{s.tenant}/log/{config_id}", json=payload)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    # parse response
    try:
        data = resp.json()
        is_json = True
    except Exception:
        data = resp.text
        is_json = False

    if json_out:
        format = "json"

    if is_json:
        formatter = OutputFormatter(format=format, output_file=output_file)
        formatter.output(data)
    else:
        if output_file:
            from pathlib import Path as _Path
            p = _Path(output_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(str(data))
        else:
            typer.echo(str(data))


@app.command("report-config")
def report_config(
    config_id: str = typer.Argument(..., help="Config id"),
    body: Optional[str] = typer.Option(None, "--body", help="JSON string or @file.json to send as request body (array or object)"),
    example: bool = typer.Option(False, "--example", help="Print a sample payload JSON and exit"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Report compliance for a specific config id.

    Calls POST /api/v1/compliance/{tenant}/report/{config_id}.

    The endpoint expects a JSON array of log entries. Use `--body @file.json` or
    `--body '[{...}]'`. Use `--example` to print a sample array payload.
    """
    s = load_settings(); cli = ApiClient(s)

    if example:
        sample = [
            {
                "outcome": "SUCCESS",
                "rule_name": "rule_1_01_install_the_latest_firmware",
                "rule_id": "cis_wlc_1_wireless_lan_controller/rule_1_01",
                "exec_at": "2026-01-01T12:40:04.716Z",
                "exec_ns": 0,
                "commit": "498c6e87fa8233cdde380cab699265130fa6a456",
                "excinfo": {
                    "message": "",
                    "tb": {"path": "example.py", "lineno": 1, "relline": 0, "lines": ["print('ok')"]},
                },
                "passinfo": {"passed": [{"lineno": 1, "original": "check-firmware", "explanation": "Firmware is up-to-date"}]},
                "cli_log": [{"tenant": s.tenant, "ipaddress": "192.0.2.1", "commands": [{"command": "show version", "response": "Version 1.2.3"}]}],
                "policy": "cis_wlc_1_wireless_lan_controller",
            }
        ]
        typer.echo(json.dumps(sample, indent=2))
        return

    payload = []
    if body:
        try:
            if body.startswith("@"):
                path = body[1:]
                with open(path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
            else:
                payload = json.loads(body)
            # accept single object or list
            if isinstance(payload, dict):
                payload = [payload]
            if not isinstance(payload, list):
                raise ValueError("payload must be a JSON array or object")
        except Exception as e:
            typer.echo(f"Invalid --body payload: {e}")
            raise typer.Exit(code=2)

    try:
        resp = cli.post(f"/api/v1/compliance/{s.tenant}/report/{config_id}", json=payload)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    try:
        data = resp.json()
        is_json = True
    except Exception:
        data = resp.text
        is_json = False

    if json_out:
        format = "json"

    if is_json:
        formatter = OutputFormatter(format=format, output_file=output_file)
        formatter.output(data)
    else:
        if output_file:
            from pathlib import Path as _Path
            p = _Path(output_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(str(data))
        else:
            typer.echo(str(data))
