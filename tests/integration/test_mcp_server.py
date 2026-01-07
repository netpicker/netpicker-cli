"""
Tests for NetPicker MCP Server
"""

import pytest
import subprocess
from unittest.mock import patch, MagicMock
import json
from netpicker_cli.mcp.server import mcp, run_netpicker_command


class TestNetPickerMCP:
    """Test the NetPicker MCP server functionality."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that tools are properly listed."""
        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = [
            "devices_list", "devices_show", "devices_create", "devices_delete",
            "backups_upload", "backups_history", "backups_diff",
            "policy_list", "policy_create", "policy_add_rule", "policy_test_rule",
            "automation_list_jobs", "automation_execute_job",
            "health_check"
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_devices_list_tool(self, mock_run_command):
        """Test the devices_list tool."""
        mock_run_command.return_value = {
            "stdout": "Device list output",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("devices_list", {"json_output": True})

        assert "Device list output" in result[0][0].text
        mock_run_command.assert_called_once()
        args, kwargs = mock_run_command.call_args
        assert args[0] == ["devices", "list", "--json"]

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_devices_create_tool(self, mock_run_command):
        """Test the devices_create tool."""
        mock_run_command.return_value = {
            "stdout": "Device created successfully",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        args = {
            "ip": "192.168.1.100",
            "name": "test-router",
            "platform": "cisco_ios",
            "vault": "default",
            "tags": "test,production"
        }

        result = await mcp.call_tool("devices_create", args)

        assert "Device created successfully" in result[0][0].text
        mock_run_command.assert_called_once()
        call_args, kwargs = mock_run_command.call_args
        expected_args = ["devices", "create", "192.168.1.100", "--name", "test-router", "--platform", "cisco_ios", "--vault", "default", "--tags", "test,production"]
        assert call_args[0] == expected_args

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_backups_upload_tool(self, mock_run_command):
        """Test the backups_upload tool."""
        mock_run_command.return_value = {
            "stdout": "Config uploaded successfully",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        args = {
            "ip": "192.168.1.100",
            "config_content": "interface GigabitEthernet0/0\n ip address 192.168.1.100 255.255.255.0",
            "changed": True
        }

        result = await mcp.call_tool("backups_upload", args)

        assert "Config uploaded successfully" in result[0][0].text
        mock_run_command.assert_called_once()

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_policy_test_rule_tool(self, mock_run_command):
        """Test the policy_test_rule tool."""
        mock_run_command.return_value = {
            "stdout": "PASS - Rule validation successful",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        args = {
            "policy_id": "security-policy",
            "rule_name": "no-telnet",
            "ip": "192.168.1.100",
            "config": "line vty 0 4\n transport input ssh"
        }

        result = await mcp.call_tool("policy_test_rule", args)

        assert "PASS - Rule validation successful" in result[0][0].text
        mock_run_command.assert_called_once()

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_command_failure(self, mock_run_command):
        """Test handling of command failures."""
        mock_run_command.return_value = {
            "stdout": "",
            "stderr": "Error: Device not found",
            "returncode": 1,
            "success": False
        }

        result = await mcp.call_tool("devices_show", {"ip": "192.168.1.999"})

        assert "Command failed" in result[0][0].text
        assert "Device not found" in result[0][0].text

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        """Test handling of unknown tools."""
        with pytest.raises(Exception):  # FastMCP should raise an exception for unknown tools
            await mcp.call_tool("unknown_tool", {})

    def test_run_netpicker_command_success(self):
        """Test successful command execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Success output",
                stderr="",
                returncode=0
            )

            result = run_netpicker_command(["devices", "list"])

            assert result["success"] is True
            assert result["stdout"] == "Success output"
            assert result["stderr"] == ""
            assert result["returncode"] == 0

    def test_run_netpicker_command_failure(self):
        """Test failed command execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="Command failed",
                returncode=1
            )

            result = run_netpicker_command(["invalid", "command"])

            assert result["success"] is False
            assert result["stdout"] == ""
            assert result["stderr"] == "Command failed"
            assert result["returncode"] == 1

    def test_run_netpicker_command_timeout(self):
        """Test command timeout handling."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("timeout", 30)):
            result = run_netpicker_command(["slow", "command"])

            assert result["success"] is False
            assert "timed out" in result["stderr"]
            assert result["returncode"] == -1