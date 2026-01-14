import json
import typer
from typing import Optional
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.helpers import extract_items_from_response, format_tags_for_display
from ..utils.cache import get_session_cache

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """
    Show available automation commands when no subcommand is provided.
    """
    if ctx.invoked_subcommand is None:
        typer.echo("Netpicker Automation Commands:")
        typer.echo("")
        typer.echo("Available commands:")
        typer.echo("  list-fixtures    List available automation fixtures")
        typer.echo("  list-jobs        List automation jobs")
        typer.echo("  store-job        Store an automation job")
        typer.echo("  store-job-file   Store an automation job from a file")
        typer.echo("  show-job         Get details of a specific automation job")
        typer.echo("  delete-job       Delete an automation job")
        typer.echo("  test-job         Test an automation job")
        typer.echo("  execute-job      Execute an automation job")
        typer.echo("  logs             Get job log report")
        typer.echo("  show-log         Get details of a specific job log entry")
        typer.echo("  list-queue       List queued jobs")
        typer.echo("  store-queue      Store a queued job")
        typer.echo("  show-queue       Get details of a specific queued job")
        typer.echo("  delete-queue     Delete a queued job")
        typer.echo("  review-queue     Review a queued job (approve or reject)")
        typer.echo("")
        typer.echo("Examples:")
        typer.echo("  netpicker automation list-jobs")
        typer.echo("  netpicker automation execute-job --name my-job")
        typer.echo("  netpicker automation show-job my-job")
        typer.echo("  netpicker automation list-queue")
        typer.echo("")
        typer.echo("Use 'netpicker automation <command> --help' for more information about a specific command.")
        raise typer.Exit()


