"""
Unit tests for core CLI commands: health, whoami, auth, devices, backups, compliance.

These tests mock load_settings() and ApiClient to test command logic in isolation,
without making any real HTTP calls. Each test verifies:
- Correct API endpoints are called
- Output formatting works for table and JSON modes
- Error paths raise appropriate exits
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from click.exceptions import Exit as ClickExit
from netpicker_cli.utils.config import Settings

runner = CliRunner()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _settings() -> Settings:
    """Standard mock Settings for every test."""
    return Settings(
        base_url="https://api.example.com",
        tenant="test-tenant",
        token="test-token",
    )


def _mock_api_client(json_responses: dict | list | None = None):
    """Return a MagicMock that behaves like ApiClient.

    `json_responses` – if provided, `.get(...).json()` returns this value.
    """
    cli = MagicMock()
    if json_responses is not None:
        cli.get.return_value.json.return_value = json_responses
    cli.post.return_value.json.return_value = {}
    return cli


# ============================================================================
# Health command
# ============================================================================

class TestHealthCommand:

    @patch("netpicker_cli.commands.health.ApiClient")
    @patch("netpicker_cli.commands.health.load_settings")
    def test_health_ok(self, mock_ls, mock_cli_cls):
        """Health check should return OK status."""
        mock_ls.return_value = _settings()
        client = _mock_api_client({"ok": True, "api_base": "https://api.example.com", "tz": "UTC"})
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.health import HealthCommand
        cmd = HealthCommand()
        result = cmd.execute()
        assert result["status"] == "OK"
        assert isinstance(result["response_time_ms"], int)

    @patch("netpicker_cli.commands.health.ApiClient")
    @patch("netpicker_cli.commands.health.load_settings")
    def test_health_returns_dict(self, mock_ls, mock_cli_cls):
        """HealthCommand.execute() should return a dict with expected keys."""
        mock_ls.return_value = _settings()
        client = _mock_api_client({"ok": True})
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.health import HealthCommand
        cmd = HealthCommand()
        result = cmd.execute()

        assert "response_time_ms" in result
        assert "status" in result
        assert result["status"] == "OK"

    @patch("netpicker_cli.commands.health.ApiClient")
    @patch("netpicker_cli.commands.health.load_settings")
    def test_health_api_error(self, mock_ls, mock_cli_cls):
        """Health command should propagate API errors."""
        mock_ls.return_value = _settings()
        client = MagicMock()
        client.get.side_effect = ConnectionError("timeout")
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.health import HealthCommand
        cmd = HealthCommand()
        with pytest.raises(ConnectionError):
            cmd.execute()


# ============================================================================
# Whoami command
# ============================================================================

class TestWhoamiCommand:

    def _make_jwt(self, payload: dict) -> str:
        """Build a fake unsigned JWT with the given payload."""
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        return f"{header}.{body}.sig"

    @patch("netpicker_cli.commands.whoami.load_settings")
    def test_whoami_decodes_email(self, mock_ls):
        """Whoami should extract email from JWT claims."""
        token = self._make_jwt({"claims": {"email": "alice@net.co"}, "scopes": ["read"]})
        s = _settings()
        s.token = token
        mock_ls.return_value = s

        from netpicker_cli.commands.whoami import WhoamiCommand
        cmd = WhoamiCommand()
        result = cmd.execute()

        assert result["email"] == "alice@net.co"
        assert result["base_url"] == "https://api.example.com"
        assert result["tenant"] == "test-tenant"

    @patch("netpicker_cli.commands.whoami.load_settings")
    def test_whoami_bad_token(self, mock_ls):
        """Whoami should handle non-JWT tokens gracefully."""
        s = _settings()
        s.token = "not-a-jwt"
        mock_ls.return_value = s

        from netpicker_cli.commands.whoami import WhoamiCommand
        cmd = WhoamiCommand()
        result = cmd.execute()

        assert result["email"] is None

    @patch("netpicker_cli.commands.whoami.load_settings")
    def test_whoami_json_format(self, mock_ls, capsys):
        """Whoami --format json should emit valid JSON."""
        token = self._make_jwt({"sub": "bob@net.co"})
        s = _settings()
        s.token = token
        mock_ls.return_value = s

        from netpicker_cli.commands.whoami import WhoamiCommand
        cmd = WhoamiCommand(format="json")
        cmd.run()

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["email"] == "bob@net.co"

    def test_decode_jwt_unverified_invalid(self):
        """Static helper should return {} for garbage tokens."""
        from netpicker_cli.commands.whoami import WhoamiCommand
        assert WhoamiCommand._decode_jwt_unverified("") == {}
        assert WhoamiCommand._decode_jwt_unverified("x.y") == {}
        assert WhoamiCommand._decode_jwt_unverified("a.!!!.c") == {}

    @patch("netpicker_cli.commands.whoami.load_settings")
    def test_whoami_scopes_extraction(self, mock_ls):
        """Whoami should extract scopes list from JWT."""
        token = self._make_jwt({"sub": "user@net.co", "scopes": ["admin", "read", "write"]})
        s = _settings()
        s.token = token
        mock_ls.return_value = s

        from netpicker_cli.commands.whoami import WhoamiCommand
        cmd = WhoamiCommand()
        result = cmd.execute()

        assert result["scopes"] == ["admin", "read", "write"]


# ============================================================================
# Auth command
# ============================================================================

class TestAuthCommand:

    def test_login_normalizes_url(self):
        """LoginCommand should add https:// and strip trailing slash."""
        from netpicker_cli.commands.auth import LoginCommand
        cmd = LoginCommand(base_url="example.com/", tenant="t", token="tok")
        assert cmd._normalize_base_url("example.com/") == "https://example.com"
        assert cmd._normalize_base_url("http://a.io/") == "http://a.io"

    def test_login_validates_empty_url(self):
        """LoginCommand should reject empty base URL."""
        from netpicker_cli.commands.auth import LoginCommand
        import typer
        cmd = LoginCommand(base_url="", tenant="t", token="tok")
        with pytest.raises(typer.BadParameter):
            cmd.validate_args()

    @patch("netpicker_cli.commands.auth.save_config")
    def test_login_execute(self, mock_save):
        """LoginCommand execute should call save_config and return result."""
        mock_save.return_value = True
        from netpicker_cli.commands.auth import LoginCommand
        cmd = LoginCommand(base_url="https://api.test.com", tenant="t", token="secret")
        result = cmd.execute()

        assert result["base_url"] == "https://api.test.com"
        assert result["tenant"] == "t"
        assert result["keyring_saved"] is True
        mock_save.assert_called_once()

    @patch("netpicker_cli.commands.auth.clear_config")
    def test_logout_clears_config(self, mock_clear):
        """LogoutCommand should call clear_config."""
        mock_clear.return_value = True
        from netpicker_cli.commands.auth import LogoutCommand
        cmd = LogoutCommand()
        result = cmd.execute()
        assert result["removed_config"] is True
        mock_clear.assert_called_once()


