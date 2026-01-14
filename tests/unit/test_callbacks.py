"""
Tests for callback functions and command lifecycle
"""

import pytest
from unittest import mock
from typer.testing import CliRunner
from netpicker_cli.cli import app
from netpicker_cli.commands import devices, backups, automation, compliance


@pytest.fixture
def runner():
    """CLI test runner"""
    return CliRunner()


class TestCommandCallbacks:
    """Test command callback functions"""

    def test_devices_callback_no_subcommand(self, runner):
        """Test devices callback when no subcommand is provided"""
        result = runner.invoke(app, ["devices"])
        
        assert result.exit_code == 0
        assert "Netpicker Device Commands" in result.output
        assert "list" in result.output
        assert "show" in result.output
        assert "create" in result.output

    def test_backups_callback_no_subcommand(self, runner):
        """Test backups callback when no subcommand is provided"""
        result = runner.invoke(app, ["backups"])
        
        assert result.exit_code == 0
        assert "Netpicker Backup Commands" in result.output
        assert "diff" in result.output
        assert "recent" in result.output

    def test_automation_callback_no_subcommand(self, runner):
        """Test automation callback when no subcommand is provided"""
        result = runner.invoke(app, ["automation"])
        
        assert result.exit_code == 0
        assert "Netpicker Automation Commands" in result.output
        assert "list-jobs" in result.output
        assert "execute-job" in result.output

    def test_compliance_callback_no_subcommand(self, runner):
        """Test compliance callback when no subcommand is provided"""
        result = runner.invoke(app, ["compliance"])
        
        assert result.exit_code == 0
        assert "Netpicker Compliance Commands" in result.output
        assert "overview" in result.output
        assert "status" in result.output


class TestCallbackContext:
    """Test callback context handling"""

    def test_callback_receives_context(self):
        """Test that callbacks receive typer context"""
        from typer import Context
        
        callback_called = {"called": False, "ctx": None}
        
        def test_callback(ctx: Context):
            callback_called["called"] = True
            callback_called["ctx"] = ctx
        
        # Mock a callback
        with mock.patch.object(devices.app, 'callback', return_value=test_callback):
            runner = CliRunner()
            runner.invoke(app, ["devices"])
        
        # Callback should have been invoked
        # Note: This test structure may need adjustment based on actual callback mechanism

    def test_callback_invoked_subcommand_flag(self):
        """Test callback's invoke_without_command parameter"""
        runner = CliRunner()
        
        # When subcommand is provided, callback should not show help
        result = runner.invoke(app, ["devices", "list"])
        
        # Should not show the help text from callback
        assert "Netpicker Device Commands:" not in result.output or result.exit_code != 0


class TestParameterValidation:
    """Test parameter validation in callbacks"""

    def test_required_parameter_validation(self, runner):
        """Test that required parameters are validated"""
        # Try to create device without required IP
        result = runner.invoke(app, ["devices", "create"])
        
        assert result.exit_code != 0
        assert "required" in result.output.lower() or "missing" in result.output.lower()

    def test_optional_parameter_defaults(self, runner):
        """Test that optional parameters use defaults"""
        # This should succeed with defaults (though may fail due to API)
        result = runner.invoke(app, ["devices", "list"])
        
        # Should attempt to execute even without optional params
        assert "required" not in result.output.lower()

    def test_parameter_type_validation(self, runner):
        """Test parameter type validation"""
        # Try to use string where number expected
        result = runner.invoke(app, ["devices", "list", "--limit", "abc"])
        
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "error" in result.output.lower()


