"""
NetPicker MCP Server

This MCP server provides access to NetPicker CLI functionality through
Model Context Protocol, allowing AI assistants to interact with network
devices, backups, compliance policies, and automation.
"""

import asyncio
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Import NetPicker CLI modules for direct access where possible
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound

server = Server("netpicker-mcp")


def run_netpicker_command(args: List[str]) -> Dict[str, Any]:
    """
    Run a NetPicker CLI command and return the result.

    Args:
        args: Command line arguments for netpicker CLI

    Returns:
        Dict containing stdout, stderr, and return code
    """
    try:
        # Set environment variables for NetPicker
        env = os.environ.copy()

        # Run the netpicker command
        cmd = [sys.executable, "-m", "netpicker_cli.cli"] + args
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


@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available NetPicker tools."""
    return [
        types.Tool(
            name="devices_list",
            description="List all network devices with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {
                        "type": "string",
                        "description": "Filter devices by tag"
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON output instead of table",
                        "default": False
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Limit number of results",
                        "default": 50
                    }
                }
            }
        ),
        types.Tool(
            name="devices_show",
            description="Show details of a specific device",
            inputSchema={
                "type": "object",
                "required": ["ip"],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Device IP address or hostname"
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON output instead of table",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="devices_create",
            description="Create a new network device",
            inputSchema={
                "type": "object",
                "required": ["ip", "name", "platform", "vault"],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Device IP address"
                    },
                    "name": {
                        "type": "string",
                        "description": "Device friendly name"
                    },
                    "platform": {
                        "type": "string",
                        "description": "Netmiko platform (e.g., cisco_ios, arista_eos)"
                    },
                    "vault": {
                        "type": "string",
                        "description": "Vault/credential profile name"
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port",
                        "default": 22
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags"
                    }
                }
            }
        ),
        types.Tool(
            name="devices_delete",
            description="Delete a network device",
            inputSchema={
                "type": "object",
                "required": ["ip"],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Device IP address to delete"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Skip confirmation prompt",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="backups_upload",
            description="Upload a device configuration backup",
            inputSchema={
                "type": "object",
                "required": ["ip", "config_content"],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Device IP address"
                    },
                    "config_content": {
                        "type": "string",
                        "description": "Device configuration content"
                    },
                    "changed": {
                        "type": "boolean",
                        "description": "Mark as changed configuration",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="backups_history",
            description="Show backup history for a device",
            inputSchema={
                "type": "object",
                "required": ["ip"],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Device IP address"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Limit number of results",
                        "default": 20
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON output",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="backups_diff",
            description="Compare two device configuration backups",
            inputSchema={
                "type": "object",
                "required": ["ip"],
                "properties": {
                    "ip": {
                        "type": "string",
                        "description": "Device IP address"
                    },
                    "id_a": {
                        "type": "string",
                        "description": "First config ID to compare"
                    },
                    "id_b": {
                        "type": "string",
                        "description": "Second config ID to compare"
                    },
                    "context": {
                        "type": "integer",
                        "description": "Lines of context for diff",
                        "default": 3
                    }
                }
            }
        ),
        types.Tool(
            name="policy_list",
            description="List compliance policies",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON output",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="policy_create",
            description="Create a new compliance policy",
            inputSchema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Policy name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Policy description"
                    },
                    "policy_type": {
                        "type": "string",
                        "description": "Policy type"
                    }
                }
            }
        ),
        types.Tool(
            name="policy_add_rule",
            description="Add a rule to a compliance policy",
            inputSchema={
                "type": "object",
                "required": ["policy_id", "name", "rule_text"],
                "properties": {
                    "policy_id": {
                        "type": "string",
                        "description": "Policy ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Rule name"
                    },
                    "rule_text": {
                        "type": "string",
                        "description": "Text to match in configurations"
                    },
                    "description": {
                        "type": "string",
                        "description": "Rule description"
                    },
                    "severity": {
                        "type": "string",
                        "description": "Rule severity (HIGH, MEDIUM, LOW)",
                        "default": "HIGH"
                    }
                }
            }
        ),
        types.Tool(
            name="policy_test_rule",
            description="Test a compliance rule against device configuration",
            inputSchema={
                "type": "object",
                "required": ["policy_id", "rule_name", "ip", "config"],
                "properties": {
                    "policy_id": {
                        "type": "string",
                        "description": "Policy ID"
                    },
                    "rule_name": {
                        "type": "string",
                        "description": "Rule name to test"
                    },
                    "ip": {
                        "type": "string",
                        "description": "Device IP address"
                    },
                    "config": {
                        "type": "string",
                        "description": "Device configuration content"
                    }
                }
            }
        ),
        types.Tool(
            name="automation_list_jobs",
            description="List available automation jobs",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON output",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="automation_execute_job",
            description="Execute an automation job",
            inputSchema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Job name to execute"
                    },
                    "variables": {
                        "type": "string",
                        "description": "Variables as JSON string"
                    },
                    "devices": {
                        "type": "string",
                        "description": "Target devices (comma-separated)"
                    },
                    "tags": {
                        "type": "string",
                        "description": "Target device tags (comma-separated)"
                    }
                }
            }
        ),
        types.Tool(
            name="health_check",
            description="Check system health and connectivity",
            inputSchema={
                "type": "object",
                "properties": {
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON output",
                        "default": False
                    }
                }
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls."""

    try:
        if name == "devices_list":
            args = ["devices", "list"]
            if arguments.get("tag"):
                args.extend(["--tag", arguments["tag"]])
            if arguments.get("json_output"):
                args.append("--json")
            if arguments.get("limit"):
                args.extend(["--limit", str(arguments["limit"])])

        elif name == "devices_show":
            args = ["devices", "show", arguments["ip"]]
            if arguments.get("json_output"):
                args.append("--json")

        elif name == "devices_create":
            args = [
                "devices", "create", arguments["ip"],
                "--name", arguments["name"],
                "--platform", arguments["platform"],
                "--vault", arguments["vault"]
            ]
            if arguments.get("port"):
                args.extend(["--port", str(arguments["port"])])
            if arguments.get("tags"):
                args.extend(["--tags", arguments["tags"]])

        elif name == "devices_delete":
            args = ["devices", "delete", arguments["ip"]]
            if arguments.get("force"):
                args.append("--force")

        elif name == "backups_upload":
            # For config upload, we need to create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(arguments["config_content"])
                config_file = f.name

            try:
                args = ["backups", "upload", arguments["ip"], "--file", config_file]
                if arguments.get("changed"):
                    args.append("--changed")
            finally:
                os.unlink(config_file)

        elif name == "backups_history":
            args = ["backups", "history", arguments["ip"]]
            if arguments.get("limit"):
                args.extend(["--limit", str(arguments["limit"])])
            if arguments.get("json_output"):
                args.append("--json")

        elif name == "backups_diff":
            args = ["backups", "diff", arguments["ip"]]
            if arguments.get("id_a"):
                args.extend(["--id-a", arguments["id_a"]])
            if arguments.get("id_b"):
                args.extend(["--id-b", arguments["id_b"]])
            if arguments.get("context"):
                args.extend(["--context", str(arguments["context"])])

        elif name == "policy_list":
            args = ["policy", "list"]
            if arguments.get("json_output"):
                args.append("--json")

        elif name == "policy_create":
            args = ["policy", "create", "--name", arguments["name"]]
            if arguments.get("description"):
                args.extend(["--description", arguments["description"]])
            if arguments.get("policy_type"):
                args.extend(["--type", arguments["policy_type"]])

        elif name == "policy_add_rule":
            args = [
                "policy", "add-rule", arguments["policy_id"],
                "--name", arguments["name"],
                "--simplified-text", arguments["rule_text"]
            ]
            if arguments.get("description"):
                args.extend(["--description", arguments["description"]])
            if arguments.get("severity"):
                args.extend(["--severity", arguments["severity"]])

        elif name == "policy_test_rule":
            args = [
                "policy", "test-rule", arguments["policy_id"],
                "--name", arguments["rule_name"],
                "--ip", arguments["ip"],
                "--config", arguments["config"]
            ]

        elif name == "automation_list_jobs":
            args = ["automation", "list-jobs"]
            if arguments.get("json_output"):
                args.append("--json")

        elif name == "automation_execute_job":
            args = ["automation", "execute-job", "--name", arguments["name"]]
            if arguments.get("variables"):
                args.extend(["--variables", arguments["variables"]])
            if arguments.get("devices"):
                args.extend(["--devices", arguments["devices"]])
            if arguments.get("tags"):
                args.extend(["--tags", arguments["tags"]])

        elif name == "health_check":
            args = ["health"]
            if arguments.get("json_output"):
                args.append("--json")

        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

        # Execute the command
        result = await asyncio.get_event_loop().run_in_executor(
            None, run_netpicker_command, args
        )

        # Format the response
        if result["success"]:
            content = result["stdout"].strip() or "Command executed successfully"
        else:
            content = f"Command failed:\n{result['stderr'].strip()}\nExit code: {result['returncode']}"

        return [types.TextContent(type="text", text=content)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error executing tool {name}: {str(e)}"
        )]


async def main():
    """Main entry point for the MCP server."""
    # Run the server using stdio transport
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="netpicker-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


def main_sync():
    """Synchronous wrapper for the main function."""
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()