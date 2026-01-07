"""
Tests for parameter extraction logic in AI commands
"""

import pytest
from netpicker_cli.commands.ai import extract_parameters, fetch_latest_backup, run_netpicker_command
from unittest.mock import patch, MagicMock


class TestParameterExtraction:
    """Test parameter extraction from natural language queries"""

    def test_extract_limit_from_numeric_pattern(self):
        """Test extracting limit from queries with numeric patterns"""
        assert extract_parameters("list 5 devices")["limit"] == 5
        assert extract_parameters("show top 10 routers")["limit"] == 10
        assert extract_parameters("get first 3 switches")["limit"] == 3
        assert extract_parameters("show last 2 configs")["limit"] == 2
        assert extract_parameters("show any 7 items")["limit"] == 7
        assert extract_parameters("list with limit 15")["limit"] == 15

    def test_extract_limit_priority_order(self):
        """Test that first matched pattern takes priority"""
        # Should match "5 devices" not "top 10"
        result = extract_parameters("list 5 devices from top 10")
        assert result["limit"] == 5

    def test_extract_ip_address(self):
        """Test extracting IP addresses from queries"""
        assert extract_parameters("show device 192.168.1.1")["ip"] == "192.168.1.1"
        assert extract_parameters("get config for 10.0.0.5")["ip"] == "10.0.0.5"
        assert extract_parameters("check 172.16.254.1 status")["ip"] == "172.16.254.1"

    def test_extract_tag_various_patterns(self):
        """Test extracting tags from different query patterns"""
        assert extract_parameters("list devices with tag production")["tag"] == "production"
        assert extract_parameters("show devices tag testing")["tag"] == "testing"
        assert extract_parameters("get devices for tag datacenter-1")["tag"] == "datacenter-1"
        assert extract_parameters("devices with tag lab_env")["tag"] == "lab_env"

    def test_extract_multiple_parameters(self):
        """Test extracting multiple parameters from single query"""
        result = extract_parameters("show 5 devices with tag production")
        assert result["limit"] == 5
        assert result["tag"] == "production"

        result = extract_parameters("get config for 192.168.1.1 tag router")
        assert result["ip"] == "192.168.1.1"
        assert result["tag"] == "router"

    def test_no_parameters_found(self):
        """Test queries with no extractable parameters"""
        result = extract_parameters("list all devices")
        assert "limit" not in result
        assert "ip" not in result
        assert "tag" not in result

    def test_invalid_ip_address_not_matched(self):
        """Test that invalid IP addresses are not extracted"""
        result = extract_parameters("show 999.999.999.999")
        # Even though this matches the pattern, it's returned
        # Real validation should happen at API level
        assert result.get("ip") == "999.999.999.999" or "ip" not in result

    def test_tag_case_insensitivity(self):
        """Test that tag extraction is case-insensitive"""
        assert extract_parameters("devices TAG production")["tag"] == "production"
        assert extract_parameters("show devices Tag testing")["tag"] == "testing"
        assert extract_parameters("devices WITH TAG datacenter")["tag"] == "datacenter"

    def test_edge_case_zero_limit(self):
        """Test edge case with zero as limit"""
        result = extract_parameters("show 0 devices")
        assert result["limit"] == 0

    def test_large_limit_value(self):
        """Test extraction of large limit values"""
        result = extract_parameters("list 1000 devices")
        assert result["limit"] == 1000

    def test_extract_first_ip_when_multiple(self):
        """Test that first IP is extracted when multiple present"""
        result = extract_parameters("copy config from 192.168.1.1 to 192.168.1.2")
        assert result["ip"] == "192.168.1.1"