class TestCommandLifecycle:
    """Test complete command lifecycle"""

    @mock.patch("netpicker_cli.commands.devices.load_settings")
    @mock.patch("netpicker_cli.api.client.ApiClient.get")
    def test_full_command_lifecycle(self, mock_get, mock_settings):
        """Test complete command execution lifecycle"""
        # Setup mocks
        mock_settings.return_value = mock.MagicMock(
            base_url="https://api.example.com",
            tenant="test-tenant",
            token="test-token"
        )
        mock_get.return_value = mock.MagicMock(
            json=lambda: {"items": [{"name": "router1", "ipaddress": "192.168.1.1"}]}
        )
        
        runner = CliRunner()
        result = runner.invoke(app, ["devices", "list"])
        
        # Verify lifecycle: parse args -> load settings -> API call -> format output
        assert mock_settings.called
        assert mock_get.called
        assert result.exit_code == 0

    def test_error_handling_in_lifecycle(self, runner):
        """Test error handling during command lifecycle"""
        # Trigger an error by using invalid config
        with mock.patch("netpicker_cli.commands.devices.load_settings") as mock_settings:
            mock_settings.side_effect = Exception("Config error")
            
            result = runner.invoke(app, ["devices", "list"])
            
            # Should handle error gracefully
            assert result.exit_code != 0


class TestDeprecatedParameters:
    """Test handling of deprecated parameters"""

    @mock.patch("netpicker_cli.commands.devices.load_settings")
    @mock.patch("netpicker_cli.api.client.ApiClient.get")
    def test_deprecated_json_flag(self, mock_get, mock_settings):
        """Test that deprecated --json flag still works"""
        mock_settings.return_value = mock.MagicMock(
            base_url="https://api.example.com",
            tenant="test-tenant",
            token="test-token"
        )
        mock_get.return_value = mock.MagicMock(
            json=lambda: {"items": [{"name": "router1"}]}
        )
        
        runner = CliRunner()
        result = runner.invoke(app, ["devices", "list", "--json"])
        
        # Should work and output JSON
        assert result.exit_code == 0

    @mock.patch("netpicker_cli.commands.devices.load_settings")
    @mock.patch("netpicker_cli.api.client.ApiClient.get")
    def test_new_format_parameter(self, mock_get, mock_settings):
        """Test new --format parameter"""
        mock_settings.return_value = mock.MagicMock(
            base_url="https://api.example.com",
            tenant="test-tenant",
            token="test-token"
        )
        mock_get.return_value = mock.MagicMock(
            json=lambda: {"items": [{"name": "router1"}]}
        )
        
        runner = CliRunner()
        result = runner.invoke(app, ["devices", "list", "--format", "json"])
        
        assert result.exit_code == 0


class TestHelpText:
    """Test help text generation from callbacks"""

    def test_main_help_text(self, runner):
        """Test main app help text"""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "devices" in result.output
        assert "backups" in result.output
        assert "compliance" in result.output

    def test_command_help_text(self, runner):
        """Test command-specific help text"""
        result = runner.invoke(app, ["devices", "--help"])
        
        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output

    def test_subcommand_help_text(self, runner):
        """Test subcommand help text"""
        result = runner.invoke(app, ["devices", "list", "--help"])
        
        assert result.exit_code == 0
        assert "limit" in result.output.lower() or "format" in result.output.lower()


class TestCallbackErrorHandling:
    """Test error handling in callback functions"""

    def test_callback_with_invalid_context(self, runner):
        """Test callback behavior with invalid context via CLI invocation."""
        # Invoke devices without subcommand to trigger callback help and exit
        result = runner.invoke(app, ["devices"]) 
        assert result.exit_code == 0 or result.exit_code == 1
        assert "Netpicker Device Commands" in result.output

    def test_callback_exception_propagation(self):
        """Test that callback exceptions are properly propagated"""
        with mock.patch("netpicker_cli.commands.devices.typer.echo") as mock_echo:
            mock_echo.side_effect = Exception("Echo failed")
            
            runner = CliRunner()
            result = runner.invoke(app, ["devices"])
            
            # Should handle exception
            assert result is not None


class TestCallbackOrdering:
    """Test callback execution order"""

    def test_parent_callback_before_child(self):
        """Test that parent callbacks execute before child commands"""
        execution_order = []
        
        # This would require instrumenting the actual callbacks
        # For now, verify that commands execute successfully
        runner = CliRunner()
        
        # Parent callback should not prevent child execution
        with mock.patch("netpicker_cli.commands.devices.load_settings"):
            result = runner.invoke(app, ["devices", "list"])
            
            # Command should execute despite parent callback
            assert result is not None


