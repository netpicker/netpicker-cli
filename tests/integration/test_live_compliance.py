"""
Live integration tests for compliance commands against a real Netpicker environment.

Prerequisites:
  1. Authenticate first:  netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
  2. Run with:  python -m pytest tests/integration/test_live_compliance.py -v -s

These tests cover ALL 8 compliance subcommands:
  - overview        — tenant compliance summary (JSON + table)
  - report-tenant   — paginated compliance report (JSON, table, filters)
  - devices         — policy devices list (JSON + table)
  - export          — export compliance report (CSV-like text)
  - status          — device compliance status (JSON + table)
  - failures        — tenant compliance failures (JSON + table)
  - log             — log compliance for a config id (example flag + POST)
  - report-config   — report compliance for a config id (example flag + POST)

To skip these tests in CI, the marker ``live`` is applied — add
``-m "not live"`` to your pytest invocation.
"""

import json
import pytest
from typer.testing import CliRunner
from netpicker_cli.cli import app

pytestmark = pytest.mark.live

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ensure_auth():
    """Verify that credentials are configured before running any test."""
    result = runner.invoke(app, ["whoami", "--format", "json"])
    if result.exit_code != 0:
        pytest.skip(
            "Not authenticated — run `netpicker auth login` first.\n"
            f"  output: {result.output}"
        )
    return json.loads(result.output)


@pytest.fixture(scope="module")
def compliance_device(ensure_auth):
    """Find a device that has compliance data.

    Looks at the compliance devices list and picks the first one with a
    non-empty summary.
    """
    result = runner.invoke(app, [
        "compliance", "devices", "--format", "json", "--size", "5",
    ])
    if result.exit_code != 0:
        pytest.skip(f"compliance devices failed: {result.output}")

    items = json.loads(result.output)
    for it in items:
        ip = it.get("ipaddress")
        summary = it.get("summary") or {}
        if ip and summary:
            return {"ip": ip, "name": it.get("name", ""), "summary": summary}

    pytest.skip("No device with compliance data found in tenant")


