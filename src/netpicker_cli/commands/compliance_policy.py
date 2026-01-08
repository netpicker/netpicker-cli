import json
import typer
from typing import Optional
from tabulate import tabulate
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.cli_helpers import with_client, handle_api_errors
from ..utils.helpers import ensure_list, safe_dict_get
from ..utils.cache import get_session_cache

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("list")
@handle_api_errors
def list_policies(
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache and fetch fresh data"),
):
    """
    List compliance policies.

    Calls GET /api/v1/policy/{tenant} and displays available policies.
    Use --json to see the raw response.
    Cache is enabled by default (policies are static) unless --no-cache is used.
    """
    with with_client() as (s, cli):
        cache_key = f"policies:{s.tenant}"
        
        with get_session_cache(use_cache=not no_cache) as cache:
            data = cache.get(cache_key, lambda: cli.get(f"/api/v1/policy/{s.tenant}").json())

    if json_out:
        format = "json"

    policies = ensure_list(data)
    if not policies:
        typer.echo("No policies found.")
        return
    
    formatter = OutputFormatter(format=format, output_file=output_file)
    headers = ["id", "name", "enabled", "read_only"]

    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        rows = []
        for policy in policies:
            rows.append({
                "id": policy.get("id", ""),
                "name": policy.get("name", ""),
                "enabled": "Yes" if policy.get("enabled") else "No",
                "read_only": "Yes" if policy.get("read_only") else "No",
            })
        formatter.output(rows, headers=headers)
    else:
        formatter.output(policies)


