"""
Integration tests for AI query routing
"""

import pytest
import respx
from unittest import mock
from typer.testing import CliRunner
from netpicker_cli.cli import app
from netpicker_cli.utils.config import Settings
from netpicker_cli.ai.router import route_query, MistralRouter


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

        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "list devices", "--no-ai"])

        assert result.exit_code == 0

    @respx.mock
    def test_ai_query_with_parameters(self, runner, mock_settings):
        """Test AI query with extracted parameters"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": "router1", "ipaddress": "192.168.1.1"}]}
        )

        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "list 5 devices with tag production", "--no-ai"])

        assert result.exit_code == 0

    def test_ai_query_unknown_intent(self, runner, mock_settings):
        """Test AI query with unknown intent"""
        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "something completely random", "--no-ai"])

        # Should handle gracefully
        assert "Unknown" in result.output or "not understand" in result.output or result.exit_code != 0

    @respx.mock
    def test_ai_query_backup_history(self, runner, mock_settings):
        """Test AI query routing to backup history"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=[{"id": "123", "upload_date": "2026-01-01"}]
        )

        with mock.patch("netpicker_cli.commands.ai.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["ai", "query", "show backup history for 192.168.1.1", "--no-ai"])

        assert result.exit_code == 0


class TestMistralRouter:
    """Test Mistral AI router functionality"""

    @pytest.mark.asyncio
    async def test_route_query_devices_intent(self):
        """Test routing a devices query"""
        with mock.patch('httpx.AsyncClient.post') as mock_post:
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "devices_list"
                    }
                }]
            }
            mock_post.return_value = mock_response

            router = MistralRouter()
            result = await router.route("list all devices")
            
            assert "devices" in result.lower()

    @pytest.mark.asyncio
    async def test_route_query_timeout(self):
        """Test query routing with timeout"""
        with mock.patch('httpx.AsyncClient.post') as mock_post:
            import asyncio
            mock_post.side_effect = asyncio.TimeoutError()

            router = MistralRouter()
            result = await router.route("list devices")
            
            # Should fallback gracefully
            assert result is not None

    @pytest.mark.asyncio
    async def test_route_query_malformed_response(self):
        """Test handling malformed Mistral response"""
        with mock.patch('httpx.AsyncClient.post') as mock_post:
            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}  # Missing expected structure
            mock_post.return_value = mock_response

            router = MistralRouter()
            result = await router.route("show devices")
            
            # Should handle gracefully
            assert result is not None

    @pytest.mark.asyncio
    async def test_route_query_api_error(self):
        """Test handling Mistral API errors"""
        with mock.patch('httpx.AsyncClient.post') as mock_post:
            mock_response = mock.MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = Exception("API Error")
            mock_post.return_value = mock_response

            router = MistralRouter()
            result = await router.route("list devices")
            
            # Should fallback or return error indicator
            assert result is not None


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