@pytest.fixture(scope="module")
def config_id(ensure_auth):
    """Get a valid config_id from recent backups for log/report-config tests."""
    result = runner.invoke(app, ["backups", "recent", "--format", "json"])
    if result.exit_code != 0:
        pytest.skip(f"backups recent failed: {result.output}")

    items = json.loads(result.output)
    for it in items:
        cid = it.get("id") or it.get("config_id")
        if cid and not it.get("readout_error"):
            return str(cid)

    pytest.skip("No config with valid id found in recent backups")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLiveComplianceWorkflow:
    """End-to-end compliance tests covering all 8 subcommands."""

    # -- 1: overview ----------------------------------------------------------

    def test_01_overview_json(self, ensure_auth):
        """compliance overview --format json should return devices/policies dict."""
        result = runner.invoke(app, ["compliance", "overview", "--format", "json"])
        assert result.exit_code == 0, f"overview failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict), f"expected dict, got {type(data)}"
        # Should have at least one of 'devices' or 'policies'
        assert "devices" in data or "policies" in data, (
            f"overview missing expected keys: {list(data.keys())}"
        )

    def test_02_overview_table(self, ensure_auth):
        """compliance overview in table format should produce readable output."""
        result = runner.invoke(app, ["compliance", "overview"])
        assert result.exit_code == 0, f"overview table failed:\n{result.output}"
        assert len(result.output.strip()) > 0, "overview table output is empty"

    # -- 2: report-tenant -----------------------------------------------------

    def test_03_report_tenant_json(self, ensure_auth):
        """compliance report-tenant --format json should return report entries."""
        result = runner.invoke(app, [
            "compliance", "report-tenant", "--format", "json", "--size", "5",
        ])
        assert result.exit_code == 0, f"report-tenant failed:\n{result.output}"
        items = json.loads(result.output)
        assert isinstance(items, list), f"expected list, got {type(items)}"
        assert len(items) > 0, "report-tenant returned no entries"

    def test_04_report_tenant_table(self, ensure_auth):
        """compliance report-tenant in table format should show column headers."""
        result = runner.invoke(app, [
            "compliance", "report-tenant", "--size", "5",
        ])
        assert result.exit_code == 0, f"report-tenant table failed:\n{result.output}"
        output = result.output.lower()
        assert "policy" in output or "rule" in output or "outcome" in output, (
            f"table missing expected headers: {result.output[:300]}"
        )

    def test_05_report_tenant_with_outcome_filter(self, ensure_auth):
        """compliance report-tenant --outcome should filter by outcome."""
        result = runner.invoke(app, [
            "compliance", "report-tenant",
            "--outcome", "SUCCESS",
            "--format", "json", "--size", "5",
        ])
        assert result.exit_code == 0, f"report-tenant --outcome failed:\n{result.output}"
        items = json.loads(result.output)
        assert isinstance(items, list)
        # All returned items should have outcome SUCCESS (if server honours filter)
        for it in items:
            assert it.get("outcome") == "SUCCESS", (
                f"expected outcome SUCCESS, got {it.get('outcome')}"
            )

    # -- 3: devices -----------------------------------------------------------

    def test_06_devices_json(self, ensure_auth):
        """compliance devices --format json should return device list."""
        result = runner.invoke(app, [
            "compliance", "devices", "--format", "json", "--size", "5",
        ])
        assert result.exit_code == 0, f"devices failed:\n{result.output}"
        items = json.loads(result.output)
        assert isinstance(items, list), f"expected list, got {type(items)}"
        assert len(items) > 0, "devices returned no entries"
        # Each item should have ipaddress
        assert items[0].get("ipaddress"), "device entry missing 'ipaddress'"

    def test_07_devices_table(self, ensure_auth):
        """compliance devices in table format should produce output."""
        result = runner.invoke(app, [
            "compliance", "devices", "--size", "5",
        ])
        assert result.exit_code == 0, f"devices table failed:\n{result.output}"
        assert len(result.output.strip()) > 0, "devices table output is empty"

    # -- 4: export ------------------------------------------------------------

    def test_08_export_returns_data(self, ensure_auth):
        """compliance export should return CSV-like or JSON data."""
        result = runner.invoke(app, ["compliance", "export"])
        assert result.exit_code == 0, f"export failed:\n{result.output}"
        assert len(result.output.strip()) > 0, "export returned empty output"

    def test_09_export_json_format(self, ensure_auth):
        """compliance export --format json should return parseable output."""
        result = runner.invoke(app, ["compliance", "export", "--format", "json"])
        assert result.exit_code == 0, f"export --json failed:\n{result.output}"
        # Export may return CSV text even with --json flag (depends on server)
        # Just verify the command succeeds and has output
        assert len(result.output.strip()) > 0, "export --json returned empty output"

    # -- 5: status ------------------------------------------------------------

    def test_10_status_json(self, ensure_auth, compliance_device):
        """compliance status <ip> --format json should return device status."""
        ip = compliance_device["ip"]
        result = runner.invoke(app, [
            "compliance", "status", ip, "--format", "json",
        ])
        assert result.exit_code == 0, f"status failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict), f"expected dict, got {type(data)}"
        assert data.get("ipaddress") == ip, (
            f"status ip mismatch: expected {ip}, got {data.get('ipaddress')}"
        )

    def test_11_status_table(self, ensure_auth, compliance_device):
        """compliance status <ip> in table format should produce readable output."""
        ip = compliance_device["ip"]
        result = runner.invoke(app, ["compliance", "status", ip])
        assert result.exit_code == 0, f"status table failed:\n{result.output}"
        assert len(result.output.strip()) > 0, "status table output is empty"

    # -- 6: failures ----------------------------------------------------------

    def test_12_failures_json(self, ensure_auth):
        """compliance failures --format json should return data or handle server error."""
        result = runner.invoke(app, ["compliance", "failures", "--format", "json"])
        # failures endpoint may return 500 on some server versions
        # We accept either success with data or a graceful error message
        if result.exit_code == 0:
            # If successful, should output something
            output = result.output.strip()
            assert len(output) > 0, "failures returned empty output"
        else:
            # Graceful error — should contain an error message, not a traceback
            assert "error" in result.output.lower() or "Error" in result.output, (
                f"unexpected failure output: {result.output[:300]}"
            )

    def test_13_failures_table(self, ensure_auth):
        """compliance failures in table format should handle gracefully."""
        result = runner.invoke(app, ["compliance", "failures"])
        # Same as above — accept success or graceful error
        if result.exit_code == 0:
            assert len(result.output.strip()) > 0 or "No failures" in result.output
        else:
            assert "error" in result.output.lower() or "Error" in result.output

    # -- 7: log ---------------------------------------------------------------

    def test_14_log_example_flag(self, ensure_auth):
        """compliance log --example should print sample JSON payload."""
        result = runner.invoke(app, [
            "compliance", "log", "dummy-config-id", "--example",
        ])
        assert result.exit_code == 0, f"log --example failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, dict), f"expected dict, got {type(data)}"
        assert "outcome" in data, "example payload missing 'outcome' field"
        assert "policy" in data, "example payload missing 'policy' field"

    def test_15_log_post(self, ensure_auth, config_id):
        """compliance log <config_id> should POST (empty body) and succeed or return API error."""
        result = runner.invoke(app, [
            "compliance", "log", config_id, "--format", "json",
        ])
        # The server may accept or reject depending on policy config.
        # We verify the command doesn't crash with a Python traceback.
        if result.exit_code == 0:
            # Successful — output should be valid JSON or text
            assert len(result.output.strip()) > 0
        else:
            # API error is acceptable (e.g., 422 if no body required)
            assert "error" in result.output.lower() or "Error" in result.output, (
                f"unexpected log output: {result.output[:300]}"
            )

    # -- 8: report-config -----------------------------------------------------

    def test_16_report_config_example_flag(self, ensure_auth):
        """compliance report-config --example should print sample JSON payload."""
        result = runner.invoke(app, [
            "compliance", "report-config", "dummy-config-id", "--example",
        ])
        assert result.exit_code == 0, f"report-config --example failed:\n{result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list), f"expected list, got {type(data)}"
        assert len(data) > 0, "example payload is empty"
        assert "outcome" in data[0], "example entry missing 'outcome' field"

    def test_17_report_config_post(self, ensure_auth, config_id):
        """compliance report-config <config_id> should POST and succeed or return API error."""
        result = runner.invoke(app, [
            "compliance", "report-config", config_id, "--format", "json",
        ])
        # Same as log — accept success or graceful API error
        if result.exit_code == 0:
            assert len(result.output.strip()) > 0
        else:
            assert "error" in result.output.lower() or "Error" in result.output, (
                f"unexpected report-config output: {result.output[:300]}"
            )
