"""
Tests for the ``netpicker audit report`` command.

Covers:
- Full report generation with mocked API responses
- Tag filtering
- Stale-backup detection
- Error handling (API failures for individual sections)
- Parallel vs sequential collection
- Plugin (register_section) mechanism
- All output formats: table, json, csv, yaml
- CLI integration via CliRunner
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from netpicker_cli.commands.audit import (
    AuditReport,
    AuditSection,
    SectionStatus,
    _collect_backups,
    _collect_compliance,
    _collect_inventory,
    _collect_policies,
    _validate_tag,
    _validate_stale_days,
    register_section,
    _section_registry,
)
from netpicker_cli.utils.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_settings():
    return Settings(
        base_url="https://api.example.com",
        tenant="test-tenant",
        token="test-token",
    )


def _make_mock_cli(responses: dict) -> MagicMock:
    """Build a MagicMock ApiClient that returns pre-canned responses.

    ``responses`` maps URL substrings to the JSON payload to return.
    """
    cli = MagicMock()

    def _get(url: str, params=None):
        resp = MagicMock()
        for pattern, body in responses.items():
            if pattern in url:
                resp.json.return_value = body
                return resp
        resp.json.return_value = {}
        return resp

    def _post(url: str, json=None, params=None):
        resp = MagicMock()
        for pattern, body in responses.items():
            if pattern in url:
                resp.json.return_value = body
                return resp
        resp.json.return_value = {"items": []}
        return resp

    cli.get = MagicMock(side_effect=_get)
    cli.post = MagicMock(side_effect=_post)
    cli.close = MagicMock()
    return cli


@pytest.fixture
def sample_devices():
    """Three devices spanning two platforms."""
    return {
        "items": [
            {
                "ipaddress": "10.0.0.1",
                "name": "core-rtr",
                "platform": "cisco_ios",
                "tags": ["production", "core"],
            },
            {
                "ipaddress": "10.0.0.2",
                "name": "dist-sw",
                "platform": "arista_eos",
                "tags": ["production"],
            },
            {
                "ipaddress": "10.0.0.3",
                "name": "edge-fw",
                "platform": "fortios",
                "tags": ["edge"],
            },
        ],
        "total": 3,
    }


@pytest.fixture
def sample_compliance():
    return {
        "devices": {"passed": 2, "failed": 1, "critical": 0},
        "policies": {"enabled": 3, "disabled": 1},
    }


@pytest.fixture
def sample_recent_configs():
    """Two fresh, one stale (20 days old), one errored."""
    now = datetime.now(timezone.utc)
    return {
        "items": [
            {
                "ipaddress": "10.0.0.1",
                "name": "core-rtr",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "file_size": 4096,
            },
            {
                "ipaddress": "10.0.0.2",
                "name": "dist-sw",
                "created_at": (now - timedelta(days=2)).isoformat(),
                "file_size": 2048,
            },
            {
                "ipaddress": "10.0.0.3",
                "name": "edge-fw",
                "created_at": (now - timedelta(days=20)).isoformat(),
                "file_size": 1024,
            },
            {
                "ipaddress": "10.0.0.4",
                "name": "err-device",
                "created_at": now.isoformat(),
                "readout_error": True,
            },
        ],
    }


@pytest.fixture
def sample_policies():
    return [
        {"id": "p1", "name": "CIS-IOS", "enabled": True},
        {"id": "p2", "name": "CIS-EOS", "enabled": True},
        {"id": "p3", "name": "Draft-FW", "enabled": False},
    ]


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_validate_tag_none(self):
        assert _validate_tag(None) is None

    def test_validate_tag_empty(self):
        assert _validate_tag("") is None

    def test_validate_tag_whitespace(self):
        assert _validate_tag("  ") is None

    def test_validate_tag_valid(self):
        assert _validate_tag("production") == "production"
        assert _validate_tag("core-routers") == "core-routers"
        assert _validate_tag("site_01") == "site_01"
        assert _validate_tag("v1.2:latest") == "v1.2:latest"

    def test_validate_tag_strips_whitespace(self):
        assert _validate_tag("  production  ") == "production"

    def test_validate_tag_rejects_injection(self):
        with pytest.raises(typer.BadParameter):
            _validate_tag("prod; rm -rf /")

    def test_validate_tag_rejects_special_chars(self):
        with pytest.raises(typer.BadParameter):
            _validate_tag("<script>alert(1)</script>")

    def test_validate_stale_days_valid(self):
        assert _validate_stale_days(1) == 1
        assert _validate_stale_days(7) == 7
        assert _validate_stale_days(365) == 365

    def test_validate_stale_days_zero(self):
        with pytest.raises(typer.BadParameter):
            _validate_stale_days(0)

    def test_validate_stale_days_negative(self):
        with pytest.raises(typer.BadParameter):
            _validate_stale_days(-1)

    def test_validate_stale_days_too_large(self):
        with pytest.raises(typer.BadParameter):
            _validate_stale_days(999)


# ---------------------------------------------------------------------------
# AuditReport dataclass tests
# ---------------------------------------------------------------------------

class TestAuditReport:
    def test_overall_status_ok(self):
        report = AuditReport(
            tenant="t",
            sections=[AuditSection(name="a", status="ok")],
        )
        assert report.overall_status() == "ok"

    def test_overall_status_warning(self):
        report = AuditReport(
            tenant="t",
            sections=[
                AuditSection(name="a", status="ok"),
                AuditSection(name="b", status="warning"),
            ],
        )
        assert report.overall_status() == "warning"

    def test_overall_status_error_takes_precedence(self):
        report = AuditReport(
            tenant="t",
            sections=[
                AuditSection(name="a", status="warning"),
                AuditSection(name="b", status="error"),
            ],
        )
        assert report.overall_status() == "error"

    def test_to_dict(self):
        report = AuditReport(
            tenant="demo",
            generated_at="2026-01-10T12:00:00+00:00",
            tag_filter="prod",
            sections=[AuditSection(name="inv", status="ok", summary={"total": 3})],
        )
        d = report.to_dict()
        assert d["tenant"] == "demo"
        assert d["tag_filter"] == "prod"
        assert d["overall_status"] == "ok"
        assert len(d["sections"]) == 1
        assert d["sections"][0]["name"] == "inv"
        assert d["sections"][0]["summary"]["total"] == 3

    def test_empty_sections_is_ok(self):
        report = AuditReport(tenant="t", sections=[])
        assert report.overall_status() == "ok"


# ---------------------------------------------------------------------------
# Individual collector tests
# ---------------------------------------------------------------------------

class TestCollectInventory:
    def test_basic_inventory(self, mock_settings, sample_devices):
        cli = _make_mock_cli({"devices/test-tenant": sample_devices})
        section = _collect_inventory(cli, mock_settings, {})

        assert section.name == "inventory"
        assert section.status == "ok"
        assert section.summary["total_devices"] == 3
        assert "cisco_ios" in section.summary["platforms"]
        assert len(section.items) == 3

    def test_inventory_with_tag(self, mock_settings, sample_devices):
        cli = _make_mock_cli({"by_tags": sample_devices})
        section = _collect_inventory(cli, mock_settings, {"tag": "production"})

        assert section.status == "ok"
        assert section.summary["total_devices"] == 3
        # Should have called POST (by_tags) not GET
        cli.post.assert_called_once()

    def test_inventory_api_error(self, mock_settings):
        from netpicker_cli.api.errors import ApiError

        cli = MagicMock()
        cli.get.side_effect = ApiError("connection refused")
        section = _collect_inventory(cli, mock_settings, {})

        assert section.status == "error"
        assert len(section.errors) == 1
        assert "connection refused" in section.errors[0]

    def test_inventory_empty_response(self, mock_settings):
        cli = _make_mock_cli({"devices/test-tenant": {"items": []}})
        section = _collect_inventory(cli, mock_settings, {})

        assert section.status == "ok"
        assert section.summary["total_devices"] == 0


class TestCollectCompliance:
    def test_basic_compliance(self, mock_settings, sample_compliance):
        cli = _make_mock_cli({"compliance/test-tenant/overview": sample_compliance})
        section = _collect_compliance(cli, mock_settings, {})

        assert section.name == "compliance"
        assert section.status == "warning"  # has failures
        assert section.summary["devices"]["failed"] == 1

    def test_compliance_all_passing(self, mock_settings):
        data = {
            "devices": {"passed": 5, "failed": 0},
            "policies": {"enabled": 2, "disabled": 0},
        }
        cli = _make_mock_cli({"overview": data})
        section = _collect_compliance(cli, mock_settings, {})

        assert section.status == "ok"

    def test_compliance_api_error(self, mock_settings):
        from netpicker_cli.api.errors import ApiError

        cli = MagicMock()
        cli.get.side_effect = ApiError("timeout")
        section = _collect_compliance(cli, mock_settings, {})

        assert section.status == "error"
        assert "timeout" in section.errors[0]


class TestCollectBackups:
    def test_detects_stale(self, mock_settings, sample_recent_configs):
        cli = _make_mock_cli({"recent-configs": sample_recent_configs})
        section = _collect_backups(cli, mock_settings, {"stale_days": 7})

        assert section.name == "backups"
        assert section.status == "warning"
        assert section.summary["stale"] == 1
        assert section.summary["errored"] == 1
        assert section.summary["fresh"] == 2
        # The stale item should be edge-fw
        assert section.items[0]["ip"] == "10.0.0.3"

    def test_all_fresh(self, mock_settings):
        now = datetime.now(timezone.utc)
        data = {
            "items": [
                {"ipaddress": "10.0.0.1", "name": "r1", "created_at": now.isoformat()},
            ],
        }
        cli = _make_mock_cli({"recent-configs": data})
        section = _collect_backups(cli, mock_settings, {"stale_days": 7})

        assert section.status == "ok"
        assert section.summary["stale"] == 0
        assert section.summary["fresh"] == 1

    def test_custom_stale_threshold(self, mock_settings):
        now = datetime.now(timezone.utc)
        data = {
            "items": [
                {
                    "ipaddress": "10.0.0.1",
                    "name": "r1",
                    "created_at": (now - timedelta(days=2)).isoformat(),
                },
            ],
        }
        cli = _make_mock_cli({"recent-configs": data})

        # With 1-day threshold, the 2-day-old backup is stale
        section = _collect_backups(cli, mock_settings, {"stale_days": 1})
        assert section.summary["stale"] == 1

        # With 7-day threshold, it's fresh
        cli2 = _make_mock_cli({"recent-configs": data})
        section2 = _collect_backups(cli2, mock_settings, {"stale_days": 7})
        assert section2.summary["stale"] == 0

    def test_backup_api_error(self, mock_settings):
        from netpicker_cli.api.errors import ApiError

        cli = MagicMock()
        cli.get.side_effect = ApiError("502")
        section = _collect_backups(cli, mock_settings, {"stale_days": 7})

        assert section.status == "error"


class TestCollectPolicies:
    def test_basic_policies(self, mock_settings, sample_policies):
        cli = _make_mock_cli({"policy/test-tenant": sample_policies})
        section = _collect_policies(cli, mock_settings, {})

        assert section.name == "policies"
        assert section.status == "ok"
        assert section.summary["total"] == 3
        assert section.summary["enabled"] == 2
        assert section.summary["disabled"] == 1

    def test_policies_api_error(self, mock_settings):
        from netpicker_cli.api.errors import ApiError

        cli = MagicMock()
        cli.get.side_effect = ApiError("forbidden")
        section = _collect_policies(cli, mock_settings, {})

        assert section.status == "error"


# ---------------------------------------------------------------------------
# Plugin registry tests
# ---------------------------------------------------------------------------

class TestPluginRegistry:
    def setup_method(self):
        """Clear custom plugins before each test."""
        _section_registry.clear()

    def teardown_method(self):
        _section_registry.clear()

    def test_register_section(self):
        @register_section
        def custom_check(cli, settings, options):
            return AuditSection(name="custom", summary={"result": "pass"})

        assert len(_section_registry) == 1
        # Invoke it
        cli = MagicMock()
        s = MagicMock()
        result = _section_registry[0](cli, s, {})
        assert result.name == "custom"
        assert result.summary["result"] == "pass"

    def test_multiple_plugins(self):
        @register_section
        def plugin_a(cli, settings, options):
            return AuditSection(name="plugin_a")

        @register_section
        def plugin_b(cli, settings, options):
            return AuditSection(name="plugin_b")

        assert len(_section_registry) == 2


# ---------------------------------------------------------------------------
# CLI integration tests (via CliRunner)
# ---------------------------------------------------------------------------

class TestAuditCLI:
    """Test the audit command via Typer's CliRunner."""

    def _mock_all_endpoints(self, sample_devices, sample_compliance,
                             sample_recent_configs, sample_policies):
        """Return a responses dict covering all audit endpoints."""
        return {
            "devices/test-tenant": sample_devices,
            "by_tags": sample_devices,
            "compliance/test-tenant/overview": sample_compliance,
            "recent-configs": sample_recent_configs,
            "policy/test-tenant": sample_policies,
        }

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_table_output(
        self, MockApiClient, mock_load, runner,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(audit_app, ["report", "--no-parallel"])
        assert result.exit_code == 0
        assert "INVENTORY" in result.output
        assert "COMPLIANCE" in result.output
        assert "BACKUPS" in result.output
        assert "POLICIES" in result.output

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_json_output(
        self, MockApiClient, mock_load, runner,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(audit_app, ["report", "--format", "json", "--no-parallel"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["tenant"] == "test-tenant"
        assert "sections" in data
        assert len(data["sections"]) == 4

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_csv_output(
        self, MockApiClient, mock_load, runner,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(audit_app, ["report", "--format", "csv", "--no-parallel"])
        assert result.exit_code == 0
        assert "section,status,metric,value" in result.output
        assert "inventory" in result.output

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_yaml_output(
        self, MockApiClient, mock_load, runner,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(audit_app, ["report", "--format", "yaml", "--no-parallel"])
        assert result.exit_code == 0
        assert "tenant:" in result.output
        assert "sections:" in result.output

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_with_tag_filter(
        self, MockApiClient, mock_load, runner,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(
            audit_app, ["report", "--tag", "production", "--format", "json", "--no-parallel"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["tag_filter"] == "production"

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_custom_stale_days(
        self, MockApiClient, mock_load, runner,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(
            audit_app, ["report", "--stale-days", "1", "--format", "json", "--no-parallel"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        backups_section = [s for s in data["sections"] if s["name"] == "backups"][0]
        assert backups_section["summary"]["stale_threshold_days"] == 1

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_output_to_file(
        self, MockApiClient, mock_load, runner, tmp_path,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        mock_load.return_value = mock_settings
        responses = self._mock_all_endpoints(
            sample_devices, sample_compliance,
            sample_recent_configs, sample_policies,
        )
        MockApiClient.return_value = _make_mock_cli(responses)

        out_file = str(tmp_path / "report.json")
        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(
            audit_app, ["report", "--format", "json", "--output", out_file, "--no-parallel"],
        )
        assert result.exit_code == 0
        with open(out_file) as f:
            data = json.load(f)
        assert data["tenant"] == "test-tenant"

    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_report_help_subcommand(
        self, MockApiClient, mock_load, runner, mock_settings,
    ):
        """``netpicker audit`` without subcommand should show help."""
        mock_load.return_value = mock_settings
        from netpicker_cli.commands.audit import app as audit_app
        result = runner.invoke(audit_app, [])
        assert result.exit_code == 0
        assert "report" in result.output


# ---------------------------------------------------------------------------
# Parallel collection test
# ---------------------------------------------------------------------------

class TestParallelCollection:
    @patch("netpicker_cli.commands.audit.load_settings")
    @patch("netpicker_cli.commands.audit.ApiClient")
    def test_parallel_produces_same_result(
        self, MockApiClient, mock_load,
        mock_settings, sample_devices, sample_compliance,
        sample_recent_configs, sample_policies,
    ):
        """Parallel and sequential should produce the same section names."""
        mock_load.return_value = mock_settings
        responses = {
            "devices/test-tenant": sample_devices,
            "by_tags": sample_devices,
            "compliance/test-tenant/overview": sample_compliance,
            "recent-configs": sample_recent_configs,
            "policy/test-tenant": sample_policies,
        }
        MockApiClient.return_value = _make_mock_cli(responses)

        runner = CliRunner()
        from netpicker_cli.commands.audit import app as audit_app

        result_seq = runner.invoke(
            audit_app, ["report", "--format", "json", "--no-parallel"],
        )
        result_par = runner.invoke(
            audit_app, ["report", "--format", "json", "--parallel"],
        )

        assert result_seq.exit_code == 0
        assert result_par.exit_code == 0

        seq_data = json.loads(result_seq.stdout)
        par_data = json.loads(result_par.stdout)

        seq_names = sorted(s["name"] for s in seq_data["sections"])
        par_names = sorted(s["name"] for s in par_data["sections"])
        assert seq_names == par_names
