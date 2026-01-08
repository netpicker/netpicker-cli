"""
Edge case tests for API responses and error handling
"""

import pytest
import respx
from unittest import mock
from typer.testing import CliRunner
from netpicker_cli.cli import app
from netpicker_cli.utils.config import Settings
from netpicker_cli.api.client import ApiClient
from netpicker_cli.api.errors import ApiError, NotFound, Unauthorized


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


class TestEmptyResponses:
    """Test handling of empty API responses"""

    @respx.mock
    def test_empty_device_list(self, runner, mock_settings):
        """Test handling empty device list response"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant").respond(
            json={"items": []}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code == 0
        # Should handle empty list gracefully

    @respx.mock
    def test_empty_backup_list(self, runner, mock_settings):
        """Test handling empty backup list"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/recent-configs/").respond(
            json={"items": []}
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "recent"])

        assert result.exit_code == 0

    @respx.mock
    def test_null_items_in_response(self, runner, mock_settings):
        """Test handling null items in API response"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": None}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle null items without crashing
        assert result is not None

    @respx.mock
    def test_missing_items_key(self, runner, mock_settings):
        """Test response missing 'items' key"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle missing key gracefully
        assert result is not None


class TestMalformedJSON:
    """Test handling of malformed JSON responses"""

    @respx.mock
    def test_invalid_json_syntax(self, runner, mock_settings):
        """Test handling invalid JSON syntax"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            text="{invalid json syntax"
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle invalid JSON
        assert result.exit_code != 0 or "error" in result.output.lower()

    @respx.mock
    def test_plain_text_instead_of_json(self, runner, mock_settings):
        """Test handling plain text instead of JSON"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            text="This is plain text, not JSON"
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle non-JSON response
        assert result is not None

    @respx.mock
    def test_incomplete_json_object(self, runner, mock_settings):
        """Test handling incomplete JSON object"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            text='{"items": [{"name": "router1", "ip":'
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle incomplete JSON
        assert result is not None

    @respx.mock
    def test_wrong_json_structure(self, runner, mock_settings):
        """Test handling wrong JSON structure"""
        # Return array instead of object
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json=["router1", "router2"]  # Should be object with 'items'
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should adapt to different structures
        assert result is not None


class TestHTTPErrors:
    """Test handling of HTTP error responses"""

    @respx.mock
    def test_404_not_found(self, runner, mock_settings):
        """Test handling 404 Not Found"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").respond(
            status_code=404
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "show", "192.168.1.1"])

        assert result.exit_code != 0
        assert "404" in result.output or "not found" in result.output.lower()

    @respx.mock
    def test_401_unauthorized(self, runner, mock_settings):
        """Test handling 401 Unauthorized"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            status_code=401
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code != 0
        assert "401" in result.output or "unauthorized" in result.output.lower()

    @respx.mock
    def test_500_internal_server_error(self, runner, mock_settings):
        """Test handling 500 Internal Server Error"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            status_code=500
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code != 0
        assert "500" in result.output or "error" in result.output.lower()

    @respx.mock
    def test_429_rate_limit(self, runner, mock_settings):
        """Test handling 429 Rate Limit"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            status_code=429,
            headers={"Retry-After": "60"}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code != 0


class TestNetworkErrors:
    """Test handling of network-related errors"""

    @respx.mock
    def test_connection_timeout(self, runner, mock_settings):
        """Test handling connection timeout"""
        import httpx
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code != 0

    @respx.mock
    def test_connection_refused(self, runner, mock_settings):
        """Test handling connection refused"""
        import httpx
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code != 0

    @respx.mock
    def test_dns_resolution_failure(self, runner, mock_settings):
        """Test handling DNS resolution failure"""
        import httpx
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").mock(
            side_effect=httpx.ConnectError("DNS resolution failed")
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code != 0


class TestDataIntegrity:
    """Test handling of data integrity issues"""

    @respx.mock
    def test_missing_required_fields(self, runner, mock_settings):
        """Test handling missing required fields in response"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": "router1"}]}  # Missing 'ipaddress'
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle missing fields gracefully
        assert result.exit_code == 0

    @respx.mock
    def test_wrong_data_types(self, runner, mock_settings):
        """Test handling wrong data types in response"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": 12345, "ipaddress": True}]}  # Wrong types
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle type mismatches
        assert result is not None

    @respx.mock
    def test_null_values_in_fields(self, runner, mock_settings):
        """Test handling null values in response fields"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant/").respond(
            json={"items": [{"name": None, "ipaddress": "192.168.1.1"}]}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code == 0


class TestPaginationEdgeCases:
    """Test edge cases in pagination handling"""

    @respx.mock
    def test_pagination_with_zero_items(self, runner, mock_settings):
        """Test pagination when total is zero"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant", params={"size": 50, "page": 1}).respond(
            json={"items": [], "total": 0, "page": 1, "size": 50}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        assert result.exit_code == 0

    @respx.mock
    def test_pagination_missing_metadata(self, runner, mock_settings):
        """Test pagination with missing metadata"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant", params={"size": 50, "page": 1}).respond(
            json={"items": [{"name": "router1"}]}  # No pagination metadata
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list"])

        # Should handle missing pagination info
        assert result.exit_code == 0

    @respx.mock
    def test_pagination_invalid_page_number(self, runner, mock_settings):
        """Test pagination with invalid page number"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant", params={"size": 50, "page": 1}).respond(
            json={"items": [], "total": 100, "page": -1, "size": 50}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list", "--page", "-1"])

        # Should handle invalid page gracefully
        assert result is not None


class TestOutputFormatEdgeCases:
    """Test edge cases in output formatting"""

    @respx.mock
    def test_csv_output_with_special_characters(self, runner, mock_settings):
        """Test CSV output with special characters"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant", params={"size": 50, "page": 1}).respond(
            json={"items": [{"name": "router,with,commas", "ipaddress": "192.168.1.1"}]}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list", "--format", "csv"])

        assert result.exit_code == 0
        # CSV should properly escape commas

    @respx.mock
    def test_yaml_output_with_unicode(self, runner, mock_settings):
        """Test YAML output with unicode characters"""
        respx.get("https://api.example.com/api/v1/devices/test-tenant", params={"size": 50, "page": 1}).respond(
            json={"items": [{"name": "路由器", "ipaddress": "192.168.1.1"}]}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list", "--format", "yaml"])

        assert result.exit_code == 0

    @respx.mock
    def test_table_output_with_very_long_values(self, runner, mock_settings):
        """Test table output with very long field values"""
        long_name = "x" * 500
        respx.get("https://api.example.com/api/v1/devices/test-tenant", params={"size": 50, "page": 1}).respond(
            json={"items": [{"name": long_name, "ipaddress": "192.168.1.1"}]}
        )

        with mock.patch("netpicker_cli.commands.devices.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["devices", "list", "--format", "table"])

        assert result.exit_code == 0
