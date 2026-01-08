"""
Mocked MCP tool interactions to validate behavior without a live server.

Covers:
- Successful tool execution returning a success status
- Failing tool execution (e.g., Device Unreachable) handled gracefully
"""

import pytest
from unittest.mock import patch

from netpicker_cli.mcp.server import mcp


class TestMCPToolsMocked:
    """Mock MCP server tool interactions."""

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_success(self, mock_run_cmd):
        """Simulate tool execution that returns Success."""
        mock_run_cmd.return_value = {
            "stdout": "Success",
            "stderr": "",
            "returncode": 0,
            "success": True,
        }

        result = await mcp.call_tool("devices_list", {"json_output": True})

        # mcp.call_tool returns a list of ToolResult objects; read text
        assert result and result[0][0].text
        assert "Success" in result[0][0].text

    @patch('netpicker_cli.mcp.server.run_netpicker_command')
    @pytest.mark.asyncio
    async def test_tool_error_device_unreachable(self, mock_run_cmd):
        """Simulate tool execution returning an Error status and verify graceful handling."""
        mock_run_cmd.return_value = {
            "stdout": "",
            "stderr": "Device Unreachable",
            "returncode": 1,
            "success": False,
        }

        result = await mcp.call_tool("devices_show", {"ip": "10.0.0.1"})

        # Should not raise; text should surface the error message
        assert result and result[0][0].text
        text = result[0][0].text
        assert "failed" in text.lower() or "device unreachable" in text.lower()
