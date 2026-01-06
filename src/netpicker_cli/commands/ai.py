"""
AI command for NetPicker CLI

Provides AI-powered natural language querying and AI service management.
"""

import typer
from typing import Optional, Dict, Any
import asyncio
import subprocess
import os
import re
from netpicker_cli.ai import router as ai_router
from netpicker_cli.mcp.server import mcp

def run_netpicker_command(args):
    """
    Run a NetPicker CLI command and return the result.
    Similar to the function in MCP server.
    """
    try:
        # Set environment variables for NetPicker
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

    for pattern in limit_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params['limit'] = int(match.group(1))
            break

    # Extract IP addresses for device-specific queries
    ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
    match = re.search(ip_pattern, query)
    if match:
        params['ip'] = match.group(1)

    # Extract tags (more flexible patterns)
    tag_patterns = [
        r'\btag\s+([a-z0-9_-]+)\b',         # "tag foo", "tag test-1"
        r'\bwith\s+tag\s+([a-z0-9_-]+)\b',  # "with tag foo"
        r'\bfor\s+tag\s+([a-z0-9_-]+)\b',   # "for tag foo"
    ]

    for pattern in tag_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            params['tag'] = match.group(1)
            break

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


@app.command("query")
def query(
    query: str = typer.Argument(..., help="Natural language query"),
    use_ai: bool = typer.Option(True, "--use-ai/--no-ai", help="Use AI routing (default: True)"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format")
):
    """
    Query NetPicker using natural language.

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

        if json_output:
            import json
            output = {
                "query": query,
                "tool": tool_name,
                "result": response_text,
                "reasoning": reasoning,
                "used_ai": use_ai
            }
            typer.echo(json.dumps(output, indent=2))
        else:
            typer.echo(f"Query: {query}")
            typer.echo(f"Tool: {tool_name}")
            typer.echo(f"Reasoning: {reasoning}")
            typer.echo(f"Result:\n{response_text}")

    asyncio.run(_query())


@app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format")
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

        if json_output:
            import json
            typer.echo(json.dumps(status_info, indent=2))
        else:
            typer.secho("AI Router Status", fg=typer.colors.BLUE, bold=True)
            typer.echo(f"Enabled: {status_info['enabled']}")
            typer.echo(f"Available: {status_info['available']}")
            typer.echo(f"URL: {status_info['url']}")
            typer.echo(f"Status: {status_info['status']}")

    asyncio.run(_status())


@app.command("tools")
def list_tools(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format")
):
    """
    List all available AI-routable tools.
    """
    async def _list_tools():
        tools = await mcp.list_tools()

        if json_output:
            import json
            tool_list = [{"name": t.name, "description": t.description} for t in tools]
            typer.echo(json.dumps(tool_list, indent=2))
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