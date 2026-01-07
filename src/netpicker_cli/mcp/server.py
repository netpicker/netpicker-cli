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
from typing import Any, Dict, List, Optional

from mcp.server import FastMCP

# Import NetPicker CLI modules for direct access where possible
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound

# Create FastMCP server instance
mcp = FastMCP("netpicker-mcp")


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

        # Run the netpicker command using the installed CLI
        # Use 'netpicker' directly instead of python -m to avoid output issues
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


@mcp.tool()
async def devices_list(tag: Optional[str] = None, json_output: bool = False, limit: int = 50) -> str:
    """List all network devices with optional filtering.

    Args:
        tag: Filter devices by tag
        json_output: Return JSON output instead of table
        limit: Limit number of results

    Returns:
        Device list output
    """
    args = ["devices", "list"]
    if tag:
        args.extend(["--tag", tag])
    if json_output:
        args.append("--json")
    if limit != 50:
        args.extend(["--limit", str(limit)])

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No devices found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def devices_show(ip: str, json_output: bool = False) -> str:
    """Show details of a specific device.

    Args:
        ip: Device IP address or hostname
        json_output: Return JSON output instead of table

    Returns:
        Device details
    """
    args = ["devices", "show", ip]
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Device not found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def devices_create(ip: str, name: str, platform: str, vault: str, port: int = 22, tags: Optional[str] = None) -> str:
    """Create a new network device.

    Args:
        ip: Device IP address
        name: Device friendly name
        platform: Netmiko platform (e.g., cisco_ios, arista_eos)
        vault: Vault/credential profile name
        port: SSH port
        tags: Comma-separated tags

    Returns:
        Creation result
    """
    args = ["devices", "create", ip, "--name", name, "--platform", platform, "--vault", vault]
    if port != 22:
        args.extend(["--port", str(port)])
    if tags:
        args.extend(["--tags", tags])

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Device created successfully"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def devices_delete(ip: str, force: bool = False) -> str:
    """Delete a network device.

    Args:
        ip: Device IP address to delete
        force: Skip confirmation prompt

    Returns:
        Deletion result
    """
    args = ["devices", "delete", ip]
    if force:
        args.append("--force")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Device deleted successfully"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def backups_upload(ip: str, config_content: str, changed: bool = False) -> str:
    """Upload a device configuration backup.

    Args:
        ip: Device IP address
        config_content: Device configuration content
        changed: Mark as changed configuration

    Returns:
        Upload result
    """
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(config_content)
        config_file = f.name

    try:
        args = ["backups", "upload", ip, "--file", config_file]
        if changed:
            args.append("--changed")

        result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

        if result["success"]:
            return result["stdout"].strip() or "Config uploaded successfully"
        else:
            return f"Command failed: {result['stderr'].strip()}"
    finally:
        os.unlink(config_file)