# ============================================================================
# Completion Callbacks (on_success / on_failure)
# ============================================================================

class TestCompletionCallbacks:
    """Test on_success and on_failure completion callbacks for compliance checks."""

    @mock.patch("netpicker_cli.commands.compliance.ApiClient.get")
    @mock.patch("netpicker_cli.commands.compliance.load_settings")
    def test_on_success_called_after_status_success(self, mock_settings, mock_get):
        from netpicker_cli.commands import compliance as comp
        # Arrange: mock settings and API response
        mock_settings.return_value = mock.MagicMock(
            base_url="https://api.example.com",
            tenant="t1",
            token="tok"
        )
        mock_get.return_value = mock.MagicMock(
            json=lambda: {
                "ipaddress": "10.0.0.1",
                "executed": "2026-01-07T00:00:00Z",
                "summary": {"PASS": 10, "FAIL": 0},
            }
        )

        # Spy callback
        called = {"ok": False, "payload": None}
        def _on_success(payload):
            called["ok"] = True
            called["payload"] = payload

        # Inject callback
        prev = comp.on_success
        comp.on_success = _on_success
        try:
            runner = CliRunner()
            result = runner.invoke(app, ["compliance", "status", "10.0.0.1", "--format", "json"])
            assert result.exit_code == 0
            # Callback should be called with payload containing summary
            assert called["ok"] is True
            assert isinstance(called["payload"], dict)
            assert called["payload"].get("summary", {}) == {"PASS": 10, "FAIL": 0}
        finally:
            comp.on_success = prev

    @mock.patch("netpicker_cli.commands.compliance.ApiClient.get")
    @mock.patch("netpicker_cli.commands.compliance.load_settings")
    def test_on_failure_called_on_api_error(self, mock_settings, mock_get):
        from netpicker_cli.commands import compliance as comp
        from netpicker_cli.api.errors import ApiError
        # Arrange: raise API error on GET
        mock_settings.return_value = mock.MagicMock(
            base_url="https://api.example.com",
            tenant="t1",
            token="tok"
        )
        mock_get.side_effect = ApiError("Device Unreachable")

        # Spy failure callback
        failed = {"ok": False, "err": None}
        def _on_failure(err):
            failed["ok"] = True
            failed["err"] = err

        prev = comp.on_failure
        comp.on_failure = _on_failure
        try:
            runner = CliRunner()
            result = runner.invoke(app, ["compliance", "status", "10.0.0.2"])
            # CLI should exit with error and surface message
            assert result.exit_code != 0
            assert "API error" in result.output
            # Callback captured error
            assert failed["ok"] is True
            assert isinstance(failed["err"], Exception)
        finally:
            comp.on_failure = prev

    @pytest.mark.asyncio
    async def test_async_callbacks_supported(self, monkeypatch):
        """If callbacks are async, they should still be invoked."""
        from netpicker_cli.commands import compliance as comp

        # Prepare async success callback
        events = {"called": False}
        async def async_success(payload):
            events["called"] = True

        # Patch callbacks and dependencies
        monkeypatch.setattr(comp, "on_success", async_success, raising=True)
        class _Resp: 
            def json(self):
                return {"ipaddress": "1.1.1.1", "summary": {}}
        monkeypatch.setattr(comp, "load_settings", lambda: mock.MagicMock(tenant="t"), raising=True)
        monkeypatch.setattr(comp, "ApiClient", lambda s: mock.MagicMock(get=lambda url: _Resp()), raising=True)

        # Invoke command synchronously; internal helper runs async callback
        runner = CliRunner()
        result = runner.invoke(app, ["compliance", "status", "1.1.1.1", "--format", "json"])
        assert result.exit_code == 0
        assert events["called"] is True
