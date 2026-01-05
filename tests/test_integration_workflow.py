import json
import pytest
import respx
import httpx
import tempfile
import os
from unittest.mock import patch
from typer.testing import CliRunner
from netpicker_cli.cli import app


class TestDeviceComplianceWorkflow:
    """Integration test for complete device and compliance workflow."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_settings(self, monkeypatch):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("NETPICKER_TENANT", "test-tenant")
        monkeypatch.setenv("NETPICKER_TOKEN", "test-token")

    @pytest.fixture
    def sample_device(self):
        return {
            "ipaddress": "192.168.1.100",
            "name": "test-router",
            "platform": "cisco_ios",
            "vault": "default",
            "tags": ["test", "integration"]
        }

    @pytest.fixture
    def sample_config(self):
        return """!
version 15.1
!
hostname test-router
!
interface GigabitEthernet0/0
 ip address 192.168.1.100 255.255.255.0
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
 shutdown
!
line con 0
 password cisco
!
end
"""

    @pytest.fixture
    def sample_policy(self):
        return {
            "id": "test-policy-123",
            "name": "Test Integration Policy",
            "description": "Policy for integration testing",
            "enabled": True,
            "rules": []
        }

    @respx.mock
    def test_complete_device_compliance_workflow(
        self, runner, mock_settings, sample_device, sample_config, sample_policy
    ):
        """Test complete workflow: device creation, config upload, policy/rule management, cleanup."""

        # Step 1: Create device
        create_response = {**sample_device, "id": "device-123"}
        respx.post("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(201, json=create_response)
        )

        result = runner.invoke(app, [
            "devices", "create", sample_device["ipaddress"],
            "--name", sample_device["name"],
            "--platform", sample_device["platform"],
            "--vault", sample_device["vault"],
            "--tags", ",".join(sample_device["tags"])
        ])
        assert result.exit_code == 0
        assert sample_device["ipaddress"] in result.stdout

        # Step 2: Verify device appears in list
        list_response = {"items": [create_response]}
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json=list_response)
        )

        result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code == 0
        assert sample_device["ipaddress"] in result.stdout
        assert sample_device["name"] in result.stdout

        # Step 3: Upload config for device
        upload_response = {
            "config": {
                "id": "config-456",
                "upload_date": "2024-01-01T00:00:00Z",
                "file_size": len(sample_config),
                "digest": "abc123"
            },
            "changed": False
        }
        respx.post("https://api.example.com/api/v1/devices/test-tenant/192.168.1.100/configs").mock(
            return_value=httpx.Response(201, json=upload_response)
        )

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(sample_config)
            config_file = f.name

        try:
            result = runner.invoke(app, [
                "backups", "upload", sample_device["ipaddress"],
                "--file", config_file
            ])
            assert result.exit_code == 0
            assert "config-456" in result.stdout
        finally:
            os.unlink(config_file)

        # Step 4: Create compliance policy
        policy_create_response = sample_policy.copy()
        respx.post("https://api.example.com/api/v1/policy/test-tenant").mock(
            return_value=httpx.Response(201, json=policy_create_response)
        )

        result = runner.invoke(app, [
            "policy", "create",
            "--name", sample_policy["name"],
            "--description", sample_policy["description"]
        ])
        assert result.exit_code == 0

        # Step 5: Add rule to policy (passing rule - check for hostname)
        rule_add_response = {
            "name": "hostname-check",
            "description": "Check hostname configuration",
            "ruleset": "default",
            "severity": "HIGH",
            "platform": ["cisco_ios"],
            "simplified": {
                "text": "hostname test-router",
                "regex": False,
                "invert": False
            }
        }
        respx.post("https://api.example.com/api/v1/policy/test-tenant/test-policy-123/rule/").mock(
            return_value=httpx.Response(200, json=rule_add_response)
        )

        result = runner.invoke(app, [
            "policy", "add-rule", sample_policy["id"],
            "--name", "hostname-check",
            "--simplified-text", "hostname test-router"
        ])
        assert result.exit_code == 0

        # Step 6: Test rule that passes
        test_pass_response = {
            "result": {
                "outcome": "PASS",
                "rule_name": "hostname-check",
                "exec_at": "2024-01-01T00:00:00Z"
            },
            "errors": []
        }
        respx.post("https://api.example.com/api/v1/policy/test-tenant/test-policy-123/debug").mock(
            return_value=httpx.Response(200, json=test_pass_response)
        )

        result = runner.invoke(app, [
            "policy", "test-rule", sample_policy["id"],
            "--name", "hostname-check",
            "--ip", sample_device["ipaddress"],
            "--config", sample_config
        ])
        assert result.exit_code == 0
        assert "PASS" in result.stdout

        # Step 7: Add rule that fails (check for non-existent interface)
        rule_fail_response = {
            "name": "interface-check",
            "description": "Check for specific interface",
            "ruleset": "default",
            "severity": "HIGH",
            "platform": ["cisco_ios"],
            "simplified": {
                "text": "interface GigabitEthernet0/2",
                "regex": False,
                "invert": False
            }
        }
        respx.post("https://api.example.com/api/v1/policy/test-tenant/test-policy-123/rule/").mock(
            return_value=httpx.Response(200, json=rule_fail_response)
        )

        result = runner.invoke(app, [
            "policy", "add-rule", sample_policy["id"],
            "--name", "interface-check",
            "--simplified-text", "interface GigabitEthernet0/2"
        ])
        assert result.exit_code == 0

        # Test rule that fails
        test_fail_response = {
            "result": {
                "outcome": "FAIL",
                "rule_name": "interface-check",
                "exec_at": "2024-01-01T00:00:00Z"
            },
            "errors": []
        }
        respx.post("https://api.example.com/api/v1/policy/test-tenant/test-policy-123/debug").mock(
            return_value=httpx.Response(200, json=test_fail_response)
        )

        result = runner.invoke(app, [
            "policy", "test-rule", sample_policy["id"],
            "--name", "interface-check",
            "--ip", sample_device["ipaddress"],
            "--config", sample_config
        ])
        assert result.exit_code == 0
        assert "FAIL" in result.stdout

        # Step 8: Remove the failing rule
        respx.delete("https://api.example.com/api/v1/policy/test-tenant/test-policy-123/rule/interface-check").mock(
            return_value=httpx.Response(204)
        )

        result = runner.invoke(app, [
            "policy", "remove-rule", sample_policy["id"], "interface-check"
        ])
        assert result.exit_code == 0

        # Step 9: Disable policy (since delete doesn't exist)
        policy_update_response = sample_policy.copy()
        policy_update_response["enabled"] = False
        respx.patch("https://api.example.com/api/v1/policy/test-tenant/test-policy-123").mock(
            return_value=httpx.Response(200, json=policy_update_response)
        )

        result = runner.invoke(app, [
            "policy", "update", sample_policy["id"], "--disabled"
        ])
        assert result.exit_code == 0

        # Step 10: Delete device
        respx.delete("https://api.example.com/api/v1/devices/test-tenant/192.168.1.100").mock(
            return_value=httpx.Response(204)
        )

        result = runner.invoke(app, ["devices", "delete", sample_device["ipaddress"], "--force"])
        assert result.exit_code == 0
        assert "deleted" in result.stdout

        # Step 11: Verify device is gone from list
        empty_list_response = {"items": []}
        respx.get("https://api.example.com/api/v1/devices/test-tenant").mock(
            return_value=httpx.Response(200, json=empty_list_response)
        )

        result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code == 0
        assert sample_device["ipaddress"] not in result.stdout

    @respx.mock
    def test_workflow_error_handling(self, runner, mock_settings):
        """Test error handling in the workflow."""

        # Try to show non-existent device
        from netpicker_cli.api.errors import NotFound
        respx.get("https://api.example.com/api/v1/devices/test-tenant/192.168.1.999").mock(
            side_effect=NotFound("Device not found")
        )

        result = runner.invoke(app, ["devices", "show", "192.168.1.999"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

        # Try to upload config for non-existent device
        respx.post("https://api.example.com/api/v1/devices/test-tenant/192.168.1.999/configs").mock(
            return_value=httpx.Response(404, json={"detail": "Device not found"})
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test config")
            config_file = f.name

        try:
            result = runner.invoke(app, [
                "backups", "upload", "192.168.1.999",
                "--file", config_file
            ])
            assert result.exit_code == 1  # Should fail due to API error
        finally:
            os.unlink(config_file)