@mcp.tool()
async def backups_history(ip: str, limit: int = 20, json_output: bool = False) -> str:
    """Show backup history for a device.

    Args:
        ip: Device IP address
        limit: Limit number of results
        json_output: Return JSON output

    Returns:
        Backup history
    """
    args = ["backups", "history", ip]
    if limit != 20:
        args.extend(["--limit", str(limit)])
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No backups found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def backups_diff(ip: str, id_a: Optional[str] = None, id_b: Optional[str] = None, context: int = 3) -> str:
    """Compare two device configuration backups.

    Args:
        ip: Device IP address
        id_a: First config ID to compare
        id_b: Second config ID to compare
        context: Lines of context for diff

    Returns:
        Configuration diff
    """
    args = ["backups", "diff", ip]
    if id_a:
        args.extend(["--id-a", id_a])
    if id_b:
        args.extend(["--id-b", id_b])
    if context != 3:
        args.extend(["--context", str(context)])

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No differences found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def policy_list(json_output: bool = False) -> str:
    """List compliance policies.

    Args:
        json_output: Return JSON output

    Returns:
        Policy list
    """
    args = ["policy", "list"]
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No policies found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def policy_create(name: str, description: Optional[str] = None) -> str:
    """Create a new compliance policy.

    Args:
        name: Policy name
        description: Policy description

    Returns:
        Creation result
    """
    args = ["policy", "create", "--name", name]
    if description:
        args.extend(["--description", description])

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Policy created successfully"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def policy_add_rule(policy_id: str, name: str, rule_text: str, description: Optional[str] = None, severity: str = "HIGH") -> str:
    """Add a rule to a compliance policy.

    Args:
        policy_id: Policy ID
        name: Rule name
        rule_text: Text to match in configurations
        description: Rule description
        severity: Rule severity (HIGH, MEDIUM, LOW)

    Returns:
        Rule addition result
    """
    args = ["policy", "add-rule", policy_id, "--name", name, "--rule-config", json.dumps({"pattern": rule_text, "type": "regex"})]
    if description:
        args.extend(["--description", description])

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Rule added successfully"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def policy_test_rule(policy_id: str, rule_name: str, ip: str, config: str) -> str:
    """Test a compliance rule against device configuration.

    Args:
        policy_id: Policy ID
        rule_name: Rule name to test
        ip: Device IP address
        config: Device configuration content

    Returns:
        Test result
    """
    args = ["policy", "test-rule", "--rule-config", json.dumps({"pattern": "test", "type": "regex"}), "--config-id", "test"]

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Rule test completed"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def automation_list_jobs(json_output: bool = False) -> str:
    """List available automation jobs.

    Args:
        json_output: Return JSON output

    Returns:
        Job list
    """
    args = ["automation", "list-jobs"]
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No jobs found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def automation_execute_job(name: str, variables: Optional[str] = None, devices: Optional[str] = None, tags: Optional[str] = None) -> str:
    """Execute an automation job.

    Args:
        name: Job name to execute
        variables: Variables as JSON string
        devices: Target devices (comma-separated)
        tags: Target device tags (comma-separated)

    Returns:
        Execution result
    """
    args = ["automation", "execute-job", "--name", name]
    if variables:
        args.extend(["--fixtures", variables])
    if devices:
        args.extend(["--devices", devices])
    if tags:
        args.extend(["--tags", tags])

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "Job executed successfully"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def health_check(json_output: bool = False) -> str:
    """Check system health and connectivity.

    Args:
        json_output: Return JSON output

    Returns:
        Health status
    """
    args = ["health"]
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "System is healthy"
    else:
        return f"Health check failed: {result['stderr'].strip()}"


@mcp.tool()
async def compliance_overview(json_output: bool = False) -> str:
    """Get compliance overview for the tenant.

    Args:
        json_output: Return JSON output

    Returns:
        Compliance overview
    """
    args = ["compliance", "overview"]
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No compliance data found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def compliance_report_tenant(json_output: bool = False) -> str:
    """Get compliance report for the tenant.

    Args:
        json_output: Return JSON output

    Returns:
        Tenant compliance report
    """
    args = ["compliance", "report-tenant"]
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No compliance report data found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


@mcp.tool()
async def compliance_devices(ip: Optional[str] = None, policy: Optional[str] = None, json_output: bool = False) -> str:
    """Get policy devices list for the tenant.

    Args:
        ip: Filter by device IP
        policy: Filter by policy name
        json_output: Return JSON output

    Returns:
        Device compliance status
    """
    args = ["compliance", "devices"]
    if ip:
        args.extend(["--ip", ip])
    if policy:
        args.extend(["--policy", policy])
    if json_output:
        args.append("--json")

    result = await asyncio.get_event_loop().run_in_executor(None, run_netpicker_command, args)

    if result["success"]:
        return result["stdout"].strip() or "No device compliance data found"
    else:
        return f"Command failed: {result['stderr'].strip()}"


def main():
    """Main entry point for the MCP server."""
    import asyncio
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()