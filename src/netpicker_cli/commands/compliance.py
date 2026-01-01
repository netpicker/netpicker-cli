import json
import typer
from typing import List, Optional
from tabulate import tabulate
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError

app = typer.Typer(add_completion=False, no_args_is_help=True)





@app.command("overview")
def overview(json_out: bool = typer.Option(False, "--json", "--json-out")):
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
        typer.echo(json.dumps(data, indent=2))
        return

    if not isinstance(data, dict):
        typer.echo(str(data))
        return

    devices = data.get("devices", {}) or {}
    policies = data.get("policies", {}) or {}

    if devices:
        typer.echo("Devices:")
        drows = [[k, v] for k, v in devices.items()]
        typer.echo(tabulate(drows, headers=["severity", "count"]))
    else:
        typer.echo("Devices: none")

    if policies:
        typer.echo("")
        typer.echo("Policies:")
        prows = [[k, v] for k, v in policies.items()]
        typer.echo(tabulate(prows, headers=["status", "count"]))
    else:
        typer.echo("Policies: none")


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
    json_out: bool = typer.Option(False, "--json", "--json-out"),
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
        if all_pages:
            cur = 1
            all_items = []
            while True:
                data = _fetch(cur)
                items = data.get("items") if isinstance(data, dict) else data
                if not items:
                    break
                all_items.extend(items)
                pages = data.get("pages") if isinstance(data, dict) else None
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
        typer.echo(json.dumps(result, indent=2))
        return

    items = result.get("items", []) if isinstance(result, dict) else result
    if not items:
        typer.echo("No report entries")
        return

    rows = []
    for it in items:
        rows.append([
            it.get("id"),
            it.get("ipaddress"),
            it.get("name"),
            it.get("policy"),
            it.get("rule"),
            it.get("outcome"),
            it.get("exec_at"),
        ])

    typer.echo(tabulate(rows, headers=["id", "ip", "name", "policy", "rule", "outcome", "exec_at"]))


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
    json_out: bool = typer.Option(False, "--json", "--json-out"),
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
        if all_pages:
            cur = 1
            all_items = []
            while True:
                data = _fetch(cur)
                items = data.get("items") if isinstance(data, dict) else data
                if not items:
                    break
                all_items.extend(items)
                pages = data.get("pages") if isinstance(data, dict) else None
                if pages and cur >= pages:
                    break
                cur += 1
            items = all_items
        else:
            data = _fetch(page)
            items = data if isinstance(data, list) else data.get("items", [])
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        typer.echo(json.dumps(items, indent=2))
        return

    rows = []
    for it in items:
        summary = it.get("summary") or {}
        if isinstance(summary, dict):
            summary_str = ", ".join([f"{k}:{v}" for k, v in summary.items()])
        else:
            summary_str = str(summary)
        rows.append([it.get("ipaddress"), it.get("name"), summary_str])

    typer.echo(tabulate(rows, headers=["ip", "name", "summary"]))


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
    json_out: bool = typer.Option(False, "--json", "--json-out"),
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
        if is_json:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(json.dumps({"export": data}, indent=2))
        return

    typer.echo(str(data))


@app.command("status")
def device_status(ipaddress: str = typer.Argument(..., help="Device IP/FQDN"), json_out: bool = typer.Option(False, "--json", "--json-out")):
    """
    Get compliance status for a device.

    Calls GET /api/v1/compliance/{tenant}/status/{ipaddress}.
    """
    s = load_settings(); cli = ApiClient(s)
    try:
        resp = cli.get(f"/api/v1/compliance/{s.tenant}/status/{ipaddress}")
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    # parse JSON safely
    is_json = True
    try:
        data = resp.json()
    except Exception:
        data = resp.text
        is_json = False

    if json_out:
        if is_json:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(json.dumps({"status": data}, indent=2))
        return

    if not is_json or not isinstance(data, dict):
        typer.echo(str(data))
        return

    ip = data.get("ipaddress") or ipaddress
    executed = data.get("executed") or data.get("executed_at") or data.get("timestamp")
    summary = data.get("summary") or {}

    typer.echo(f"ipaddress: {ip}")
    typer.echo(f"executed: {executed}")

    if isinstance(summary, dict) and summary:
        rows = [[k, v] for k, v in summary.items()]
        typer.echo(tabulate(rows, headers=["status","count"]))
    else:
        typer.echo("summary: none")


@app.command("failures")
def failures(json_out: bool = typer.Option(False, "--json", "--json-out")):
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
        if is_json:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(json.dumps({"failures": data}, indent=2))
        return

    items = data if isinstance(data, list) else (data.get("items", []) if isinstance(data, dict) else [])
    if not items:
        typer.echo("No failures")
        return

    rows = []
    for it in items:
        ip = it.get("ipaddress")
        executed = it.get("executed") or it.get("executed_at")
        summary = it.get("summary") or {}
        if isinstance(summary, dict):
            summary_str = ", ".join([f"{k}:{v}" for k, v in summary.items()])
        else:
            summary_str = str(summary)
        rows.append([ip, executed, summary_str])

    typer.echo(tabulate(rows, headers=["ip", "executed", "summary"]))


@app.command("log")
def log_compliance(
    config_id: str = typer.Argument(..., help="Config id"),
    body: Optional[str] = typer.Option(None, "--body", help="JSON string or @file.json to send as request body"),
    example: bool = typer.Option(False, "--example", help="Print a sample payload JSON and exit"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
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
        if is_json:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(json.dumps({"result": data}, indent=2))
        return

    typer.echo(str(data))


@app.command("report-config")
def report_config(
    config_id: str = typer.Argument(..., help="Config id"),
    body: Optional[str] = typer.Option(None, "--body", help="JSON string or @file.json to send as request body (array or object)"),
    example: bool = typer.Option(False, "--example", help="Print a sample payload JSON and exit"),
    json_out: bool = typer.Option(False, "--json", "--json-out"),
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
        if is_json:
            typer.echo(json.dumps(data, indent=2))
        else:
            typer.echo(json.dumps({"result": data}, indent=2))
        return

    typer.echo(str(data))
