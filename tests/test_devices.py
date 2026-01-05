import json
import pytest
import respx
import httpx
from unittest.mock import patch
from typer.testing import CliRunner
from netpicker_cli.cli import app


class TestDevicesCommands:
    """Comprehensive tests for devices commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_settings(self, monkeypatch):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("NETPICKER_TENANT", "test-tenant")
        monkeypatch.setenv("NETPICKER_TOKEN", "test-token")

    @pytest.fixture
    def sample_devices(self):
        return [
            {
                "ipaddress": "192.168.1.1",
                "name": "router1",
                "platform": "cisco_ios",
                "tags": ["core", "production"]
            },
            {
                "ipaddress": "192.168.1.2",
                "name": "switch1",
                "platform": "arista_eos",
                "tags": ["access"]
            },
            {
                "ipaddress": "192.168.1.3",
                "name": "firewall1",
                "platform": "paloalto_panos",
                "tags": ["security", "production"]
            }
        ]

    @respx.mock
    def test_list_devices_basic_table(self, runner, mock_settings, sample_devices):
        """Test basic device listing with table output."""
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json={"items": sample_devices})
        )

        result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code == 0
        assert "192.168.1.1" in result.stdout
        assert "router1" in result.stdout
        assert "cisco_ios" in result.stdout
        assert "core,production" in result.stdout

    @respx.mock
    def test_list_devices_json_output(self, runner, mock_settings, sample_devices):
        """Test device listing with JSON output."""
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json={"items": sample_devices})
        )

        result = runner.invoke(app, ["devices", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 3
        assert data[0]["ipaddress"] == "192.168.1.1"
        assert data[0]["name"] == "router1"

    @respx.mock
    def test_list_devices_with_tag_filter(self, runner, mock_settings, sample_devices):
        """Test device listing with tag filter."""
        respx.post("https://api.example.com/api/v1/devices/test-tenant/by_tags").mock(
            return_value=httpx.Response(200, json={"items": [sample_devices[0], sample_devices[2]]})
        )

        result = runner.invoke(app, ["devices", "list", "--tag", "production"])
        assert result.exit_code == 0
        assert "192.168.1.1" in result.stdout
        assert "192.168.1.3" in result.stdout
        assert "192.168.1.2" not in result.stdout  # switch1 doesn't have production tag

    @respx.mock
    def test_list_devices_tag_filter_fallback(self, runner, mock_settings, sample_devices):
        """Test device listing with tag filter fallback when server-side fails."""
        # First call fails, should fallback to client-side filtering
        respx.post("https://api.example.com/api/v1/devices/test-tenant/by_tags").mock(
            return_value=httpx.Response(500)
        )
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json={"items": sample_devices})
        )

        result = runner.invoke(app, ["devices", "list", "--tag", "production"])
        assert result.exit_code == 0
        assert "192.168.1.1" in result.stdout
        assert "192.168.1.3" in result.stdout
        assert "192.168.1.2" not in result.stdout

    @respx.mock
    def test_list_devices_pagination(self, runner, mock_settings, sample_devices):
        """Test device listing with pagination."""
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json={"items": sample_devices[:2]})
        )

        result = runner.invoke(app, ["devices", "list", "--limit", "2", "--offset", "0"])
        assert result.exit_code == 0
        assert "192.168.1.1" in result.stdout
        assert "192.168.1.2" in result.stdout
        assert "192.168.1.3" not in result.stdout

    @respx.mock
    def test_list_devices_fetch_all(self, runner, mock_settings, sample_devices):
        """Test device listing with --all flag to fetch all pages."""
        # Mock multiple pages
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            side_effect=[
                httpx.Response(200, json={"items": sample_devices[:2]}),  # First page
                httpx.Response(200, json={"items": [sample_devices[2]]}),  # Second page
                httpx.Response(200, json={"items": []})  # Empty page to stop
            ]
        )

        result = runner.invoke(app, ["devices", "list", "--all", "--limit", "2"])
        assert result.exit_code == 0
        assert "192.168.1.1" in result.stdout
        assert "192.168.1.2" in result.stdout
        assert "192.168.1.3" in result.stdout

    @respx.mock
    def test_list_devices_limit_cap(self, runner, mock_settings, sample_devices, capsys):
        """Test that limit is capped at server maximum."""
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json={"items": sample_devices})
        )

        result = runner.invoke(app, ["devices", "list", "--limit", "2000"])
        assert result.exit_code == 0
        # Should show the cap message
        assert "limit capped to 1000" in result.stdout

    @respx.mock
    def test_show_device_table_output(self, runner, mock_settings):
        """Test showing a single device with table output."""
        device_data = {
            "ipaddress": "192.168.1.1",
            "name": "router1",
            "platform": "cisco_ios",
            "tags": ["core", "production"],
            "status": "reachable"
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").mock(
            return_value=httpx.Response(200, json=device_data)
        )

        result = runner.invoke(app, ["devices", "show", "192.168.1.1"])
        assert result.exit_code == 0
        assert "192.168.1.1" in result.stdout
        assert "router1" in result.stdout
        assert "cisco_ios" in result.stdout
        assert "core,production" in result.stdout
        assert "reachable" in result.stdout

    @respx.mock
    def test_show_device_json_output(self, runner, mock_settings):
        """Test showing a single device with JSON output."""
        device_data = {
            "ipaddress": "192.168.1.1",
            "name": "router1",
            "platform": "cisco_ios",
            "tags": ["core", "production"],
            "status": "reachable"
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").mock(
            return_value=httpx.Response(200, json=device_data)
        )

        result = runner.invoke(app, ["devices", "show", "192.168.1.1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ipaddress"] == "192.168.1.1"
        assert data["name"] == "router1"
        assert data["status"] == "reachable"

    @respx.mock
    def test_show_device_not_found(self, runner, mock_settings):
        """Test showing a device that doesn't exist."""
        from netpicker_cli.api.errors import NotFound
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.99").mock(
            side_effect=NotFound("Device not found")
        )

        result = runner.invoke(app, ["devices", "show", "192.168.1.99"])
        assert result.exit_code == 1
        assert "device '192.168.1.99' not found" in result.stdout

    @respx.mock
    def test_show_device_api_error(self, runner, mock_settings):
        """Test showing a device with API error."""
        from netpicker_cli.api.errors import ApiError
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").mock(
            side_effect=ApiError("Internal server error")
        )

        result = runner.invoke(app, ["devices", "show", "192.168.1.1"])
        assert result.exit_code == 1
        assert "API error: Internal server error" in result.stdout

    @respx.mock
    def test_create_device_basic(self, runner, mock_settings):
        """Test creating a device with required fields."""
        create_data = {
            "ipaddress": "192.168.1.4",
            "name": "router4",
            "platform": "cisco_ios",
            "vault": "default",
            "tags": []
        }
        created_device = {
            "ipaddress": "192.168.1.4",
            "name": "router4",
            "platform": "cisco_ios",
            "tags": []
        }

        respx.post("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(201, json=created_device)
        )

        result = runner.invoke(app, [
            "devices", "create", "192.168.1.4",
            "--name", "router4",
            "--platform", "cisco_ios",
            "--vault", "default"
        ])
        assert result.exit_code == 0
        assert "192.168.1.4" in result.stdout
        assert "router4" in result.stdout
        assert "cisco_ios" in result.stdout

    @respx.mock
    def test_create_device_with_tags(self, runner, mock_settings):
        """Test creating a device with tags."""
        created_device = {
            "ipaddress": "192.168.1.4",
            "name": "router4",
            "platform": "cisco_ios",
            "tags": ["test", "lab"]
        }

        respx.post("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(201, json=created_device)
        )

        result = runner.invoke(app, [
            "devices", "create", "192.168.1.4",
            "--name", "router4",
            "--platform", "cisco_ios",
            "--vault", "default",
            "--tags", "test,lab"
        ])
        assert result.exit_code == 0
        assert "test,lab" in result.stdout

    @respx.mock
    def test_create_device_json_output(self, runner, mock_settings):
        """Test creating a device with JSON output."""
        created_device = {
            "ipaddress": "192.168.1.4",
            "name": "router4",
            "platform": "cisco_ios",
            "tags": ["test"]
        }

        respx.post("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(201, json=created_device)
        )

        result = runner.invoke(app, [
            "devices", "create", "192.168.1.4",
            "--name", "router4",
            "--platform", "cisco_ios",
            "--vault", "default",
            "--tags", "test",
            "--json"
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ipaddress"] == "192.168.1.4"
        assert data["tags"] == ["test"]

    @respx.mock
    def test_delete_device_force(self, runner, mock_settings):
        """Test deleting a device with force flag."""
        respx.delete("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").mock(
            return_value=httpx.Response(204)
        )

        result = runner.invoke(app, ["devices", "delete", "192.168.1.1", "--force"])
        assert result.exit_code == 0
        assert "deleted" in result.stdout

    @respx.mock
    def test_delete_device_with_confirmation(self, runner, mock_settings):
        """Test deleting a device with user confirmation."""
        respx.delete("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").mock(
            return_value=httpx.Response(204)
        )

        with patch('typer.confirm', return_value=True):
            result = runner.invoke(app, ["devices", "delete", "192.168.1.1"])
        assert result.exit_code == 0
        assert "deleted" in result.stdout

    @respx.mock
    def test_delete_device_confirmation_denied(self, runner, mock_settings):
        """Test deleting a device when user denies confirmation."""
        with patch('typer.confirm', return_value=False):
            result = runner.invoke(app, ["devices", "delete", "192.168.1.1"])
        assert result.exit_code == 0
        assert "aborted" in result.stdout

    @respx.mock
    def test_delete_device_not_found(self, runner, mock_settings):
        """Test deleting a device that doesn't exist."""
        from netpicker_cli.api.errors import NotFound
        respx.delete("https://api.example.com/api/v1/devices/test-tenant/192.168.1.99").mock(
            side_effect=NotFound("Device not found")
        )

        result = runner.invoke(app, ["devices", "delete", "192.168.1.99", "--force"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    @respx.mock
    def test_delete_device_api_error(self, runner, mock_settings):
        """Test deleting a device with API error."""
        from netpicker_cli.api.errors import ApiError
        respx.delete("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1").mock(
            side_effect=ApiError("Internal server error")
        )

        result = runner.invoke(app, ["devices", "delete", "192.168.1.1", "--force"])
        assert result.exit_code == 1
        assert "error: Internal server error" in result.stdout