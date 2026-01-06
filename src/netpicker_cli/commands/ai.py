"""
AI command for NetPicker CLI

Provides AI-powered natural language querying and AI service management.
"""

import typer
from typing import Optional
import asyncio
import subprocess
import os
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
            "backups_history", "backups_upload", "backups_download", "backups_diff", "backups_recent",
            "compliance_policy_list", "compliance_policy_test", "compliance_check",
            "automation_list", "automation_run", "health_check", "whoami"
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
            # Map tool names to CLI commands
            tool_commands = {
                "devices_list": ["devices", "list"],
                "devices_show": ["devices", "show"],
                "devices_create": ["devices", "create"],
                "devices_delete": ["devices", "delete"],
                "backups_history": ["backups", "history"],
                "backups_upload": ["backups", "upload"],
                "backups_download": ["backups", "download"],
                "backups_diff": ["backups", "diff"],
                "backups_recent": ["backups", "recent"],
                "compliance_policy_list": ["compliance", "policy", "list"],
                "compliance_policy_test": ["compliance", "policy", "test"],
                "compliance_check": ["compliance", "check"],
                "automation_list": ["automation", "list"],
                "automation_run": ["automation", "run"],
                "health_check": ["health", "check"],
                "whoami": ["whoami"]
            }

            if tool_name in tool_commands:
                # Execute the CLI command
                result = run_netpicker_command(tool_commands[tool_name])
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