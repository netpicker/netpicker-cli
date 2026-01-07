"""
Enhanced tests for MCP server tools with mocking
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
from netpicker_cli.mcp.server import mcp, run_netpicker_command


class TestMCPServerToolsMocked:
    """Test MCP server tools with comprehensive mocking"""

    @pytest.mark.asyncio
    async def test_list_all_tools(self):
        """Test that all expected tools are registered"""
        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        # Comprehensive tool list
        expected_tools = [
            "devices_list", "devices_show", "devices_create", "devices_delete",
            "backups_upload", "backups_history", "backups_diff",
            "policy_list", "policy_create", "policy_add_rule", "policy_test_rule",
            "automation_list_jobs", "automation_execute_job",
            "health_check"
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool {tool_name} not found"

    @pytest.mark.asyncio
    async def test_tool_has_descriptions(self):
        """Test that all tools have descriptions"""
        tools = await mcp.list_tools()
        
        for tool in tools:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 10, f"Tool {tool.name} has too short description"

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_devices_show_tool(self, mock_run_command):
        """Test devices_show tool execution"""
        mock_run_command.return_value = {
            "stdout": '{"name": "router1", "ipaddress": "192.168.1.1"}',
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("devices_show", {"ip": "192.168.1.1", "json_output": True})

        assert len(result) > 0
        assert "router1" in result[0][0].text
        mock_run_command.assert_called_once()

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_devices_create_tool(self, mock_run_command):
        """Test devices_create tool execution"""
        mock_run_command.return_value = {
            "stdout": "Device created successfully",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("devices_create", {
            "ip": "192.168.1.1",
            "name": "new-router",
            "platform": "cisco_ios"
        })

        assert "created" in result[0][0].text.lower()
        args = mock_run_command.call_args[0][0]
        assert "devices" in args
        assert "create" in args

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_backups_history_tool(self, mock_run_command):
        """Test backups_history tool execution"""
        mock_run_command.return_value = {
            "stdout": "Backup history output",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("backups_history", {
            "ip": "192.168.1.1",
            "limit": 10
        })

        assert "Backup history" in result[0][0].text
        args = mock_run_command.call_args[0][0]
        assert "backups" in args
        assert "history" in args

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_policy_create_tool(self, mock_run_command):
        """Test policy_create tool execution"""
        mock_run_command.return_value = {
            "stdout": "Policy created",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("policy_create", {
            "name": "test-policy",
            "description": "Test policy description"
        })

        assert "created" in result[0][0].text.lower()

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_automation_execute_job_tool(self, mock_run_command):
        """Test automation_execute_job tool execution"""
        mock_run_command.return_value = {
            "stdout": "Job executed on 5 devices",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("automation_execute_job", {
            "name": "backup-job",
            "devices": "192.168.1.1,192.168.1.2"
        })

        assert "executed" in result[0][0].text.lower()


class TestMCPToolParameters:
    """Test MCP tool parameter handling"""

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_with_optional_parameters(self, mock_run_command):
        """Test tool execution with optional parameters omitted"""
        mock_run_command.return_value = {
            "stdout": "Success",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        # Call with only required parameters
        result = await mcp.call_tool("devices_list", {})

        assert result is not None
        mock_run_command.assert_called_once()

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_with_all_parameters(self, mock_run_command):
        """Test tool execution with all parameters provided"""
        mock_run_command.return_value = {
            "stdout": "Success",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        result = await mcp.call_tool("devices_list", {
            "json_output": True,
            "limit": 50,
            "tag": "production"
        })

        assert result is not None
        args = mock_run_command.call_args[0][0]
        assert "--limit" in args or "50" in str(args)

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_with_json_output_flag(self, mock_run_command):
        """Test that json_output parameter adds --json flag"""
        mock_run_command.return_value = {
            "stdout": "{}",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        await mcp.call_tool("devices_list", {"json_output": True})

        args = mock_run_command.call_args[0][0]
        assert "--json" in args


class TestMCPErrorHandling:
    """Test MCP server error handling"""

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_command_failure(self, mock_run_command):
        """Test handling of command execution failure"""
        mock_run_command.return_value = {
            "stdout": "",
            "stderr": "Error: Device not found",
            "returncode": 1,
            "success": False
        }

        result = await mcp.call_tool("devices_show", {"ip": "192.168.1.1"})

        assert "failed" in result[0][0].text.lower() or "error" in result[0][0].text.lower()

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_with_exception(self, mock_run_command):
        """Test handling of exceptions during tool execution"""
        mock_run_command.side_effect = Exception("Unexpected error")

        with pytest.raises(Exception):
            await mcp.call_tool("devices_list", {})

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self):
        """Test calling non-existent tool"""
        with pytest.raises(Exception):
            await mcp.call_tool("non_existent_tool", {})

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_with_invalid_parameters(self, mock_run_command):
        """Test tool with invalid parameter types"""
        mock_run_command.return_value = {
            "stdout": "",
            "stderr": "Invalid limit value",
            "returncode": 1,
            "success": False
        }

        # Pass string where number expected
        result = await mcp.call_tool("devices_list", {"limit": "invalid"})

        # Should handle gracefully
        assert result is not None


class TestMCPCommandConstruction:
    """Test MCP command construction logic"""

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_command_args_construction(self, mock_run_command):
        """Test that command arguments are constructed correctly"""
        mock_run_command.return_value = {
            "stdout": "Success",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        await mcp.call_tool("devices_show", {"ip": "192.168.1.1"})

        args = mock_run_command.call_args[0][0]
        assert args[0] == "devices"
        assert args[1] == "show"
        assert "192.168.1.1" in args

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_comma_separated_parameters(self, mock_run_command):
        """Test handling of comma-separated parameters"""
        mock_run_command.return_value = {
            "stdout": "Success",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        await mcp.call_tool("automation_execute_job", {
            "name": "test-job",
            "devices": "192.168.1.1,192.168.1.2,192.168.1.3"
        })

        args = mock_run_command.call_args[0][0]
        assert any("192.168.1.1" in str(arg) for arg in args)

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_json_string_parameters(self, mock_run_command):
        """Test handling of JSON string parameters"""
        mock_run_command.return_value = {
            "stdout": "Success",
            "stderr": "",
            "returncode": 0,
            "success": True
        }

        variables_json = '{"key1": "value1", "key2": "value2"}'
        await mcp.call_tool("automation_execute_job", {
            "name": "test-job",
            "variables": variables_json
        })

        args = mock_run_command.call_args[0][0]
        # JSON should be passed as parameter
        assert any("key1" in str(arg) for arg in args) or "--fixtures" in args


class TestRunNetpickerCommandMocked:
    """Test run_netpicker_command function with mocking"""

    @patch('subprocess.run')
    def test_command_execution_success(self, mock_subprocess):
        """Test successful command execution"""
        mock_subprocess.return_value = MagicMock(
            stdout="Command output",
            stderr="",
            returncode=0
        )

        result = run_netpicker_command(["devices", "list"])

        assert result["success"] is True
        assert result["stdout"] == "Command output"
        assert result["returncode"] == 0

    @patch('subprocess.run')
    def test_command_execution_failure(self, mock_subprocess):
        """Test failed command execution"""
        mock_subprocess.return_value = MagicMock(
            stdout="",
            stderr="Command failed",
            returncode=1
        )

        result = run_netpicker_command(["devices", "delete", "192.168.1.1"])

        assert result["success"] is False
        assert result["stderr"] == "Command failed"
        assert result["returncode"] == 1

    @patch('subprocess.run')
    def test_subprocess_exception_handling(self, mock_subprocess):
        """Test handling of subprocess exceptions"""
        mock_subprocess.side_effect = FileNotFoundError("netpicker command not found")

        result = run_netpicker_command(["devices", "list"])

        assert result["success"] is False
        assert "not found" in result["stderr"].lower() or "error" in result["stderr"].lower()

    @patch('subprocess.run')
    def test_environment_variable_passing(self, mock_subprocess):
        """Test that environment variables are passed to subprocess"""
        mock_subprocess.return_value = MagicMock(
            stdout="Output",
            stderr="",
            returncode=0
        )

        run_netpicker_command(["devices", "list"])

        call_kwargs = mock_subprocess.call_args.kwargs
        assert "env" in call_kwargs
        assert isinstance(call_kwargs["env"], dict)


class TestMCPServerIntegration:
    """Integration tests for MCP server"""

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test that MCP server initializes correctly"""
        # Server should be initialized
        assert mcp is not None
        tools = await mcp.list_tools()
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_sequence(self):
        """Test calling multiple tools in sequence"""
        with patch('netpicker_cli.mcp.server.run_netpicker_command') as mock_run:
            mock_run.return_value = {
                "stdout": "Success",
                "stderr": "",
                "returncode": 0,
                "success": True
            }

            # Call multiple tools
            await mcp.call_tool("devices_list", {})
            await mcp.call_tool("health_check", {})
            await mcp.call_tool("policy_list", {})

            assert mock_run.call_count == 3
