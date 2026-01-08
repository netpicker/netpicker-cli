"""
AI command for Netpicker CLI

Provides AI-powered natural language querying and AI service management.
"""

import typer
from typing import Optional, Dict, Any, List
import asyncio
import subprocess
import os
import re
from netpicker_cli.ai import router as ai_router
from netpicker_cli.mcp.server import mcp
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.helpers import extract_ip_from_text, extract_number_from_text, extract_tag_from_text

def run_netpicker_command(args: List[str]) -> Dict[str, Any]:
    """
    Run a Netpicker CLI command and return the result.
    Similar to the function in MCP server.
    
    Args:
        args: Command arguments to pass to netpicker CLI
        
    Returns:
        Dictionary with stdout, stderr, returncode, and success status
    """
    try:
        # Set environment variables for Netpicker
        env = os.environ.copy()

        # Run the netpicker command using the installed CLI
        cmd = ["netpicker"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=30  # 30 second timeout
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Command timed out after 30 seconds",
            "returncode": -1,
            "success": False
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error running command: {str(e)}",
            "returncode": -1,
            "success": False
        }

def extract_parameters(query: str) -> Dict[str, Any]:
    """
    Extract parameters from natural language queries.

    Args:
        query: Natural language query

    Returns:
        Dictionary of extracted parameters
    """
    params = {}

    # Extract limit numbers (e.g., "list 5 devices", "show top 10", "any 2 devices")
    limit_patterns = [
        r'\b(\d+)\s+devices?\b',  # "5 devices"
        r'\bany\s+(\d+)\b',       # "any 2"
        r'\btop\s+(\d+)\b',       # "top 10"
        r'\bfirst\s+(\d+)\b',     # "first 3"
        r'\blast\s+(\d+)\b',      # "last 5"
        r'\blimit\s+(\d+)\b',     # "limit 2"
    ]
    
    limit = extract_number_from_text(query, limit_patterns)
    if limit:
        params['limit'] = limit

    # Extract IP addresses for device-specific queries
    ip = extract_ip_from_text(query)
    if ip:
        params['ip'] = ip

    # Extract tags (more flexible patterns)
    tag_patterns = [
        r'\btag\s+([a-z0-9_-]+)\b',         # "tag foo", "tag test-1"
        r'\bwith\s+tag\s+([a-z0-9_-]+)\b',  # "with tag foo"
        r'\bfor\s+tag\s+([a-z0-9_-]+)\b',   # "for tag foo"
    ]
    
    tag = extract_tag_from_text(query, tag_patterns)
    if tag:
        params['tag'] = tag

    return params

def fetch_latest_backup(ip: str) -> str:
    """
    Fetch the latest backup configuration for a device.
    
    This is a two-step process:
    1. Get the list of backups to find the latest ID
    2. Fetch the configuration using that ID
    
    Args:
        ip: Device IP address
        
    Returns:
        The configuration content or an error message
    """
    try:
        # Step 1: Get the latest backup ID
        result = run_netpicker_command(["backups", "list", "--ip", ip, "--json"])
        if not result["success"]:
            return f"Error getting backup list: {result['stderr']}"
        
        # Parse JSON output to get the latest ID
        import json
        try:
            data = json.loads(result["stdout"])
            # The response is usually a list of backup entries
            if isinstance(data, list) and len(data) > 0:
                latest_id = data[0].get("id")
                if not latest_id:
                    return "Could not find backup ID in response"
                
                # Step 2: Fetch the configuration using the ID
                fetch_result = run_netpicker_command(["backups", "fetch", "--ip", ip, "--id", latest_id])
                if fetch_result["success"]:
                    return fetch_result["stdout"].strip()
                else:
                    return f"Error fetching backup: {fetch_result['stderr']}"
            else:
                return "No backups found for this device"
        except json.JSONDecodeError:
            return "Could not parse backup list response"
    except Exception as e:
        return f"Error fetching latest backup: {str(e)}"