# ============================================================================
# Devices command
# ============================================================================

class TestDevicesCommand:

    @patch("netpicker_cli.commands.devices.ApiClient")
    @patch("netpicker_cli.commands.devices.load_settings")
    def test_list_devices_json(self, mock_ls, mock_cli_cls, capsys):
        """devices list --format json should output JSON array."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([
            {"ipaddress": "10.0.0.1", "name": "switch01", "platform": "cisco_ios", "tags": ["core"]},
            {"ipaddress": "10.0.0.2", "name": "switch02", "platform": "cisco_nxos", "tags": []},
        ])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.devices import list_devices
        list_devices(
            tag=None, json_out=False, format="json", output_file=None,
            limit=50, offset=0, all_=False, parallel=0, no_cache=True,
        )

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["ipaddress"] == "10.0.0.1"

    @patch("netpicker_cli.commands.devices.ApiClient")
    @patch("netpicker_cli.commands.devices.load_settings")
    def test_list_devices_table(self, mock_ls, mock_cli_cls, capsys):
        """devices list should output a table by default."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([
            {"ipaddress": "192.168.1.1", "name": "router01", "platform": "cisco_ios", "tags": ["wan"]},
        ])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.devices import list_devices
        list_devices(
            tag=None, json_out=False, format="table", output_file=None,
            limit=50, offset=0, all_=False, parallel=0, no_cache=True,
        )

        out = capsys.readouterr().out
        assert "router01" in out
        assert "192.168.1.1" in out

    @patch("netpicker_cli.commands.devices.ApiClient")
    @patch("netpicker_cli.commands.devices.load_settings")
    def test_list_devices_empty(self, mock_ls, mock_cli_cls, capsys):
        """devices list with no devices should handle empty list."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.devices import list_devices
        list_devices(
            tag=None, json_out=False, format="json", output_file=None,
            limit=50, offset=0, all_=False, parallel=0, no_cache=True,
        )

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data == []

    @patch("netpicker_cli.commands.devices.ApiClient")
    @patch("netpicker_cli.commands.devices.load_settings")
    def test_list_devices_limit_cap(self, mock_ls, mock_cli_cls):
        """Limit >1000 should raise ValidationError."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.devices import list_devices
        from netpicker_cli.utils.validation import ValidationError
        with pytest.raises(ValidationError, match="limit cannot exceed 1000"):
            list_devices(
                tag=None, json_out=False, format="json", output_file=None,
                limit=5000, offset=0, all_=False, parallel=0, no_cache=True,
            )


