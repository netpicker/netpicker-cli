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


class TestAutomationCommands:
    """Test automation commands"""

    @respx.mock
    def test_list_fixtures_success(self, runner, mock_settings):
        """Test listing fixtures successfully"""
        # Mock the API response
        fixtures_data = ["device", "api", "configuration", "commands"]
        respx.get("https://api.example.com/api/v1/automation/test-tenant/fixtures").respond(
            json=fixtures_data
        )

        # Mock settings loading
        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "list-fixtures"])

        assert result.exit_code == 0
        assert "Available fixtures:" in result.output
        for fixture in fixtures_data:
            assert fixture in result.output

    @respx.mock
    def test_list_fixtures_json_output(self, runner, mock_settings):
        """Test listing fixtures with JSON output"""
        fixtures_data = ["device", "api"]
        respx.get("https://api.example.com/api/v1/automation/test-tenant/fixtures").respond(
            json=fixtures_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "list-fixtures", "--json"])

        assert result.exit_code == 0
        assert '"device"' in result.output
        assert '"api"' in result.output

    @respx.mock
    def test_list_jobs_success(self, runner, mock_settings):
        """Test listing jobs successfully"""
        jobs_data = [
            {
                "name": "test_job",
                "platforms": ["cisco_ios"],
                "variables": ["var1", "var2"],
                "is_simple": True
            }
        ]
        respx.get("https://api.example.com/api/v1/automation/test-tenant/job").respond(
            json=jobs_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "list-jobs"])

        assert result.exit_code == 0
        assert "Available jobs:" in result.output
        assert "test_job:" in result.output
        assert "Platforms: cisco_ios" in result.output
        assert "Variables: var1, var2" in result.output
        assert "Simple: Yes" in result.output

    @respx.mock
    def test_show_job_success(self, runner, mock_settings):
        """Test showing job details successfully"""
        job_data = {
            "jobs": [
                {
                    "id": "test_job/__init__.py::test_job",
                    "name": "test_job",
                    "platforms": ["cisco_ios"],
                    "signature": {
                        "params": [
                            {
                                "name": "param1",
                                "has_default": False,
                                "annotated": {"annotation": "builtins.str"}
                            }
                        ]
                    },
                    "range": {"start": 1, "end": 10},
                    "is_simple": False
                }
            ],
            "sources": {
                "__init__.py": "def test_job():\n    pass"
            }
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/job/test_job").respond(
            json=job_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "show-job", "test_job"])

        assert result.exit_code == 0
        assert "Job: test_job" in result.output
        assert "Parameters:" in result.output
        assert "param1: str" in result.output
        assert "Source Files:" in result.output

    @respx.mock
    def test_show_job_not_found(self, runner, mock_settings):
        """Test showing job that doesn't exist"""
        respx.get("https://api.example.com/api/v1/automation/test-tenant/job/nonexistent").respond(
            status_code=404
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "show-job", "nonexistent"])

        assert result.exit_code == 1
        assert "Job 'nonexistent' not found" in result.output

    @respx.mock
    def test_delete_job_success(self, runner, mock_settings):
        """Test deleting job successfully"""
        respx.delete("https://api.example.com/api/v1/automation/test-tenant/job/test_job").respond(
            status_code=204
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "delete-job", "test_job"])

        assert result.exit_code == 0
        assert "Job deleted successfully" in result.output

    @respx.mock
    def test_test_job_success(self, runner, mock_settings):
        """Test testing job successfully"""
        test_response = {
            "nodeid": "test_job/__init__.py::test_job",
            "exec_at": "2025-11-04T12:07:45.591267",
            "exec_ns": 128786738,
            "return_value": 42,
            "logs": "Job execution finished",
            "status": "COMPLETED"
        }
        respx.post("https://api.example.com/api/v1/automation/test-tenant/debug").respond(
            json=test_response
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "automation", "test-job", 
                "--name", "test_job",
                "--variables", "n:21",
                "--ipaddress", "10.10.10.1"
            ])

        assert result.exit_code == 0
        assert "Job Test Results for 'test_job':" in result.output
        assert "Status: COMPLETED" in result.output
        assert "Return Value: 42" in result.output

    @respx.mock
    def test_execute_job_success(self, runner, mock_settings):
        """Test executing job successfully"""
        respx.post("https://api.example.com/api/v1/automation/test-tenant/execute").respond(
            text="Job executed successfully on 2 devices"
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "automation", "execute-job", 
                "--name", "test_job",
                "--variables", "n:21",
                "--devices", "10.10.10.1,10.10.10.2"
            ])

        assert result.exit_code == 0
        assert "Job executed successfully on 2 devices" in result.output

    @respx.mock
    def test_logs_success(self, runner, mock_settings):
        """Test getting job logs successfully"""
        logs_data = {
            "items": [
                {
                    "id": "log-123",
                    "job_name": "test_job",
                    "job_id": "job-456",
                    "initiator": "user@example.com",
                    "variables": {"n": 21},
                    "return_value": ["success"],
                    "exec_at": "2026-01-05T17:41:35.195Z",
                    "exec_ns": 1500000000,
                    "log": "Job completed successfully\nDetails: n=21",
                    "ipaddress": "10.10.10.1",
                    "name": "test_job_run",
                    "status": "SUCCESS",
                    "created": "2026-01-05T17:41:35.195Z"
                }
            ],
            "total": 1,
            "page": 1,
            "size": 50,
            "pages": 1
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/logs").respond(
            json=logs_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "logs"])

        assert result.exit_code == 0
        assert "Job Logs" in result.output
        assert "test_job" in result.output
        assert "SUCCESS" in result.output

    @respx.mock
    def test_logs_with_filters(self, runner, mock_settings):
        """Test getting job logs with filters"""
        logs_data = {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 50,
            "pages": 0
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/logs?job_name=test_job&status=SUCCESS&page=2&size=10").respond(
            json=logs_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "automation", "logs",
                "--job-name", "test_job",
                "--status", "SUCCESS",
                "--page", "2",
                "--size", "10"
            ])

        assert result.exit_code == 0
        assert "No logs found" in result.output

    @respx.mock
    def test_show_log_success(self, runner, mock_settings):
        """Test getting a specific log entry successfully"""
        log_data = {
            "id": "log-123",
            "job_name": "test_job",
            "job_id": "job-456",
            "initiator": "user@example.com",
            "variables": {"n": 21},
            "return_value": ["success"],
            "exec_at": "2026-01-05T17:41:35.195Z",
            "exec_ns": 1500000000,
            "log": "Job completed successfully\nDetails: n=21",
            "ipaddress": "10.10.10.1",
            "name": "test_job_run",
            "status": "SUCCESS",
            "created": "2026-01-05T17:41:35.195Z"
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/logs/log-123").respond(
            json=log_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "show-log", "log-123"])

        assert result.exit_code == 0
        assert "Log Entry: log-123" in result.output
        assert "test_job" in result.output
        assert "SUCCESS" in result.output
        assert "n: 21" in result.output

    @respx.mock
    def test_list_queue_success(self, runner, mock_settings):
        """Test listing queued jobs successfully"""
        queue_data = {
            "items": [
                {
                    "id": "queue-123",
                    "tenant_id": 1,
                    "branch": "main",
                    "submitter": "user@example.com",
                    "submitted": "2026-01-05T17:44:23.722Z",
                    "reviewer": "admin@example.com",
                    "reviewed": "2026-01-05T17:45:00.000Z",
                    "expires": "2026-01-06T17:44:23.722Z",
                    "job_name": "scheduled_backup",
                    "job_id": "job-456",
                    "devices": ["10.10.10.1", "10.10.10.2"],
                    "tags": ["backup", "scheduled"],
                    "variables": {"frequency": "daily"},
                    "execron": {
                        "minute": "0",
                        "hour": "2",
                        "day_of_week": "*",
                        "day_of_month": "*",
                        "month_of_year": "*",
                        "timezone": "UTC"
                    },
                    "status": "APPROVED"
                }
            ],
            "total": 1,
            "page": 1,
            "size": 50,
            "pages": 1
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/queue").respond(
            json=queue_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "list-queue"])

        assert result.exit_code == 0
        assert "Queued Jobs" in result.output
        assert "scheduled_backup" in result.output
        assert "APPROVED" in result.output
        assert "backup, scheduled" in result.output

    @respx.mock
    def test_list_queue_with_filters(self, runner, mock_settings):
        """Test listing queued jobs with filters"""
        queue_data = {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 50,
            "pages": 0
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/queue?name=test_job&status=APPROVED&page=2&size=10").respond(
            json=queue_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "automation", "list-queue",
                "--name", "test_job",
                "--status", "APPROVED",
                "--page", "2",
                "--size", "10"
            ])

        assert result.exit_code == 0
        assert "No queued jobs found" in result.output

    @respx.mock
    def test_store_queue_success(self, runner, mock_settings):
        """Test storing a queued job successfully"""
        queue_response = {
            "id": "queue-456",
            "tenant_id": 1,
            "branch": "main",
            "submitter": "user@example.com",
            "submitted": "2026-01-05T17:47:00.707Z",
            "reviewer": None,
            "reviewed": None,
            "expires": "2026-01-06T17:47:00.707Z",
            "job_name": "scheduled_backup",
            "job_id": "job-789",
            "devices": ["10.10.10.1"],
            "tags": ["backup"],
            "variables": {"frequency": "daily"},
            "execron": {
                "minute": "0",
                "hour": "2",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
                "timezone": "UTC"
            },
            "status": "UNAPPROVED"
        }
        respx.post("https://api.example.com/api/v1/automation/test-tenant/queue").respond(
            json=queue_response
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, [
                "automation", "store-queue",
                "--name", "scheduled_backup",
                "--sources", "backup.py:print('backup')",
                "--variables", "frequency:daily",
                "--devices", "10.10.10.1",
                "--tags", "backup",
                "--execron-hour", "2",
                "--expires", "2026-01-06T17:47:00.707Z"
            ])

        assert result.exit_code == 0
        assert "Job queued successfully" in result.output
        assert "queue-456" in result.output
        assert "UNAPPROVED" in result.output

    @respx.mock
    def test_show_queue_success(self, runner, mock_settings):
        """Test getting a specific queued job successfully"""
        queue_data = {
            "id": "queue-123",
            "tenant_id": 1,
            "branch": "main",
            "submitter": "user@example.com",
            "submitted": "2026-01-05T17:47:23.509Z",
            "reviewer": "admin@example.com",
            "reviewed": "2026-01-05T17:48:00.000Z",
            "expires": "2026-01-06T17:47:23.509Z",
            "job_name": "scheduled_backup",
            "job_id": "job-456",
            "devices": ["10.10.10.1", "10.10.10.2"],
            "tags": ["backup", "scheduled"],
            "variables": {"frequency": "daily"},
            "execron": {
                "minute": "0",
                "hour": "2",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
                "timezone": "UTC"
            },
            "status": "APPROVED",
            "sources": {
                "backup.py": "def main():\n    print('Running backup')\n    return 'success'"
            }
        }
        respx.get("https://api.example.com/api/v1/automation/test-tenant/queue/queue-123").respond(
            json=queue_data
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "show-queue", "queue-123"])

        assert result.exit_code == 0
        assert "Queued Job: queue-123" in result.output
        assert "scheduled_backup" in result.output
        assert "APPROVED" in result.output
        assert "backup, scheduled" in result.output
        assert "backup.py:" in result.output

    @respx.mock
    def test_delete_queue_success(self, runner, mock_settings):
        """Test deleting a queued job successfully"""
        respx.delete("https://api.example.com/api/v1/automation/test-tenant/queue/queue-123").respond(
            status_code=204
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "delete-queue", "queue-123"])

        assert result.exit_code == 0
        assert "Queued job deleted successfully" in result.output

    @respx.mock
    def test_review_queue_approve(self, runner, mock_settings):
        """Test approving a queued job"""
        review_response = {
            "id": "queue-123",
            "tenant_id": 1,
            "branch": "main",
            "submitter": "user@example.com",
            "submitted": "2026-01-05T17:47:23.509Z",
            "reviewer": "admin@example.com",
            "reviewed": "2026-01-05T17:48:32.453Z",
            "expires": "2026-01-06T17:47:23.509Z",
            "job_name": "scheduled_backup",
            "job_id": "job-456",
            "devices": ["10.10.10.1"],
            "tags": ["backup"],
            "variables": {"frequency": "daily"},
            "execron": {
                "minute": "0",
                "hour": "2",
                "day_of_week": "*",
                "day_of_month": "*",
                "month_of_year": "*",
                "timezone": "UTC"
            },
            "status": "APPROVED"
        }
        respx.post("https://api.example.com/api/v1/automation/test-tenant/queue/queue-123/review?approved=true").respond(
            json=review_response
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "review-queue", "queue-123", "--approved=true"])

        assert result.exit_code == 0
        assert "Queued job approved successfully" in result.output
        assert "APPROVED" in result.output

    @respx.mock
    def test_review_queue_reject(self, runner, mock_settings):
        """Test rejecting a queued job"""
        review_response = {
            "id": "queue-123",
            "status": "REJECTED",
            "reviewer": "admin@example.com",
            "reviewed": "2026-01-05T17:48:32.453Z"
        }
        respx.post("https://api.example.com/api/v1/automation/test-tenant/queue/queue-123/review?approved=false").respond(
            json=review_response
        )

        with mock.patch("netpicker_cli.commands.automation.load_settings", return_value=mock_settings):
            result = runner.invoke(app, ["automation", "review-queue", "queue-123", "--approved=false"])

        assert result.exit_code == 0
        assert "Queued job rejected successfully" in result.output
        assert "REJECTED" in result.output