@app.command("list-fixtures")
def list_fixtures(
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache and fetch fresh data"),
):
    """
    List available automation fixtures.

    Calls GET /api/v1/automation/{tenant}/fixtures to get available fixtures.
    Fixtures are predefined variables that take precedence in job functions.
    Cache is enabled by default (fixtures are static) unless --no-cache is used.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        cache_key = f"fixtures:{s.tenant}"
        
        with get_session_cache(use_cache=not no_cache) as cache:
            data = cache.get(cache_key, lambda: cli.get(f"/api/v1/automation/{s.tenant}/fixtures").json())
    except NotFound:
        typer.echo("No fixtures found for this tenant.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    # When a structured format is requested, use OutputFormatter
    if format != "table" or output_file:
        fixtures = data if isinstance(data, list) else []
        rows = [{"fixture": f} for f in sorted(fixtures)]
        headers = ["fixture"]
        OutputFormatter(format=format, output_file=output_file).output(rows, headers=headers)
        return

    # Default human-readable output
    fixtures = data if isinstance(data, list) else []
    if not fixtures:
        typer.echo("No fixtures available.")
        return
    
    typer.echo("Available fixtures:")
    for fixture in sorted(fixtures):
        typer.echo(f"  - {fixture}")


@app.command("list-jobs")
def list_jobs(
    pattern: str = typer.Option(None, "--pattern", help="Filter jobs by name pattern"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache and fetch fresh data"),
):
    """
    List automation jobs.

    Calls GET /api/v1/automation/{tenant}/job to get available jobs.
    Use --pattern to filter jobs by name. 
    Cache is enabled by default (jobs are mostly static) unless --no-cache is used.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build URL with optional pattern parameter
    url = f"/api/v1/automation/{s.tenant}/job"
    # When pattern is provided, don't use cache (we're filtering)
    use_cache = not no_cache and pattern is None
    cache_key = f"jobs:{s.tenant}"
    
    try:
        if use_cache:
            with get_session_cache(use_cache=True) as cache:
                data = cache.get(cache_key, lambda: cli.get(url).json())
        else:
            # Pattern provided or no-cache requested, fetch fresh
            if pattern:
                url += f"?pattern={pattern}"
            data = cli.get(url).json()
    except NotFound:
        typer.echo("No jobs found for this tenant.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    # Structured formats via OutputFormatter
    if format != "table" or output_file:
        jobs = data if isinstance(data, list) else []
        rows = [
            {
                "name": job.get("name", ""),
                "platforms": ", ".join(job.get("platforms", []) or []),
                "variables": ", ".join(job.get("variables", []) or []),
                "simple": "Yes" if job.get("is_simple") else "No",
            }
            for job in jobs
        ]
        headers = ["name", "platforms", "variables", "simple"]
        OutputFormatter(format=format, output_file=output_file).output(rows, headers=headers)
        return

    # Default human-readable output
    jobs = data if isinstance(data, list) else []
    if not jobs:
        typer.echo("No jobs found.")
        return
    
    typer.echo("Available jobs:")
    for job in jobs:
        name = job.get("name", "")
        platforms = ", ".join(job.get("platforms", []))
        variables = ", ".join(job.get("variables", []))
        is_simple = "Yes" if job.get("is_simple") else "No"
        
        typer.echo(f"  {name}:")
        typer.echo(f"    Platforms: {platforms}")
        typer.echo(f"    Variables: {variables}")
        typer.echo(f"    Simple: {is_simple}")
        typer.echo(f"    Simple: {is_simple}")
        typer.echo()


@app.command("store-job")
def store_job(
    name: str = typer.Option(..., "--name", help="Job name"),
    sources: str = typer.Option(..., "--sources", help="Source files as 'filename:content' pairs, separated by semicolons"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Store an automation job.

    Calls POST /api/v1/automation/{tenant}/job to store a job definition.
    Use --sources to specify source files as 'filename:content' pairs separated by semicolons.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Parse sources
    sources_dict = {}
    if sources:
        try:
            # Parse format: "file1.py:content1;file2.py:content2"
            for source_pair in sources.split(";"):
                if ":" not in source_pair:
                    typer.echo(f"Invalid source format: {source_pair}. Use 'filename:content'")
                    raise typer.Exit(code=1)
                filename, content = source_pair.split(":", 1)
                sources_dict[filename.strip()] = content.strip()
        except Exception as e:
            typer.echo(f"Error parsing sources: {e}")
            raise typer.Exit(code=1)
    
    if not sources_dict:
        typer.echo("Error: At least one source file must be provided")
        raise typer.Exit(code=1)
    
    # Build payload
    payload = {
        "name": name,
        "sources": sources_dict,
    }
    
    try:
        data = cli.post(f"/api/v1/automation/{s.tenant}/job", payload).json()
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
    else:
        typer.echo(f"✓ Job '{data.get('name', name)}' stored successfully")
        sources_count = len(data.get("sources", {}))
        typer.echo(f"  Sources: {sources_count} file(s)")


@app.command("store-job-file")
def store_job_file(
    name: str = typer.Option(..., "--name", help="Job name"),
    file_path: str = typer.Option(..., "--file", help="Path to source file"),
    file_name: str = typer.Option(None, "--filename", help="Filename to use in sources (defaults to basename)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Store an automation job from a file.

    Calls POST /api/v1/automation/{tenant}/job to store a job definition from a file.
    Use --file to specify the source file path.
    Use --json to see the raw response.
    """
    import os
    
    s = load_settings()
    cli = ApiClient(s)
    
    # Read file content
    if not os.path.exists(file_path):
        typer.echo(f"File not found: {file_path}")
        raise typer.Exit(code=1)
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
    except Exception as e:
        typer.echo(f"Error reading file: {e}")
        raise typer.Exit(code=1)
    
    # Determine filename
    if not file_name:
        file_name = os.path.basename(file_path)
    
    # Build payload
    payload = {
        "name": name,
        "sources": {
            file_name: content
        },
    }
    
    try:
        data = cli.post(f"/api/v1/automation/{s.tenant}/job", payload).json()
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
    else:
        typer.echo(f"✓ Job '{data.get('name', name)}' stored successfully")
        typer.echo(f"  File: {file_name}")


@app.command("show-job")
def show_job(
    name: str = typer.Argument(..., help="Job name"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get details of a specific automation job.

    Calls GET /api/v1/automation/{tenant}/job/{name} to get job details and source code.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        data = cli.get(f"/api/v1/automation/{s.tenant}/job/{name}").json()
    except NotFound:
        typer.echo(f"Job '{name}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        # For structured formats, output the raw response
        OutputFormatter(format=format, output_file=output_file).output(data)
        return

    # Display job information
    jobs = data.get("jobs", [])
    sources = data.get("sources", {})
    
    if not jobs:
        typer.echo("No job details found.")
        return
    
    # Display each job (usually just one)
    for job in jobs:
        typer.echo(f"Job: {job.get('name', '')}")
        typer.echo(f"ID: {job.get('id', '')}")
        typer.echo(f"Platforms: {', '.join(job.get('platforms', []))}")
        typer.echo(f"Simple: {job.get('is_simple', False)}")
        
        # Display signature
        signature = job.get("signature", {})
        params = signature.get("params", [])
        if params:
            typer.echo("Parameters:")
            for param in params:
                param_type = param.get("annotated", {}).get("annotation", "unknown")
                if param_type.startswith("builtins."):
                    param_type = param_type.replace("builtins.", "")
                elif param_type == "inspect._empty":
                    param_type = "any"
                
                default_info = " (optional)" if param.get("has_default") else ""
                typer.echo(f"  - {param.get('name', '')}: {param_type}{default_info}")
        
        # Display range
        range_info = job.get("range", {})
        if range_info:
            typer.echo(f"Code Range: lines {range_info.get('start', 0)} - {range_info.get('end', 0)}")
        
        typer.echo()
    
    # Display sources
    if sources:
        typer.echo("Source Files:")
        for filename, content in sources.items():
            typer.echo(f"  {filename}:")
            # Show first few lines of content
            lines = content.split('\n')[:10]  # Show first 10 lines
            for i, line in enumerate(lines, 1):
                typer.echo(f"    {i:2d}: {line}")
            if len(content.split('\n')) > 10:
                line_count = len(content.splitlines()) - 10
                typer.echo(f"    ... ({line_count} more lines)")
            typer.echo()


@app.command("delete-job")
def delete_job(
    name: str = typer.Argument(..., help="Job name to delete"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Delete an automation job.

    Calls DELETE /api/v1/automation/{tenant}/job/{name} to delete a job.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        response = cli.delete(f"/api/v1/automation/{s.tenant}/job/{name}")
        
        # Check if the request was successful (204 No Content is success for DELETE)
        if response.status_code >= 400:
            typer.echo(f"API error: HTTP {response.status_code}")
            raise typer.Exit(code=1)
        
        # For successful DELETE (204), no content is returned
        if response.status_code == 204:
            data = "Job deleted successfully"
        else:
            # Try to parse JSON for other success responses
            try:
                data = response.json()
            except ValueError:
                data = response.text.strip() if response.text else "Job deleted successfully"
    except NotFound:
        typer.echo(f"Job '{name}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"

    if format != "table" or output_file:
        payload = data if not isinstance(data, str) else {"message": data}
        OutputFormatter(format=format, output_file=output_file).output(payload)
    else:
        if isinstance(data, str):
            typer.echo(f"✓ {data}")
        else:
            typer.echo("✓ Job deleted successfully")


@app.command("test-job")
def test_job(
    name: str = typer.Option(..., "--name", help="Job name"),
    sources: str = typer.Option(None, help="Source files as 'filename:content' pairs, separated by semicolons"),
    variables: str = typer.Option(None, help="Variables as 'key:value' pairs, separated by semicolons"),
    tags: str = typer.Option(None, help="Tags as comma-separated list"),
    ipaddress: str = typer.Option(None, help="Target device IP address"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Test an automation job.

    Calls POST /api/v1/automation/{tenant}/debug to execute a job test.
    Provide job sources, variables, and target device for testing.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload
    payload = {"name": name}
    
    # Parse sources if provided
    if sources:
        sources_dict = {}
        try:
            for source_pair in sources.split(";"):
                if ":" not in source_pair:
                    typer.echo(f"Invalid source format: {source_pair}. Use 'filename:content'")
                    raise typer.Exit(code=1)
                filename, content = source_pair.split(":", 1)
                sources_dict[filename.strip()] = content.strip()
            payload["sources"] = sources_dict
        except Exception as e:
            typer.echo(f"Error parsing sources: {e}")
            raise typer.Exit(code=1)
    
    # Parse variables if provided
    if variables:
        variables_dict = {}
        try:
            for var_pair in variables.split(";"):
                if ":" not in var_pair:
                    typer.echo(f"Invalid variable format: {var_pair}. Use 'key:value'")
                    raise typer.Exit(code=1)
                key, value = var_pair.split(":", 1)
                # Try to parse as JSON, otherwise keep as string
                try:
                    variables_dict[key.strip()] = json.loads(value.strip())
                except json.JSONDecodeError:
                    variables_dict[key.strip()] = value.strip()
            payload["variables"] = variables_dict
        except Exception as e:
            typer.echo(f"Error parsing variables: {e}")
            raise typer.Exit(code=1)
    
    # Add tags if provided
    if tags:
        payload["tags"] = [tag.strip() for tag in tags.split(",")]
    
    # Add ipaddress if provided
    if ipaddress:
        payload["ipaddress"] = ipaddress
    
    try:
        data = cli.post(f"/api/v1/automation/{s.tenant}/debug", payload).json()
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
        return

    # Display test results
    typer.echo(f"Job Test Results for '{name}':")
    typer.echo(f"Node ID: {data.get('nodeid', '')}")
    typer.echo(f"Status: {data.get('status', 'UNKNOWN')}")
    typer.echo(f"Executed At: {data.get('exec_at', '')}")
    typer.echo(f"Execution Time: {data.get('exec_ns', 0)} ns")
    
    if 'return_value' in data:
        typer.echo(f"Return Value: {data.get('return_value')}")
    
    # Display logs if present
    logs = data.get("logs", "")
    if logs:
        typer.echo("\nExecution Logs:")
        typer.echo("-" * 80)
        typer.echo(logs)
        typer.echo("-" * 80)


@app.command("execute-job")
def execute_job(
    name: str = typer.Option(..., "--name", help="Job name"),
    sources: str = typer.Option(None, help="Source files as 'filename:content' pairs, separated by semicolons"),
    variables: str = typer.Option(None, help="Variables as 'key:value' pairs, separated by semicolons"),
    tags: str = typer.Option(None, help="Tags as comma-separated list"),
    devices: str = typer.Option(None, help="Devices as comma-separated list"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Execute an automation job.

    Calls POST /api/v1/automation/{tenant}/execute to run a job on target devices.
    Provide job sources, variables, and target devices/tags for execution.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload
    payload = {"name": name}
    
    # Parse sources if provided
    if sources:
        sources_dict = {}
        try:
            for source_pair in sources.split(";"):
                if ":" not in source_pair:
                    typer.echo(f"Invalid source format: {source_pair}. Use 'filename:content'")
                    raise typer.Exit(code=1)
                filename, content = source_pair.split(":", 1)
                sources_dict[filename.strip()] = content.strip()
            payload["sources"] = sources_dict
        except Exception as e:
            typer.echo(f"Error parsing sources: {e}")
            raise typer.Exit(code=1)
    
    # Parse variables if provided
    if variables:
        variables_dict = {}
        try:
            for var_pair in variables.split(";"):
                if ":" not in var_pair:
                    typer.echo(f"Invalid variable format: {var_pair}. Use 'key:value'")
                    raise typer.Exit(code=1)
                key, value = var_pair.split(":", 1)
                # Try to parse as JSON, otherwise keep as string
                try:
                    variables_dict[key.strip()] = json.loads(value.strip())
                except json.JSONDecodeError:
                    variables_dict[key.strip()] = value.strip()
            payload["variables"] = variables_dict
        except Exception as e:
            typer.echo(f"Error parsing variables: {e}")
            raise typer.Exit(code=1)
    
    # Add tags if provided
    if tags:
        payload["tags"] = [tag.strip() for tag in tags.split(",")]
    
    # Add devices if provided
    if devices:
        payload["devices"] = [device.strip() for device in devices.split(",")]
    
    try:
        response = cli.post(f"/api/v1/automation/{s.tenant}/execute", payload)
        
        # Try to parse JSON, but handle string responses
        try:
            data = response.json()
        except ValueError:
            data = response.text.strip() if response.text else "Job executed successfully"
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        payload = data if not isinstance(data, str) else {"message": data}
        OutputFormatter(format=format, output_file=output_file).output(payload)
    else:
        if isinstance(data, str):
            typer.echo(f"✓ {data}")
        else:
            typer.echo("✓ Job executed successfully")


@app.command("logs")
def logs(
    job_name: str = typer.Option(None, "--job-name", help="Filter by job name"),
    ipaddress: str = typer.Option(None, "--ipaddress", help="Filter by IP address"),
    exec_at: str = typer.Option(None, "--exec-at", help="Filter by execution time as 'operator:value' pairs, comma-separated"),
    created: str = typer.Option(None, "--created", help="Filter by creation time as 'operator:value' pairs, comma-separated"),
    initiator: str = typer.Option(None, "--initiator", help="Filter by initiator"),
    status: str = typer.Option(None, "--status", help="Filter by status"),
    ordering: str = typer.Option(None, "--ordering", help="Ordering fields as comma-separated list"),
    page: int = typer.Option(1, "--page", help="Page number (default: 1)"),
    size: int = typer.Option(50, "--size", help="Page size (default: 50, max: 1000)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get job log report.

    Calls GET /api/v1/automation/{tenant}/logs to get job execution logs.
    Use various filters to narrow down the results. Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build query parameters
    params = {}
    if job_name:
        params["job_name"] = job_name
    if ipaddress:
        params["ipaddress"] = ipaddress
    if initiator:
        params["initiator"] = initiator
    if status:
        params["status"] = status
    if page != 1:
        params["page"] = page
    if size != 50:
        params["size"] = size
    
    # Parse exec_at filter
    if exec_at:
        try:
            exec_at_list = []
            for pair in exec_at.split(","):
                if ":" not in pair:
                    typer.echo(f"Invalid exec_at format: {pair}. Use 'operator:value'")
                    raise typer.Exit(code=1)
                op, val = pair.split(":", 1)
                exec_at_list.append([op.strip(), val.strip()])
            params["exec_at"] = exec_at_list
        except Exception as e:
            typer.echo(f"Error parsing exec_at: {e}")
            raise typer.Exit(code=1)
    
    # Parse created filter
    if created:
        try:
            created_list = []
            for pair in created.split(","):
                if ":" not in pair:
                    typer.echo(f"Invalid created format: {pair}. Use 'operator:value'")
                    raise typer.Exit(code=1)
                op, val = pair.split(":", 1)
                created_list.append([op.strip(), val.strip()])
            params["created"] = created_list
        except Exception as e:
            typer.echo(f"Error parsing created: {e}")
            raise typer.Exit(code=1)
    
    # Parse ordering
    if ordering:
        params["ordering"] = [field.strip() for field in ordering.split(",")]
    
    # Build URL with query parameters
    url = f"/api/v1/automation/{s.tenant}/logs"
    if params:
        from urllib.parse import urlencode
        query_string = urlencode(params, doseq=True)  # doseq=True for arrays
        url += f"?{query_string}"
    
    try:
        response = cli.get(url)
        data = response.json()
    except NotFound:
        typer.echo("No logs found for this tenant.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        items = extract_items_from_response(data)
        rows = [
            {
                "id": it.get("id", ""),
                "job": it.get("job_name", ""),
                "ip": it.get("ipaddress", ""),
                "status": it.get("status", ""),
                "exec_at": it.get("exec_at", ""),
                "created": it.get("created", ""),
                "exec_ns": it.get("exec_ns", 0),
            }
            for it in items
        ]
        headers = ["id", "job", "ip", "status", "exec_at", "created", "exec_ns"]
        OutputFormatter(format=format, output_file=output_file).output(rows, headers=headers)
        return

    # Default human-readable output
    items = data.get("items", [])
    total = data.get("total", 0)
    page_num = data.get("page", 1)
    page_size = data.get("size", 50)
    pages = data.get("pages", 0)
    
    if not items:
        typer.echo("No logs found.")
        return
    
    typer.echo(f"Job Logs (Page {page_num}/{pages}, Total: {total}):")
    typer.echo()
    
    for item in items:
        typer.echo(f"ID: {item.get('id', '')}")
        typer.echo(f"Job: {item.get('job_name', '')} (ID: {item.get('job_id', '')})")
        typer.echo(f"Initiator: {item.get('initiator', '')}")
        typer.echo(f"IP Address: {item.get('ipaddress', '')}")
        typer.echo(f"Status: {item.get('status', '')}")
        typer.echo(f"Executed At: {item.get('exec_at', '')}")
        typer.echo(f"Created: {item.get('created', '')}")
        typer.echo(f"Execution Time: {item.get('exec_ns', 0)} ns")
        
        # Display variables if any
        variables = item.get('variables', {})
        if variables:
            typer.echo("Variables:")
            for key, value in variables.items():
                typer.echo(f"  {key}: {value}")
        
        # Display return value if any
        return_value = item.get('return_value', [])
        if return_value:
            typer.echo("Return Value:")
            for rv in return_value:
                typer.echo(f"  {rv}")
        
        # Display log
        log = item.get('log', '')
        if log:
            typer.echo("Log:")
            # Show first few lines
            lines = log.split('\n')[:10]
            for line in lines:
                typer.echo(f"  {line}")
            if len(log.split('\n')) > 10:
                line_count = len(content.splitlines()) - 10
                typer.echo(f"    ... ({line_count} more lines)")
        typer.echo("-" * 50)


@app.command("show-log")
def show_log(
    log_id: str = typer.Argument(..., help="Log entry ID to retrieve"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get details of a specific job log entry.

    Calls GET /api/v1/automation/{tenant}/logs/{id} to get a specific log entry.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        response = cli.get(f"/api/v1/automation/{s.tenant}/logs/{log_id}")
        data = response.json()
    except NotFound:
        typer.echo(f"Log entry '{log_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
        return

    # Display log details
    typer.echo(f"Log Entry: {data.get('id', '')}")
    typer.echo(f"Job: {data.get('job_name', '')} (ID: {data.get('job_id', '')})")
    typer.echo(f"Initiator: {data.get('initiator', '')}")
    typer.echo(f"IP Address: {data.get('ipaddress', '')}")
    typer.echo(f"Status: {data.get('status', '')}")
    typer.echo(f"Executed At: {data.get('exec_at', '')}")
    typer.echo(f"Created: {data.get('created', '')}")
    typer.echo(f"Execution Time: {data.get('exec_ns', 0)} ns")
    
    # Display variables if any
    variables = data.get('variables', {})
    if variables:
        typer.echo("Variables:")
        for key, value in variables.items():
            typer.echo(f"  {key}: {value}")
    
    # Display return value if any
    return_value = data.get('return_value', [])
    if return_value:
        typer.echo("Return Value:")
        for rv in return_value:
            typer.echo(f"  {rv}")
    
    # Display log
    log = data.get('log', '')
    if log:
        typer.echo("Log:")
        for line in log.split('\n'):
            typer.echo(f"  {line}")


@app.command("list-queue")
def list_queue(
    name: str = typer.Option(None, "--name", help="Filter by job name"),
    devices: str = typer.Option(None, "--devices", help="Filter by devices as comma-separated list"),
    tags: str = typer.Option(None, "--tags", help="Filter by tags as comma-separated list"),
    status: str = typer.Option(None, "--status", help="Filter by status"),
    submitted: str = typer.Option(None, "--submitted", help="Filter by submitted date-time"),
    submitter: str = typer.Option(None, "--submitter", help="Filter by submitter"),
    reviewed: str = typer.Option(None, "--reviewed", help="Filter by reviewed date-time"),
    reviewer: str = typer.Option(None, "--reviewer", help="Filter by reviewer"),
    ordering: str = typer.Option(None, "--ordering", help="Ordering fields as comma-separated list"),
    page: int = typer.Option(1, "--page", help="Page number (default: 1)"),
    size: int = typer.Option(50, "--size", help="Page size (default: 50, max: 1000)"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    List queued jobs.

    Calls GET /api/v1/automation/{tenant}/queue to get queued jobs.
    Use various filters to narrow down the results. Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build query parameters
    params = {}
    if name:
        params["name"] = name
    if status:
        params["status"] = status
    if submitted:
        params["submitted"] = submitted
    if submitter:
        params["submitter"] = submitter
    if reviewed:
        params["reviewed"] = reviewed
    if reviewer:
        params["reviewer"] = reviewer
    if page != 1:
        params["page"] = page
    if size != 50:
        params["size"] = size
    
    # Parse devices
    if devices:
        params["devices"] = [device.strip() for device in devices.split(",")]
    
    # Parse tags
    if tags:
        params["tags"] = [tag.strip() for tag in tags.split(",")]
    
    # Parse ordering
    if ordering:
        params["ordering"] = [field.strip() for field in ordering.split(",")]
    
    # Build URL with query parameters
    url = f"/api/v1/automation/{s.tenant}/queue"
    if params:
        from urllib.parse import urlencode
        query_string = urlencode(params, doseq=True)  # doseq=True for arrays
        url += f"?{query_string}"
    
    try:
        response = cli.get(url)
        data = response.json()
    except NotFound:
        typer.echo("No queued jobs found for this tenant.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        items = extract_items_from_response(data)
        rows = [
            {
                "id": it.get("id", ""),
                "job": it.get("job_name", ""),
                "branch": it.get("branch", ""),
                "submitter": it.get("submitter", ""),
                "submitted": it.get("submitted", ""),
                "status": it.get("status", ""),
                "tags": format_tags_for_display(it.get("tags")),
                "devices": ", ".join(it.get("devices", []) or []),
            }
            for it in items
        ]
        headers = ["id", "job", "branch", "submitter", "submitted", "status", "tags", "devices"]
        OutputFormatter(format=format, output_file=output_file).output(rows, headers=headers)
        return

    # Default human-readable output
    items = data.get("items", [])
    total = data.get("total", 0)
    page_num = data.get("page", 1)
    page_size = data.get("size", 50)
    pages = data.get("pages", 0)
    
    if not items:
        typer.echo("No queued jobs found.")
        return
    
    typer.echo(f"Queued Jobs (Page {page_num}/{pages}, Total: {total}):")
    typer.echo()
    
    for item in items:
        typer.echo(f"ID: {item.get('id', '')}")
        typer.echo(f"Job: {item.get('job_name', '')} (ID: {item.get('job_id', '')})")
        typer.echo(f"Branch: {item.get('branch', '')}")
        typer.echo(f"Submitter: {item.get('submitter', '')}")
        typer.echo(f"Submitted: {item.get('submitted', '')}")
        typer.echo(f"Reviewer: {item.get('reviewer', '')}")
        typer.echo(f"Reviewed: {item.get('reviewed', '')}")
        typer.echo(f"Expires: {item.get('expires', '')}")
        typer.echo(f"Status: {item.get('status', '')}")
        
        # Display devices
        devices_list = item.get('devices', [])
        if devices_list:
            typer.echo(f"Devices: {', '.join(devices_list)}")
        
        # Display tags
        tags_list = item.get('tags', [])
        if tags_list:
            typer.echo(f"Tags: {', '.join(tags_list)}")
        
        # Display variables if any
        variables = item.get('variables', {})
        if variables:
            typer.echo("Variables:")
            for key, value in variables.items():
                typer.echo(f"  {key}: {value}")
        
        # Display execron (cron schedule)
        execron = item.get('execron', {})
        if execron:
            typer.echo("Schedule:")
            typer.echo(f"  Minute: {execron.get('minute', '*')}")
            typer.echo(f"  Hour: {execron.get('hour', '*')}")
            typer.echo(f"  Day of Week: {execron.get('day_of_week', '*')}")
            typer.echo(f"  Day of Month: {execron.get('day_of_month', '*')}")
            typer.echo(f"  Month of Year: {execron.get('month_of_year', '*')}")
            typer.echo(f"  Timezone: {execron.get('timezone', '')}")
        
        typer.echo("-" * 50)


@app.command("store-queue")
def store_queue(
    name: str = typer.Option(..., "--name", help="Job name"),
    branch: str = typer.Option("main", "--branch", help="Branch name (default: main)"),
    sources: str = typer.Option(..., "--sources", help="Source files as 'filename:content' pairs, separated by semicolons"),
    variables: str = typer.Option(None, help="Variables as 'key:value' pairs, separated by semicolons"),
    devices: str = typer.Option(None, help="Devices as comma-separated list"),
    tags: str = typer.Option(None, help="Tags as comma-separated list"),
    execron_minute: str = typer.Option("*", "--execron-minute", help="Cron minute pattern (default: *)"),
    execron_hour: str = typer.Option("*", "--execron-hour", help="Cron hour pattern (default: *)"),
    execron_day_of_week: str = typer.Option("*", "--execron-day-of-week", help="Cron day of week pattern (default: *)"),
    execron_day_of_month: str = typer.Option("*", "--execron-day-of-month", help="Cron day of month pattern (default: *)"),
    execron_month_of_year: str = typer.Option("*", "--execron-month-of-year", help="Cron month of year pattern (default: *)"),
    execron_timezone: str = typer.Option("UTC", "--execron-timezone", help="Cron timezone (default: UTC)"),
    expires: str = typer.Option(None, help="Expiration date-time (ISO format)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force operation"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Store a queued job.

    Calls POST /api/v1/automation/{tenant}/queue to queue a job for approval.
    Provide job sources, variables, devices, and schedule information.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Build payload
    payload = {
        "name": name,
        "branch": branch,
    }
    
    # Parse sources
    sources_dict = {}
    if sources:
        try:
            for source_pair in sources.split(";"):
                if ":" not in source_pair:
                    typer.echo(f"Invalid source format: {source_pair}. Use 'filename:content'")
                    raise typer.Exit(code=1)
                filename, content = source_pair.split(":", 1)
                sources_dict[filename.strip()] = content.strip()
        except Exception as e:
            typer.echo(f"Error parsing sources: {e}")
            raise typer.Exit(code=1)
    
    if sources_dict:
        payload["sources"] = sources_dict
    
    # Parse variables if provided
    if variables:
        variables_dict = {}
        try:
            for var_pair in variables.split(";"):
                if ":" not in var_pair:
                    typer.echo(f"Invalid variable format: {var_pair}. Use 'key:value'")
                    raise typer.Exit(code=1)
                key, value = var_pair.split(":", 1)
                # Try to parse as JSON, otherwise keep as string
                try:
                    variables_dict[key.strip()] = json.loads(value.strip())
                except json.JSONDecodeError:
                    variables_dict[key.strip()] = value.strip()
            payload["variables"] = variables_dict
        except Exception as e:
            typer.echo(f"Error parsing variables: {e}")
            raise typer.Exit(code=1)
    
    # Add devices if provided
    if devices:
        payload["devices"] = [device.strip() for device in devices.split(",")]
    
    # Add tags if provided
    if tags:
        payload["tags"] = [tag.strip() for tag in tags.split(",")]
    
    # Add execron (cron schedule)
    payload["execron"] = {
        "minute": execron_minute,
        "hour": execron_hour,
        "day_of_week": execron_day_of_week,
        "day_of_month": execron_day_of_month,
        "month_of_year": execron_month_of_year,
        "timezone": execron_timezone,
    }
    
    # Add expires if provided
    if expires:
        payload["expires"] = expires
    
    # Build query parameters
    params = {}
    if force:
        params["f"] = "true"
    
    # Build URL with query parameters
    url = f"/api/v1/automation/{s.tenant}/queue"
    if params:
        from urllib.parse import urlencode
        query_string = urlencode(params)
        url += f"?{query_string}"
    
    try:
        response = cli.post(url, payload)
        data = response.json()
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
    else:
        typer.echo("✓ Job queued successfully")
        typer.echo(f"Queue ID: {data.get('id', '')}")
        typer.echo(f"Status: {data.get('status', '')}")
        if data.get('expires'):
            typer.echo(f"Expires: {data.get('expires', '')}")


@app.command("show-queue")
def show_queue(
    queue_id: str = typer.Argument(..., help="Queue entry ID to retrieve"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Get details of a specific queued job.

    Calls GET /api/v1/automation/{tenant}/queue/{id} to get a specific queued job.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        response = cli.get(f"/api/v1/automation/{s.tenant}/queue/{queue_id}")
        data = response.json()
    except NotFound:
        typer.echo(f"Queued job '{queue_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
        return

    # Display queued job details
    typer.echo(f"Queued Job: {data.get('id', '')}")
    typer.echo(f"Job: {data.get('job_name', '')} (ID: {data.get('job_id', '')})")
    typer.echo(f"Branch: {data.get('branch', '')}")
    typer.echo(f"Submitter: {data.get('submitter', '')}")
    typer.echo(f"Submitted: {data.get('submitted', '')}")
    typer.echo(f"Reviewer: {data.get('reviewer', '')}")
    typer.echo(f"Reviewed: {data.get('reviewed', '')}")
    typer.echo(f"Expires: {data.get('expires', '')}")
    typer.echo(f"Status: {data.get('status', '')}")
    
    # Display devices
    devices_list = data.get('devices', [])
    if devices_list:
        typer.echo(f"Devices: {', '.join(devices_list)}")
    
    # Display tags
    tags_list = data.get('tags', [])
    if tags_list:
        typer.echo(f"Tags: {', '.join(tags_list)}")
    
    # Display variables if any
    variables = data.get('variables', {})
    if variables:
        typer.echo("Variables:")
        for key, value in variables.items():
            typer.echo(f"  {key}: {value}")
    
    # Display execron (cron schedule)
    execron = data.get('execron', {})
    if execron:
        typer.echo("Schedule:")
        typer.echo(f"  Minute: {execron.get('minute', '*')}")
        typer.echo(f"  Hour: {execron.get('hour', '*')}")
        typer.echo(f"  Day of Week: {execron.get('day_of_week', '*')}")
        typer.echo(f"  Day of Month: {execron.get('day_of_month', '*')}")
        typer.echo(f"  Month of Year: {execron.get('month_of_year', '*')}")
        typer.echo(f"  Timezone: {execron.get('timezone', '')}")
    
    # Display sources
    sources = data.get('sources', {})
    if sources:
        typer.echo("Source Files:")
        for filename, content in sources.items():
            typer.echo(f"  {filename}:")
            # Show first few lines of content
            lines = content.split('\n')[:10]  # Show first 10 lines
            for i, line in enumerate(lines, 1):
                typer.echo(f"    {i:2d}: {line}")
            if len(content.split('\n')) > 10:
                line_count = len(content.splitlines()) - 10
                typer.echo(f"    ... ({line_count} more lines)")
            typer.echo()


@app.command("delete-queue")
def delete_queue(
    queue_id: str = typer.Argument(..., help="Queue entry ID to delete"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Delete a queued job.

    Calls DELETE /api/v1/automation/{tenant}/queue/{id} to delete a queued job.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    try:
        response = cli.delete(f"/api/v1/automation/{s.tenant}/queue/{queue_id}")
        
        # Check if the request was successful (204 No Content is success for DELETE)
        if response.status_code >= 400:
            typer.echo(f"API error: HTTP {response.status_code}")
            raise typer.Exit(code=1)
        
        # For successful DELETE (204), no content is returned
        if response.status_code == 204:
            data = "Queued job deleted successfully"
        else:
            # Try to parse JSON for other success responses
            try:
                data = response.json()
            except ValueError:
                data = response.text.strip() if response.text else "Queued job deleted successfully"
    except NotFound:
        typer.echo(f"Queued job '{queue_id}' not found for tenant '{s.tenant}'.")
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        payload = data if not isinstance(data, str) else {"message": data}
        OutputFormatter(format=format, output_file=output_file).output(payload)
    else:
        if isinstance(data, str):
            typer.echo(f"✓ {data}")
        else:
            typer.echo("✓ Queued job deleted successfully")


@app.command("review-queue")
def review_queue(
    queue_id: str = typer.Argument(..., help="Queue entry ID to review"),
    approved: str = typer.Option(..., "--approved", help="Whether to approve ('true') or reject ('false') the queued job"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Review a queued job (approve or reject).

    Calls POST /api/v1/automation/{tenant}/queue/{id}/review to approve or reject a queued job.
    Use --approved=true to approve or --approved=false to reject.
    Use --json to see the raw response.
    """
    s = load_settings()
    cli = ApiClient(s)
    
    # Parse approved parameter
    if approved.lower() not in ["true", "false"]:
        typer.echo("Error: --approved must be 'true' or 'false'")
        raise typer.Exit(code=1)
    
    approved_bool = approved.lower() == "true"
    
    # Build URL with query parameters
    url = f"/api/v1/automation/{s.tenant}/queue/{queue_id}/review"
    url += f"?approved={str(approved_bool).lower()}"
    
    try:
        response = cli.post(url)
        data = response.json()
    except ApiError as e:
        typer.echo(f"API error: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Unexpected error: {e}")
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
    else:
        action = "approved" if approved_bool else "rejected"
        typer.echo(f"✓ Queued job {action} successfully")
        typer.echo(f"Queue ID: {data.get('id', '')}")
        typer.echo(f"Status: {data.get('status', '')}")
        if data.get('reviewer'):
            typer.echo(f"Reviewer: {data.get('reviewer', '')}")
        if data.get('reviewed'):
            typer.echo(f"Reviewed: {data.get('reviewed', '')}")