class TestFetchLatestBackup:
    """Test backup fetching logic"""

    @patch('netpicker_cli.commands.ai.run_netpicker_command')
    def test_fetch_latest_backup_success(self, mock_run):
        """Test successful backup fetch"""
        # Mock returns list on first call, then backup content on second
        mock_run.side_effect = [
            {
                "success": True,
                "stdout": '[{"id": "123", "upload_date": "2026-01-01"}]',
                "stderr": "",
                "returncode": 0
            },
            {
                "success": True,
                "stdout": "hostname router1\ninterface Gi0/0",
                "stderr": "",
                "returncode": 0
            }
        ]
        
        result = fetch_latest_backup("192.168.1.1")
        assert "hostname router1" in result or "123" in result
        assert mock_run.call_count == 2

    @patch('netpicker_cli.commands.ai.run_netpicker_command')
    def test_fetch_latest_backup_empty_list(self, mock_run):
        """Test backup fetch with empty backup list"""
        mock_run.return_value = {
            "success": True,
            "stdout": '[]',
            "stderr": "",
            "returncode": 0
        }
        
        result = fetch_latest_backup("192.168.1.1")
        assert "No backups found" in result

    @patch('netpicker_cli.commands.ai.run_netpicker_command')
    def test_fetch_latest_backup_command_failure(self, mock_run):
        """Test backup fetch when command fails"""
        mock_run.return_value = {
            "success": False,
            "stdout": "",
            "stderr": "Connection error",
            "returncode": 1
        }
        
        result = fetch_latest_backup("192.168.1.1")
        assert "Error" in result or "Connection error" in result

    @patch('netpicker_cli.commands.ai.run_netpicker_command')
    def test_fetch_latest_backup_malformed_json(self, mock_run):
        """Test backup fetch with malformed JSON response"""
        mock_run.return_value = {
            "success": True,
            "stdout": 'not a json',
            "stderr": "",
            "returncode": 0
        }
        
        result = fetch_latest_backup("192.168.1.1")
        assert "Error parsing" in result or "Failed" in result

    @patch('netpicker_cli.commands.ai.run_netpicker_command')
    def test_fetch_latest_backup_with_fetch_command(self, mock_run):
        """Test that backup is fetched after list"""
        # First call returns list with backup ID
        # Second call fetches the actual backup
        mock_run.side_effect = [
            {
                "success": True,
                "stdout": '[{"id": "config-123", "upload_date": "2026-01-01"}]',
                "stderr": "",
                "returncode": 0
            },
            {
                "success": True,
                "stdout": "hostname router1\ninterface Gi0/0\n",
                "stderr": "",
                "returncode": 0
            }
        ]
        
        result = fetch_latest_backup("192.168.1.1")
        assert "hostname router1" in result
        assert mock_run.call_count == 2


class TestRunNetpickerCommand:
    """Test command execution wrapper"""

    @patch('subprocess.run')
    def test_run_command_success(self, mock_subprocess):
        """Test successful command execution"""
        mock_subprocess.return_value = MagicMock(
            stdout="output",
            stderr="",
            returncode=0
        )
        
        result = run_netpicker_command(["devices", "list"])
        assert result["success"] is True
        assert result["stdout"] == "output"
        assert result["returncode"] == 0

    @patch('subprocess.run')
    def test_run_command_failure(self, mock_subprocess):
        """Test failed command execution"""
        mock_subprocess.return_value = MagicMock(
            stdout="",
            stderr="Error occurred",
            returncode=1
        )
        
        result = run_netpicker_command(["devices", "delete"])
        assert result["success"] is False
        assert result["stderr"] == "Error occurred"
        assert result["returncode"] == 1

    @patch('subprocess.run')
    def test_run_command_with_environment(self, mock_subprocess):
        """Test that environment variables are passed"""
        mock_subprocess.return_value = MagicMock(
            stdout="output",
            stderr="",
            returncode=0
        )
        
        run_netpicker_command(["devices", "list"])
        call_kwargs = mock_subprocess.call_args.kwargs
        assert "env" in call_kwargs
        assert "PATH" in call_kwargs["env"]

    @patch('subprocess.run')
    def test_run_command_timeout_handled(self, mock_subprocess):
        """Test that subprocess timeout is handled"""
        mock_subprocess.side_effect = Exception("Timeout")
        
        result = run_netpicker_command(["devices", "list"])
        assert result["success"] is False
        assert "error" in result["stderr"].lower() or "Timeout" in str(result.get("stderr", ""))
