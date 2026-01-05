import pytest
import respx
from unittest import mock
from typer.testing import CliRunner
from netpicker_cli.cli import app
from netpicker_cli.utils.config import Settings


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


class TestBackupsCommands:
    """Test backups commands"""

    @respx.mock
    def test_recent_success(self, runner, mock_settings):
        """Test listing recent backups successfully"""
        recent_data = {
            "items": [
                {
                    "name": "router1",
                    "ipaddress": "192.168.1.1",
                    "id": "config-123",
                    "upload_date": "2026-01-05T10:00:00Z",
                    "file_size": 1024
                },
                {
                    "name": "router2",
                    "ipaddress": "192.168.1.2",
                    "id": "config-456",
                    "upload_date": "2026-01-05T09:00:00Z",
                    "file_size": 2048
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/recent-configs/").respond(
            json=recent_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "recent"])

        assert result.exit_code == 0
        assert "router1" in result.output
        assert "192.168.1.1" in result.output
        assert "config-123" in result.output

    @respx.mock
    def test_recent_json_output(self, runner, mock_settings):
        """Test listing recent backups with JSON output"""
        recent_data = {
            "items": [
                {
                    "name": "router1",
                    "ipaddress": "192.168.1.1",
                    "id": "config-123",
                    "upload_date": "2026-01-05T10:00:00Z",
                    "file_size": 1024
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/recent-configs/").respond(
            json=recent_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "recent", "--json"])

        assert result.exit_code == 0
        assert '"name": "router1"' in result.output

    @respx.mock
    def test_list_configs_success(self, runner, mock_settings):
        """Test listing configs for a device successfully"""
        configs_data = {
            "items": [
                {
                    "id": "config-123",
                    "created_at": "2026-01-05T10:00:00Z",
                    "size": 1024,
                    "digest": "abc123"
                },
                {
                    "id": "config-456",
                    "created_at": "2026-01-05T09:00:00Z",
                    "size": 2048,
                    "digest": "def456"
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=configs_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "list", "--ip", "192.168.1.1"])

        assert result.exit_code == 0
        assert "config-123" in result.output
        assert "1024" in result.output
        assert "abc123" in result.output

    @respx.mock
    def test_list_configs_json_output(self, runner, mock_settings):
        """Test listing configs for a device with JSON output"""
        configs_data = {
            "items": [
                {
                    "id": "config-123",
                    "created_at": "2026-01-05T10:00:00Z",
                    "size": 1024,
                    "digest": "abc123"
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=configs_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "list", "--ip", "192.168.1.1", "--json"])

        assert result.exit_code == 0
        assert '"id": "config-123"' in result.output

    @respx.mock
    def test_fetch_success(self, runner, mock_settings, tmp_path):
        """Test fetching a config successfully"""
        config_content = b"hostname router1\ninterface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n"
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs/config-123").respond(
            content=config_content
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "backups", "fetch",
                "--ip", "192.168.1.1",
                "--id", "config-123",
                "--output", str(tmp_path)
            ])

        assert result.exit_code == 0
        assert "saved:" in result.output
        assert "192.168.1.1-config-123.cfg" in result.output

        # Check file was created with correct content
        saved_file = tmp_path / "192.168.1.1-config-123.cfg"
        assert saved_file.exists()
        assert saved_file.read_bytes() == config_content

    @respx.mock
    def test_search_configs_success(self, runner, mock_settings):
        """Test searching configs successfully"""
        search_data = {
            "items": [
                {
                    "name": "router1",
                    "ipaddress": "192.168.1.1",
                    "id": "config-123",
                    "created_at": "2026-01-05T10:00:00Z",
                    "size": 1024
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/search-configs/").respond(
            json=search_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "search", "--q", "router1"])

        assert result.exit_code == 0
        assert "router1" in result.output
        assert "192.168.1.1" in result.output

    @respx.mock
    def test_search_configs_fallback_recent(self, runner, mock_settings):
        """Test searching configs with fallback to recent"""
        # Mock search endpoint to fail, then fallback to recent
        respx.get("https://api.example.com/api/v1/devices/test-tenant/search-configs/").mock(
            side_effect=Exception("Search not available")
        )
        recent_data = {
            "items": [
                {
                    "name": "router1",
                    "ipaddress": "192.168.1.1",
                    "id": "config-123",
                    "upload_date": "2026-01-05T10:00:00Z",
                    "file_size": 1024
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/recent-configs/").respond(
            json=recent_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "search", "--q", "router1"])

        assert result.exit_code == 0
        assert "router1" in result.output

    @respx.mock
    def test_backup_commands_success(self, runner, mock_settings):
        """Test listing backup commands successfully"""
        commands_data = {
            "cisco_ios": [
                "show running-config",
                "show version"
            ],
            "juniper": [
                "show configuration",
                "show version"
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/platform-commands/").respond(
            json=commands_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "commands"])

        assert result.exit_code == 0
        assert "cisco_ios" in result.output
        assert "show running-config" in result.output

    @respx.mock
    def test_backup_commands_platform_filter(self, runner, mock_settings):
        """Test listing backup commands with platform filter"""
        commands_data = {
            "cisco_ios": [
                "show running-config",
                "show version"
            ],
            "juniper": [
                "show configuration",
                "show version"
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/platform-commands/").respond(
            json=commands_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "commands", "--platform", "cisco_ios"])

        assert result.exit_code == 0
        assert "cisco_ios" in result.output
        assert "show running-config" in result.output
        assert "juniper" not in result.output

    @respx.mock
    def test_upload_config_success(self, runner, mock_settings, tmp_path):
        """Test uploading a config successfully"""
        config_file = tmp_path / "test_config.txt"
        config_file.write_text("hostname router1\ninterface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n")

        upload_response = {
            "config": {
                "id": "config-789",
                "upload_date": "2026-01-05T11:00:00Z",
                "file_size": 1024,
                "digest": "upload123"
            },
            "changed": False
        }
        respx.post("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=upload_response
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "backups", "upload",
                "192.168.1.1",
                "--file", str(config_file)
            ])

        assert result.exit_code == 0
        assert "config-789" in result.output
        assert "upload123" in result.output

    @respx.mock
    def test_upload_config_stdin(self, runner, mock_settings):
        """Test uploading a config from stdin"""
        upload_response = {
            "config": {
                "id": "config-789",
                "upload_date": "2026-01-05T11:00:00Z",
                "file_size": 1024,
                "digest": "upload123"
            },
            "changed": False
        }
        respx.post("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=upload_response
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "backups", "upload",
                "192.168.1.1",
                "--file", "-"
            ], input="hostname router1\ninterface GigabitEthernet0/1\n")

        assert result.exit_code == 0
        assert "config-789" in result.output

    @respx.mock
    def test_history_success(self, runner, mock_settings):
        """Test showing backup history successfully"""
        history_data = {
            "items": [
                {
                    "id": "config-123",
                    "timestamp": "2026-01-05T10:00:00Z",
                    "size": 1024,
                    "digest": "abc123",
                    "data": {
                        "variables": {
                            "os_version": "15.1"
                        }
                    }
                },
                {
                    "id": "config-456",
                    "timestamp": "2026-01-05T09:00:00Z",
                    "size": 2048,
                    "digest": "def456",
                    "data": {
                        "variables": {
                            "os_version": "15.1"
                        }
                    }
                }
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/config/history").respond(
            json=history_data
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "history", "192.168.1.1"])

        assert result.exit_code == 0
        assert "config-123" in result.output
        assert "15.1" in result.output

    @respx.mock
    def test_diff_configs_latest_two(self, runner, mock_settings):
        """Test diffing the latest two configs"""
        # Mock the configs list endpoint
        configs_data = {
            "items": [
                {"id": "config-2", "created_at": "2026-01-05T11:00:00Z"},
                {"id": "config-1", "created_at": "2026-01-05T10:00:00Z"}
            ]
        }
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs").respond(
            json=configs_data
        )

        # Mock the config download endpoints
        config1_content = b"hostname router1\ninterface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n"
        config2_content = b"hostname router1\ninterface GigabitEthernet0/1\n ip address 192.168.1.2 255.255.255.0\n"
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs/config-1").respond(
            content=config1_content
        )
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs/config-2").respond(
            content=config2_content
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["backups", "diff", "--ip", "192.168.1.1"])

        assert result.exit_code == 0
        assert "@@" in result.output  # Unified diff format
        assert "192.168.1.1" in result.output
        assert "192.168.1.2" in result.output

    @respx.mock
    def test_diff_configs_specific_ids(self, runner, mock_settings):
        """Test diffing specific config IDs"""
        # Mock the config download endpoints
        config1_content = b"hostname router1\ninterface GigabitEthernet0/1\n ip address 192.168.1.1 255.255.255.0\n"
        config2_content = b"hostname router1\ninterface GigabitEthernet0/1\n ip address 192.168.1.2 255.255.255.0\n"
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs/config-1").respond(
            content=config1_content
        )
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.1/configs/config-2").respond(
            content=config2_content
        )

        with mock.patch("netpicker_cli.commands.backups.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "backups", "diff",
                "--ip", "192.168.1.1",
                "--id-a", "config-1",
                "--id-b", "config-2"
            ])

        assert result.exit_code == 0
        assert "@@" in result.output  # Unified diff format
        assert "192.168.1.1" in result.output
        assert "192.168.1.2" in result.output