app = typer.Typer(help="AI-powered natural language querying and AI service management")


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """
    Show available AI commands when no subcommand is provided.
    """
    if ctx.invoked_subcommand is None:
        typer.echo("Netpicker AI Commands:")
        typer.echo("")
        typer.echo("Available commands:")
        typer.echo("  query    Query NetPicker using natural language")
        typer.echo("  status   Check AI service status and configuration")
        typer.echo("  tools    List all available AI-routable tools")
        typer.echo("  chat     Interactive AI chat mode for querying NetPicker")
        typer.echo("")
        typer.echo("Examples:")
        typer.echo("  netpicker ai query \"Show me all devices\"")
        typer.echo("  netpicker ai status")
        typer.echo("  netpicker ai tools")
        typer.echo("  netpicker ai chat")
        typer.echo("")
        typer.echo("Use 'netpicker ai <command> --help' for more information about a specific command.")
        raise typer.Exit()


@app.command("query")
def query(
    query: str = typer.Argument(..., help="Natural language query"),
    use_ai: bool = typer.Option(True, "--use-ai/--no-ai", help="Use AI routing (default: True)"),
    json_output: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Query Netpicker using natural language.

    Uses AI routing (Mistral) by default, falls back to keyword matching.
    """
    async def _query():
        # Get available tools (synchronously for now)
        available_tools = [
            "devices_list", "devices_show", "devices_create", "devices_delete",
            "backups_history", "backups_list", "backups_upload", "backups_diff",
            "policy_list", "policy_create", "policy_add_rule", "policy_test_rule",
            "automation_list_jobs", "automation_execute_job", "health_check",
            "compliance_overview", "compliance_report_tenant", "compliance_devices"
        ]

        if use_ai:
            tool_name, reasoning = await ai_router.route_query(query, available_tools)
        else:
            # Import here to avoid circular imports
            from netpicker_cli.api_server import find_tool_by_keywords
            tool_name = find_tool_by_keywords(query)
            reasoning = "Used keyword matching"

        # If AI routing failed, fall back to keyword matching
        if not tool_name:
            from netpicker_cli.api_server import find_tool_by_keywords
            tool_name = find_tool_by_keywords(query)
            reasoning = "Used keyword matching (AI routing failed)"

        response_text = "No response"
        try:
            # Extract parameters from the query
            params = extract_parameters(query)

            # Map tool names to CLI commands with parameter handling
            tool_commands = {
                "devices_list": ["devices", "list"],
                "devices_show": ["devices", "show"],
                "devices_create": ["devices", "create"],
                "devices_delete": ["devices", "delete"],
                "backups_history": ["backups", "history"],
                "backups_list": ["backups", "list"],
                "backups_upload": ["backups", "upload"],
                "backups_diff": ["backups", "diff"],
                "policy_list": ["policy", "list"],
                "policy_create": ["policy", "create"],
                "policy_add_rule": ["policy", "add-rule"],
                "policy_test_rule": ["policy", "test-rule"],
                "automation_list_jobs": ["automation", "list-jobs"],
                "automation_execute_job": ["automation", "execute-job"],
                "health_check": ["health"],
                "compliance_overview": ["compliance", "overview"],
                "compliance_report_tenant": ["compliance", "report-tenant"],
                "compliance_devices": ["compliance", "devices"]
            }

            if tool_name in tool_commands:
                # Special handling for backup configuration retrieval
                wants_content = "config" in query.lower() or "text" in query.lower() or "content" in query.lower()
                
                if (tool_name in ["backups_list", "backups_history", "backups_diff"] and 
                    "ip" in params and wants_content):
                    # User wants the actual configuration content
                    response_text = fetch_latest_backup(params["ip"])
                else:
                    # Build the command with extracted parameters
                    cmd = tool_commands[tool_name].copy()

                    # Add parameter handling for specific tools
                    if tool_name == "devices_list" and "limit" in params:
                        cmd.extend(["--limit", str(params["limit"])])
                    if tool_name == "devices_list" and "tag" in params:
                        cmd.extend(["--tag", params["tag"]])
                    if tool_name == "devices_show" and "ip" in params:
                        cmd.append(params["ip"])
                    if tool_name == "backups_history" and "ip" in params:
                        cmd.append(params["ip"])
                    if tool_name == "backups_list" and "ip" in params:
                        cmd.extend(["--ip", params["ip"]])
                    if tool_name == "backups_diff" and "ip" in params:
                        cmd.extend(["--ip", params["ip"]])
                    if tool_name == "compliance_devices" and "ip" in params:
                        cmd.extend(["--ip", params["ip"]])

                    # Execute the CLI command
                    result = run_netpicker_command(cmd)
                    if result["success"]:
                        response_text = result["stdout"].strip() or "Command executed successfully"
                    else:
                        response_text = f"Command failed: {result['stderr'].strip()}"
            else:
                response_text = f"Unknown tool: {tool_name}"
        except Exception as e:
            response_text = f"Error: {str(e)}"

        # Handle deprecated --json flag
        output_format = format
        if json_output:
            output_format = "json"
        
        output_data = {
            "query": query,
            "tool": tool_name,
            "result": response_text,
            "reasoning": reasoning,
            "used_ai": use_ai
        }
        
        if output_format != "table" or output_file:
            OutputFormatter(format=output_format, output_file=output_file).output(output_data)
        else:
            typer.echo(f"Query: {query}")
            typer.echo(f"Tool: {tool_name}")
            typer.echo(f"Reasoning: {reasoning}")
            typer.echo(f"Result:\n{response_text}")

    asyncio.run(_query())


@app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    Check AI service status and configuration.
    """
    async def _status():
        available = await ai_router.is_available()

        status_info = {
            "enabled": ai_router.enabled,
            "available": available,
            "url": ai_router.mistral_url,
            "status": "connected" if available else "unavailable"
        }

        # Handle deprecated --json flag
        output_format = format
        if json_output:
            output_format = "json"
        
        if output_format != "table" or output_file:
            OutputFormatter(format=output_format, output_file=output_file).output(status_info)
        else:
            typer.secho("AI Router Status", fg=typer.colors.BLUE, bold=True)
            typer.echo(f"Enabled: {status_info['enabled']}")
            typer.echo(f"Available: {status_info['available']}")
            typer.echo(f"URL: {status_info['url']}")
            typer.echo(f"Status: {status_info['status']}")

    asyncio.run(_status())


@app.command("tools")
def list_tools(
    json_output: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """
    List all available AI-routable tools.
    """
    async def _list_tools():
        tools = await mcp.list_tools()

        tool_list = [{"name": t.name, "description": t.description} for t in tools]
        
        if json_output:
            format_to_use = "json"
        else:
            format_to_use = format
        
        if format_to_use != "table" or output_file:
            OutputFormatter(format=format_to_use, output_file=output_file).output(tool_list)
        else:
            typer.secho("Available Tools", fg=typer.colors.BLUE, bold=True)
            for tool in tools:
                typer.echo(f"• {tool.name}: {tool.description}")

    asyncio.run(_list_tools())


@app.command("chat")
def chat(
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", help="Interactive mode")
):
    """
    Interactive AI chat mode for querying NetPicker.
    """
    typer.secho("NetPicker AI Chat Mode", fg=typer.colors.GREEN, bold=True)
    typer.echo("Type your queries in natural language. Type 'exit' or 'quit' to end.")
    typer.echo("Use 'status' to check AI status, 'tools' to list available tools.")
    typer.echo("")

    while True:
        try:
            query = typer.prompt("NetPicker> ")
            query = query.strip()

            if query.lower() in ['exit', 'quit', 'q']:
                typer.secho("Goodbye!", fg=typer.colors.YELLOW)
                break

            if query.lower() == 'status':
                asyncio.run(status())
                continue

            if query.lower() == 'tools':
                asyncio.run(list_tools())
                continue

            # Process the query
            asyncio.run(query(query, use_ai=True, json_output=False))

        except KeyboardInterrupt:
            typer.secho("\nGoodbye!", fg=typer.colors.YELLOW)
            break
        except Exception as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)


if __name__ == "__main__":
    app()