# ============================================================================
# Backups command
# ============================================================================

class TestBackupsCommand:

    @patch("netpicker_cli.commands.backups.ApiClient")
    @patch("netpicker_cli.commands.backups.load_settings")
    def test_recent_json(self, mock_ls, mock_cli_cls, capsys):
        """backups recent --format json should output a JSON list."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([
            {"name": "router01", "ipaddress": "10.0.0.1", "id": "cfg-1", "created_at": "2025-01-01"},
        ])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.backups import recent
        recent(limit=10, json_out=False, format="json", output_file=None)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert data[0]["name"] == "router01"

    @patch("netpicker_cli.commands.backups.ApiClient")
    @patch("netpicker_cli.commands.backups.load_settings")
    def test_recent_table(self, mock_ls, mock_cli_cls, capsys):
        """backups recent table format should contain device info."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([
            {"name": "sw01", "ipaddress": "10.0.0.5", "id": "c-2", "created_at": "2025-01-02", "platform": "cisco_ios"},
        ])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.backups import recent
        recent(limit=10, json_out=False, format="table", output_file=None)

        out = capsys.readouterr().out
        assert "sw01" in out
        assert "10.0.0.5" in out

    @patch("netpicker_cli.commands.backups.ApiClient")
    @patch("netpicker_cli.commands.backups.load_settings")
    def test_diff_needs_two_configs(self, mock_ls, mock_cli_cls):
        """backups diff should exit with code 2 when fewer than 2 configs exist."""
        mock_ls.return_value = _settings()
        client = _mock_api_client([{"id": "only-one"}])
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.backups import diff_configs
        with pytest.raises(ClickExit) as exc_info:
            diff_configs(
                ip="10.0.0.1", id_a="", id_b="",
                context=3, json_out=False, format="table", output_file=None,
            )
        assert exc_info.value.exit_code == 2


# ============================================================================
# Compliance command
# ============================================================================

class TestComplianceCommand:

    @patch("netpicker_cli.commands.compliance.ApiClient")
    @patch("netpicker_cli.commands.compliance.load_settings")
    def test_overview_json(self, mock_ls, mock_cli_cls, capsys):
        """compliance overview --format json should output valid JSON."""
        mock_ls.return_value = _settings()
        client = _mock_api_client({
            "total_devices": 10,
            "compliant": 8,
            "non_compliant": 2,
        })
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.compliance import overview
        overview(json_out=False, format="json", output_file=None)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["total_devices"] == 10

    @patch("netpicker_cli.commands.compliance.ApiClient")
    @patch("netpicker_cli.commands.compliance.load_settings")
    def test_overview_api_error_exits(self, mock_ls, mock_cli_cls):
        """compliance overview should exit(1) on API error."""
        from netpicker_cli.api.errors import ApiError

        mock_ls.return_value = _settings()
        client = MagicMock()
        client.get.side_effect = ApiError("forbidden")
        mock_cli_cls.return_value = client

        from netpicker_cli.commands.compliance import overview
        with pytest.raises(ClickExit) as exc_info:
            overview(json_out=False, format="table", output_file=None)
        assert exc_info.value.exit_code == 1


