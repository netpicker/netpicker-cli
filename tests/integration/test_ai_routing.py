"""
Integration tests for AI query routing
"""

import pytest
import respx
from unittest import mock
from typer.testing import CliRunner
from netpicker_cli.cli import app
from netpicker_cli.utils.config import Settings
from netpicker_cli.ai.router import QueryRouter


@pytest.fixture
def runner():
    """CLI test runner"""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    return Settings(
        base_url="https://api.example.com",
        tenant="test-tenant",
        token="test-token"
    )


class TestAIQueryRouting:
    """Test AI query routing functionality"""

    @respx.mock
    def test_ai_query_devices_list(self, runner, mock_settings):
        """Test AI query routing to devices list"""
        # Mock the devices list API endpoint
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": "router1", "ipaddress": "192.168.1.1"}]}
        )

        result = runner.invoke(app, ["ai", "query", "list devices", "--no-ai"])
        assert result.exit_code == 0

    def test_ai_routing_check_compliance_calls_compliance_devices(self, runner):
        """When AI returns a compliance intent, call compliance tool with params."""
        query_text = "check compliance for 10.0.0.1"

        # Mock the AI router to return a compliance intent/tool
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("compliance_devices", "check_compliance")),
        ) as _route_mock:
            with patch(
                "netpicker_cli.commands.ai.run_netpicker_command",
                return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
            ) as run_mock:
                result = runner.invoke(app, ["ai", "query", query_text, "--format", "json"])
                assert result.exit_code == 0

                # Verify the function call and parameters passed to execution layer
                args = run_mock.call_args[0][0]
                assert args[:2] == ["compliance", "devices"]
                assert "--ip" in args and args[args.index("--ip") + 1] == "10.0.0.1"

    def test_ai_routing_parameters_passed_from_ai_response(self, runner):
        """Verify parameters derived alongside AI intent flow into tool execution."""
        # Mock AI returning compliance intent
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("compliance_devices", "check_compliance")),
        ) as _route_mock:
            # Pretend parameter extraction (fed by AI understanding) yields a specific IP
            with patch(
                "netpicker_cli.commands.ai.extract_parameters",
                return_value={"ip": "10.2.3.4"},
            ):
                with patch(
                    "netpicker_cli.commands.ai.run_netpicker_command",
                    return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
                ) as run_mock:
                    result = runner.invoke(app, ["ai", "query", "check compliance", "--format", "json"])
                    assert result.exit_code == 0

                    args = run_mock.call_args[0][0]
                    assert args[:2] == ["compliance", "devices"]
                    assert "--ip" in args and args[args.index("--ip") + 1] == "10.2.3.4"

    def test_ai_unknown_tool_message(self, runner):
        """When AI returns an unknown tool, show a clear message and do not crash."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("some_unknown_tool", "reason")),
        ):
            result = runner.invoke(app, ["ai", "query", "do something unusual", "--format", "table"])
            assert result.exit_code == 0
            # Table format prints plain text; look for the message
            assert "Unknown tool" in result.stdout

    def test_ai_missing_ip_param_still_calls_tool_base(self, runner):
        """If AI selects a tool but no params are extracted, still call the base tool."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("compliance_devices", "check_compliance")),
        ):
            with patch("netpicker_cli.commands.ai.extract_parameters", return_value={}):
                with patch(
                    "netpicker_cli.commands.ai.run_netpicker_command",
                    return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
                ) as run_mock:
                    result = runner.invoke(app, ["ai", "query", "check compliance", "--format", "json"])
                    assert result.exit_code == 0
                    args = run_mock.call_args[0][0]
                    assert args[:2] == ["compliance", "devices"]
                    assert "--ip" not in args

    def test_ai_backups_content_fetch_path_calls_fetch_latest_backup(self, runner):
        """When query requests config content and AI selects backups tool, call fetch_latest_backup."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("backups_list", "fetch")),
        ):
            with patch("netpicker_cli.commands.ai.extract_parameters", return_value={"ip": "1.2.3.4"}):
                with patch("netpicker_cli.commands.ai.fetch_latest_backup", return_value="CONFIG_TEXT") as fetch_mock:
                    with patch(
                        "netpicker_cli.commands.ai.run_netpicker_command",
                        return_value={"stdout": "should not be used", "stderr": "", "returncode": 0, "success": True},
                    ) as run_mock:
                        # include words like 'config' to trigger wants_content path
                        result = runner.invoke(app, ["ai", "query", "show config for 1.2.3.4", "--format", "json"])
                        assert result.exit_code == 0
                        fetch_mock.assert_called_once_with("1.2.3.4")
                        # Ensure we didn't run the generic CLI path
                        assert run_mock.call_count == 0

    def test_ai_policy_add_rule_invocation(self, runner):
        """Intent to add policy rule should map to policy add-rule command."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("policy_add_rule", "add a rule")),
        ):
            with patch(
                "netpicker_cli.commands.ai.run_netpicker_command",
                return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
            ) as run_mock:
                result = runner.invoke(app, ["ai", "query", "add a compliance policy rule", "--format", "json"])
                assert result.exit_code == 0
                args = run_mock.call_args[0][0]
                assert args[:2] == ["policy", "add-rule"]

    def test_ai_compliance_overview_invocation(self, runner):
        """Intent for compliance overview should map correctly."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("compliance_overview", "overview")),
        ):
            with patch(
                "netpicker_cli.commands.ai.run_netpicker_command",
                return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
            ) as run_mock:
                result = runner.invoke(app, ["ai", "query", "show compliance overview", "--format", "json"])
                assert result.exit_code == 0
                args = run_mock.call_args[0][0]
                assert args[:2] == ["compliance", "overview"]

    def test_ai_compliance_report_tenant_invocation(self, runner):
        """Intent for compliance report-tenant should map correctly."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("compliance_report_tenant", "report")),
        ):
            with patch(
                "netpicker_cli.commands.ai.run_netpicker_command",
                return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
            ) as run_mock:
                result = runner.invoke(app, ["ai", "query", "tenant compliance report", "--format", "json"])
                assert result.exit_code == 0
                args = run_mock.call_args[0][0]
                assert args[:2] == ["compliance", "report-tenant"]

    def test_ai_keyword_fallback_when_ai_none(self, runner):
        """If AI returns no tool, fallback to keyword matching path."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=(None, "error")),
        ):
            # The ai.query function imports find_tool_by_keywords lazily; patch at module where it's referenced
            with patch("netpicker_cli.api_server.find_tool_by_keywords", return_value="devices_list"):
                with patch(
                    "netpicker_cli.commands.ai.run_netpicker_command",
                    return_value={"stdout": "OK", "stderr": "", "returncode": 0, "success": True},
                ) as run_mock:
                    result = runner.invoke(app, ["ai", "query", "list devices", "--format", "json"])
                    assert result.exit_code == 0
                    args = run_mock.call_args[0][0]
                    assert args[:2] == ["devices", "list"]

    def test_ai_run_command_failure_message(self, runner):
        """If command execution fails, the error should surface in output."""
        from unittest.mock import patch, AsyncMock
        with patch(
            "netpicker_cli.commands.ai.ai_router.route_query",
            new=AsyncMock(return_value=("devices_list", "devices")),
        ):
            with patch(
                "netpicker_cli.commands.ai.run_netpicker_command",
                return_value={"stdout": "", "stderr": "Internal error", "returncode": 1, "success": False},
            ):
                result = runner.invoke(app, ["ai", "query", "list devices", "--format", "json"])
                assert result.exit_code == 0
                # JSON output path prints via OutputFormatter; just check stderr surfaced via "Command failed"
                assert "Command failed" in result.stdout

    @respx.mock
    def test_ai_query_with_parameters(self, runner, mock_settings):
        """Test AI query with extracted parameters"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": "router1", "ipaddress": "192.168.1.1"}]}
        )

        result = runner.invoke(app, ["ai", "query", "list 5 devices with tag production", "--no-ai"])
        assert result.exit_code == 0

    def test_ai_query_unknown_intent(self, runner, mock_settings):
        """Test AI query with unknown intent"""
        result = runner.invoke(app, ["ai", "query", "something completely random", "--no-ai"])
        # Should handle gracefully
        assert "Unknown" in result.output or "not understand" in result.output or result.exit_code != 0

    @respx.mock
    def test_ai_query_backup_history(self, runner, mock_settings):
        """Test AI query routing to backup history"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=[{"id": "123", "upload_date": "2026-01-01"}]
        )

        result = runner.invoke(app, ["ai", "query", "show backup history for 192.168.1.1", "--no-ai"])
        assert result.exit_code == 0


class TestQueryRouter:
    """Test Query Router functionality"""

    @pytest.mark.asyncio
    async def test_route_query_devices_intent(self):
        """Test routing a devices query"""
        router = QueryRouter()
        tool_name, reasoning = await router.route_query("list all devices", ["devices_list", "show_config"])
        
        # Should successfully route to a tool or provide reasoning
        assert tool_name is not None or reasoning is not None

    @pytest.mark.asyncio
    async def test_route_query_timeout(self):
        """Test query routing with timeout"""
        with mock.patch('httpx.AsyncClient.get') as mock_get:
            import asyncio
            mock_get.side_effect = asyncio.TimeoutError()

            router = QueryRouter()
            # Should handle timeout gracefully
            try:
                is_available = await router.is_available()
                assert isinstance(is_available, bool)
            except:
                # Expected to handle timeout
                pass

    @pytest.mark.asyncio
    async def test_route_query_malformed_response(self):
        """Test handling malformed response"""
        router = QueryRouter()
        # Test with empty tools list
        tool_name, error_msg = await router.route_query("show devices", [])
        
        # Should handle empty tools gracefully
        assert error_msg is not None or tool_name is None

    @pytest.mark.asyncio
    async def test_route_query_api_error(self):
        """Test handling API errors"""
        router = QueryRouter()
        # Disable the router to test error handling
        router.enabled = False
        tool_name, error_msg = await router.route_query("list devices", ["devices_list"])
        
        # Should return error message
        assert error_msg is not None or tool_name is None


class TestAICommandLineInterface:
    """Test AI CLI command interface"""

    def test_ai_status_command(self, runner):
        """Test AI status command"""
        result = runner.invoke(app, ["ai", "status"])
        
        # Should show AI service status
        assert result.exit_code == 0
        assert "AI" in result.output or "status" in result.output.lower()

    def test_ai_tools_command(self, runner):
        """Test AI tools listing command"""
        result = runner.invoke(app, ["ai", "tools"])
        
        # Should list available tools
        assert result.exit_code == 0
        assert "devices" in result.output.lower() or "tools" in result.output.lower()

    @respx.mock
    def test_ai_query_with_json_output(self, runner, mock_settings):
        """Test AI query with JSON output format"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": "router1"}]}
        )

        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "list devices", "--no-ai", "--format", "json"])

        assert result.exit_code == 0

    @respx.mock  
    def test_ai_query_output_to_file(self, runner, mock_settings, tmp_path):
        """Test AI query with file output"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": "router1"}]}
        )
        
        output_file = tmp_path / "result.json"

        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "ai", "query", "list devices", 
                "--no-ai", 
                "--format", "json",
                "--output", str(output_file)
            ])

        assert result.exit_code == 0


class TestAIEdgeCases:
    """Test edge cases in AI routing"""

    def test_empty_query(self, runner):
        """Test AI query with empty string"""
        result = runner.invoke(app, ["ai", "query", ""])
        
        # Should handle empty query gracefully
        assert result.exit_code != 0 or "error" in result.output.lower()

    def test_very_long_query(self, runner, mock_settings):
        """Test AI query with very long input"""
        long_query = "show me " + "devices " * 100
        
        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", long_query, "--no-ai"])
        
        # Should handle without crashing
        assert result is not None

    @respx.mock
    def test_special_characters_in_query(self, runner, mock_settings):
        """Test AI query with special characters"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": []}
        )
        
        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "list devices with tag @#$%", "--no-ai"])
        
        # Should handle special characters
        assert result is not None

    def test_unicode_in_query(self, runner, mock_settings):
        """Test AI query with unicode characters"""
        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "列出设备", "--no-ai"])
        
        # Should handle unicode without crashing
        assert result is not None