@app.command("show")
def show_policy(
    policy_id: str = typer.Argument(..., help="Policy ID"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get details of a specific compliance policy.

    Calls GET /api/v1/policy/{tenant}/{policy_id} and displays policy details.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        data = cli.get(f"/api/v1/policy/{s.tenant}/{policy_id}").json()
    except NotFound:
        typer.echo(f"Policy '{policy_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
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
        rows = []
        # meta
        for k in [
            ("id", data.get("id", "")),
            ("name", data.get("name", "")),
            ("description", data.get("description", "")),
            ("author", data.get("author", "")),
            ("enabled", data.get("enabled", False)),
            ("read_only", data.get("read_only", False)),
            ("created", data.get("created", "")),
            ("changed", data.get("changed", "")),
        ]:
            rows.append({"section": "meta", "key": k[0], "value": k[1]})
        # summary
        summary = data.get("summary", {}) or {}
        for status, count in sorted(summary.items()):
            rows.append({"section": "summary", "key": status, "value": count})
        # rules
        for rule in data.get("rules", []) or []:
            rows.append({
                "section": "rule",
                "key": rule.get("name", ""),
                "value": rule.get("severity", ""),
            })
        formatter.output(rows, headers=["section", "key", "value"])
    else:
        formatter.output(data)


@app.command("update")
def update_policy(
    policy_id: str = typer.Argument(..., help="Policy ID"),
    name: str = typer.Option(None, "--name", help="Policy name"),
    description: str = typer.Option(None, "--description", help="Policy description"),
    author: str = typer.Option(None, "--author", help="Policy author"),
    enabled: bool = typer.Option(None, "--enabled/--disabled", help="Enable or disable policy"),
    policy_type: str = typer.Option(None, "--type", help="Policy type"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Update a compliance policy.

    Calls PATCH /api/v1/policy/{tenant}/{policy_id} to update policy details.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload with provided values
    payload = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if author is not None:
        payload["author"] = author
    if enabled is not None:
        payload["enabled"] = enabled
    if policy_type is not None:
        payload["type"] = policy_type
    
    if not payload:
        typer.echo("No fields to update. Use --name, --description, --author, --enabled, or --type")
        raise typer.Exit(code=1)
    
    try:
        data = cli.patch(f"/api/v1/policy/{s.tenant}/{policy_id}", payload).json()
    except NotFound:
        typer.echo(f"Policy '{policy_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
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
        formatter.output([
            {"policy_id": data.get("id", policy_id), "status": "updated"}
        ], headers=["policy_id", "status"])
    else:
        formatter.output(data)


@app.command("replace")
def replace_policy(
    policy_id: str = typer.Argument(..., help="Policy ID"),
    name: str = typer.Option(..., "--name", help="Policy name"),
    description: str = typer.Option("", "--description", help="Policy description"),
    author: str = typer.Option("", "--author", help="Policy author"),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable or disable policy"),
    policy_type: str = typer.Option("", "--type", help="Policy type"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Replace a compliance policy (full update).

    Calls PUT /api/v1/policy/{tenant}/{policy_id} to completely replace the policy.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build full payload
    payload = {
        "name": name,
        "description": description,
        "author": author,
        "enabled": enabled,
        "type": policy_type,
    }
    
    try:
        data = cli.put(f"/api/v1/policy/{s.tenant}/{policy_id}", payload).json()
    except NotFound:
        typer.echo(f"Policy '{policy_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
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
        formatter.output([
            {"policy_id": data.get("id", policy_id), "status": "replaced"}
        ], headers=["policy_id", "status"])
    else:
        formatter.output(data)


@app.command("create")
def create_policy(
    name: str = typer.Option(..., "--name", help="Policy name"),
    policy_id: str = typer.Option(None, "--id", help="Policy ID"),
    description: str = typer.Option("", "--description", help="Policy description"),
    author: str = typer.Option("", "--author", help="Policy author"),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable or disable policy"),
    policy_type: str = typer.Option("", "--type", help="Policy type"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Create a new compliance policy.

    Calls POST /api/v1/policy/{tenant} to create a new policy.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload
    payload = {
        "name": name,
        "description": description,
        "author": author,
        "enabled": enabled,
        "type": policy_type,
    }
    
    if policy_id:
        payload["id"] = policy_id
    
    try:
        data = cli.post(f"/api/v1/policy/{s.tenant}", payload).json()
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
        formatter.output([
            {
                "id": data.get("id", ""),
                "name": data.get("name", ""),
                "enabled": data.get("enabled", False),
                "created": data.get("created", ""),
            }
        ], headers=["id", "name", "enabled", "created"])
    else:
        formatter.output(data)


@app.command("add-rule")
def add_rule(
    policy_id: str = typer.Argument(..., help="Policy ID"),
    name: str = typer.Option(..., "--name", help="Rule name"),
    description: str = typer.Option("", "--description", help="Rule description"),
    ruleset: str = typer.Option("default", "--ruleset", help="Rule ruleset"),
    platform: str = typer.Option(None, "--platform", help="Platform(s) as comma-separated list"),
    severity: str = typer.Option("HIGH", "--severity", help="Rule severity"),
    commands: str = typer.Option(None, "--commands", help="Commands as JSON string"),
    device_tags: str = typer.Option(None, "--device-tags", help="Device tags"),
    simplified_text: str = typer.Option(None, "--simplified-text", help="Simplified text match"),
    simplified_regex: bool = typer.Option(False, "--simplified-regex", help="Use regex for simplified matching"),
    simplified_exclude: str = typer.Option(None, "--simplified-exclude", help="Text to exclude in simplified matching"),
    simplified_invert: bool = typer.Option(False, "--simplified-invert", help="Invert simplified matching"),
    definition_code: str = typer.Option(None, "--definition-code", help="Rule definition code"),
    definition_start: int = typer.Option(-1, "--definition-start", help="Definition range start"),
    definition_end: int = typer.Option(-1, "--definition-end", help="Definition range end"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Add or replace a rule in a compliance policy.

    Calls POST /api/v1/policy/{tenant}/{policy}/rule to create or replace a rule.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload - always include basic required fields
    payload = {
        "name": name,
        "description": description,
        "ruleset": ruleset,
        "platform": platform.split(",") if platform else ["cisco_ios"],  # Default to cisco_ios if not specified
        "severity": severity,
        "commands": json.loads(commands) if commands else {},
        "device_tags": device_tags or "",
    }
    
    # Build simplified object if any simplified options provided
    simplified = {}
    if simplified_text:
        simplified["text"] = simplified_text
        simplified["regex"] = simplified_regex
        if simplified_exclude:
            simplified["exclude_text"] = simplified_exclude
        simplified["invert"] = simplified_invert
        payload["simplified"] = simplified
    
    # Build definition object if code provided
    if definition_code:
        payload["definition"] = {
            "code": definition_code,
            "range": {
                "start": definition_start,
                "end": definition_end,
            }
        }
    
    try:
        data = cli.post(f"/api/v1/policy/{s.tenant}/{policy_id}/rule/", payload).json()
    except NotFound:
        typer.echo(f"Policy '{policy_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
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
        formatter.output([
            {"policy_id": policy_id, "rule": name, "status": "added/replaced"}
        ], headers=["policy_id", "rule", "status"])
    else:
        formatter.output(data)


@app.command("remove-rule")
def remove_rule(
    policy_id: str = typer.Argument(..., help="Policy ID"),
    rule_name: str = typer.Argument(..., help="Rule name to remove"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Remove a rule from a compliance policy.

    Calls DELETE /api/v1/policy/{tenant}/{policy}/rule/{rule_name} to remove a rule.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        response = cli.delete(f"/api/v1/policy/{s.tenant}/{policy_id}/rule/{rule_name}")
        
        # Note: API returns 204 for successful deletion regardless of whether 
        # the policy or rule exists (idempotent design)
        
        # Check if the request was successful (204 No Content is success for DELETE)
        if response.status_code >= 400:
            typer.echo(f"API error: HTTP {response.status_code}")
            raise typer.Exit(code=1)
        
        # For successful DELETE (204), no content is returned
        if response.status_code == 204:
            data = "Rule removed successfully"
        else:
            # Try to parse JSON for other success responses
            try:
                data = response.json()
            except ValueError:
                data = response.text.strip() if response.text else "Rule removed successfully"
    except NotFound:
        typer.echo(f"Policy '{policy_id}' or rule '{rule_name}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
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
        formatter.output([
            {"policy_id": policy_id, "rule": rule_name, "status": "removed"}
        ], headers=["policy_id", "rule", "status"])
    else:
        formatter.output(data)


@app.command("test-rule")
def test_rule(
    policy_id: str = typer.Argument(..., help="Policy ID"),
    name: str = typer.Option(..., "--name", help="Rule name"),
    ipaddress: str = typer.Option(..., "--ip", help="Device IP address for testing"),
    configuration: str = typer.Option(..., "--config", help="Device configuration for testing"),
    description: str = typer.Option("", "--description", help="Rule description"),
    ruleset: str = typer.Option("default", "--ruleset", help="Rule ruleset"),
    platform: str = typer.Option(None, "--platform", help="Platform(s) as comma-separated list"),
    severity: str = typer.Option("HIGH", "--severity", help="Rule severity"),
    commands: str = typer.Option(None, "--commands", help="Commands as JSON string"),
    device_tags: str = typer.Option(None, "--device-tags", help="Device tags"),
    simplified_text: str = typer.Option(None, "--simplified-text", help="Simplified text match"),
    simplified_regex: bool = typer.Option(False, "--simplified-regex", help="Use regex for simplified matching"),
    simplified_exclude: str = typer.Option(None, "--simplified-exclude", help="Text to exclude in simplified matching"),
    simplified_invert: bool = typer.Option(False, "--simplified-invert", help="Invert simplified matching"),
    definition_code: str = typer.Option(None, "--definition-code", help="Rule definition code"),
    definition_start: int = typer.Option(-1, "--definition-start", help="Definition range start"),
    definition_end: int = typer.Option(-1, "--definition-end", help="Definition range end"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Test a compliance rule against device configuration.

    Calls POST /api/v1/policy/{tenant}/{policy}/debug to execute a rule test.
    Requires --ip and --config for testing. Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    if not ipaddress:
        typer.echo("Error: --ip (device IP address) is required for testing")
        raise typer.Exit(code=1)
    
    if not configuration:
        typer.echo("Error: --config (device configuration) is required for testing")
        raise typer.Exit(code=1)
    
    # Build payload - always include basic required fields
    payload = {
        "name": name,
        "description": description,
        "ruleset": ruleset,
        "platform": platform.split(",") if platform else ["cisco_ios"],
        "severity": severity,
        "commands": json.loads(commands) if commands else {},
        "device_tags": device_tags or "",
        "ipaddress": ipaddress,
        "configuration": configuration,
    }
    
    # Add simplified object if any simplified options provided
    simplified = {}
    if simplified_text:
        simplified["text"] = simplified_text
        simplified["regex"] = simplified_regex
        if simplified_exclude:
            simplified["exclude_text"] = simplified_exclude
        simplified["invert"] = simplified_invert
        payload["simplified"] = simplified
    
    # Build definition object if code provided
    if definition_code:
        payload["definition"] = {
            "code": definition_code,
            "range": {
                "start": definition_start,
                "end": definition_end,
            }
        }
    
    try:
        data = cli.post(f"/api/v1/policy/{s.tenant}/{policy_id}/debug", payload).json()
    except NotFound:
        typer.echo(f"Policy '{policy_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
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
        result = safe_dict_get(data, "result", {})
        errors = safe_dict_get(data, "errors", [])
        rows = [
            {"section": "result", "key": "outcome", "value": result.get("outcome", "UNKNOWN")},
            {"section": "result", "key": "rule_name", "value": result.get("rule_name", "")},
            {"section": "result", "key": "exec_at", "value": result.get("exec_at", "")},
            {"section": "result", "key": "exec_ns", "value": result.get("exec_ns", 0)},
            {"section": "result", "key": "commit", "value": result.get("commit", "")},
            {"section": "summary", "key": "errors", "value": len(errors)},
        ]
        formatter.output(rows, headers=["section", "key", "value"])
    else:
        formatter.output(data)


@app.command("execute-rules")
def execute_rules(
    devices: str = typer.Option(None, "--devices", help="Device IPs/hostnames as comma-separated list"),
    policies: str = typer.Option(None, "--policies", help="Policy names as comma-separated list"),
    rules: str = typer.Option(None, "--rules", help="Rule names as comma-separated list"),
    tags: str = typer.Option(None, "--tags", help="Device tags as comma-separated list"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Execute compliance rules against devices.

    Calls POST /api/v1/policy/{tenant}/execute-rules to run rules on specified devices.
    Use --devices, --policies, --rules, or --tags to filter execution scope.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload
    payload = {}
    
    if devices:
        payload["devices"] = [d.strip() for d in devices.split(",")]
    
    if policies:
        payload["policies"] = [p.strip() for p in policies.split(",")]
    
    if rules:
        payload["rules"] = [r.strip() for r in rules.split(",")]
    
    if tags:
        payload["tags"] = [t.strip() for t in tags.split(",")]
    
    if not payload:
        typer.echo("Error: At least one of --devices, --policies, --rules, or --tags must be specified")
        raise typer.Exit(code=1)
    
    try:
        response = cli.post(f"/api/v1/policy/{s.tenant}/execute-rules", payload)
        
        # Try to parse JSON, but handle non-JSON responses
        try:
            data = response.json()
        except ValueError:
            data = response.text.strip() if response.text else "Rules executed successfully"
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    formatter = OutputFormatter(format=format, output_file=output_file)
    if isinstance(data, str):
        # wrap string into a dict for non-table formats
        if format in [OutputFormat.TABLE, OutputFormat.CSV]:
            formatter.output([{"result": data}], headers=["result"])
        else:
            formatter.output({"result": data})
    else:
        if format in [OutputFormat.TABLE, OutputFormat.CSV]:
            formatter.output([{"status": "ok"}], headers=["status"])
        else:
            formatter.output(data)