# ============================================================================
# Config / load_settings validation
# ============================================================================

class TestConfigValidation:

    def test_missing_base_url_exits(self, monkeypatch, tmp_path):
        """load_settings should exit when NETPICKER_BASE_URL is missing."""
        monkeypatch.delenv("NETPICKER_BASE_URL", raising=False)
        monkeypatch.delenv("NETPICKER_TENANT", raising=False)
        monkeypatch.delenv("NETPICKER_TOKEN", raising=False)

        # Point config at a non-existent file so file-based config also fails
        import netpicker_cli.utils.config as cfg_mod
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / "nope.json")

        with pytest.raises(SystemExit) as exc:
            cfg_mod.load_settings()
        assert "base URL" in str(exc.value).lower() or "base_url" in str(exc.value).lower()

    def test_missing_tenant_exits(self, monkeypatch, tmp_path):
        """load_settings should exit when NETPICKER_TENANT is missing."""
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://api.example.com")
        monkeypatch.delenv("NETPICKER_TENANT", raising=False)
        monkeypatch.delenv("NETPICKER_TOKEN", raising=False)

        import netpicker_cli.utils.config as cfg_mod
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / "nope.json")

        with pytest.raises(SystemExit) as exc:
            cfg_mod.load_settings()
        assert "tenant" in str(exc.value).lower()

    def test_valid_env_loads_ok(self, monkeypatch):
        """load_settings should succeed with all env vars set."""
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://api.test.com")
        monkeypatch.setenv("NETPICKER_TENANT", "my-tenant")
        monkeypatch.setenv("NETPICKER_TOKEN", "tok123")

        from netpicker_cli.utils.config import load_settings
        s = load_settings()
        assert s.base_url == "https://api.test.com"
        assert s.tenant == "my-tenant"


# ============================================================================
# Progress utility
# ============================================================================

class TestProgressUtility:

    def test_progress_bar_fallback(self):
        """progress_bar should yield items even when disabled."""
        from netpicker_cli.utils.progress import progress_bar
        data = [1, 2, 3, 4]
        result = list(progress_bar(data, desc="test", disable=True))
        assert result == [1, 2, 3, 4]

    def test_page_progress_counting(self, capsys):
        """page_progress tick should accumulate counts."""
        from netpicker_cli.utils.progress import page_progress
        with page_progress("Fetching", quiet=True) as tick:
            tick(10)
            tick(20)
        # quiet mode means no tqdm output; just verify it doesn't crash


# ============================================================================
# CLI smoke tests via CliRunner
# ============================================================================

class TestCliSmoke:

    def test_version_flag(self):
        """--version should print version string and exit 0."""
        from netpicker_cli.cli import app
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "netpicker-cli version" in result.output

    def test_no_args_shows_help(self):
        """Running with no args should show help/usage text."""
        from netpicker_cli.cli import app
        result = runner.invoke(app, [])
        # no_args_is_help=True causes exit code 0 or 2 depending on typer version
        assert result.exit_code in (0, 2)
        assert "Usage" in result.output or "usage" in result.output.lower()

    def test_help_flag(self):
        """--help should show help and exit 0."""
        from netpicker_cli.cli import app
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "health" in result.output
        assert "devices" in result.output

    @patch("netpicker_cli.commands.health.ApiClient")
    @patch("netpicker_cli.commands.health.load_settings")
    def test_health_via_cli(self, mock_ls, mock_cli_cls):
        """'netpicker health' via CliRunner should work."""
        mock_ls.return_value = _settings()
        client = _mock_api_client({"ok": True})
        mock_cli_cls.return_value = client

        from netpicker_cli.cli import app
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "OK" in result.output
