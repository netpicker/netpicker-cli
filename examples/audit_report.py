#!/usr/bin/env python3
"""
Example: Using the ``netpicker audit report`` command programmatically.

This script shows three ways to use the audit feature:

1. CLI invocation (simplest — just run the command)
2. Direct Python API (import and call the collectors)
3. Plugin extension (register a custom audit section)
"""

# =========================================================================
# 1. CLI invocation — run from your terminal
# =========================================================================
#
#   # Basic report (table format)
#   netpicker audit report
#
#   # Filter by tag, output JSON
#   netpicker audit report --tag production --format json
#
#   # Save to file for emailing
#   netpicker audit report --format json --output /tmp/audit-$(date +%F).json
#
#   # Stricter freshness check (3 days instead of default 7)
#   netpicker audit report --stale-days 3
#
#   # Disable parallel fetching (useful for debugging)
#   netpicker audit report --no-parallel --stale-days 14
#

# =========================================================================
# 2. Direct Python API — embed in your own scripts
# =========================================================================

from netpicker_cli.api.client import ApiClient
from netpicker_cli.utils.config import load_settings
from netpicker_cli.commands.audit import (
    AuditReport,
    _collect_inventory,
    _collect_compliance,
    _collect_backups,
    _collect_policies,
)
from datetime import datetime, timezone


def run_audit_programmatically():
    """Run the audit using Python imports (no CLI subprocess)."""
    settings = load_settings()
    cli = ApiClient(settings)
    opts = {"stale_days": 7}

    try:
        sections = [
            _collect_inventory(cli, settings, opts),
            _collect_compliance(cli, settings, opts),
            _collect_backups(cli, settings, opts),
            _collect_policies(cli, settings, opts),
        ]

        report = AuditReport(
            tenant=settings.tenant,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            sections=sections,
        )

        # Convert to dict for processing
        report_dict = report.to_dict()
        print(f"Overall status: {report_dict['overall_status']}")

        for sec in report_dict["sections"]:
            print(f"  [{sec['status'].upper()}] {sec['name']}: {sec['summary']}")

        # Check for stale backups
        backups = next(s for s in report_dict["sections"] if s["name"] == "backups")
        if backups["summary"].get("stale", 0) > 0:
            print(f"\n  WARNING: {backups['summary']['stale']} devices have stale backups!")
            for item in backups["items"]:
                print(f"    - {item['ip']} ({item['device']}): {item['age_days']}d old")

    finally:
        cli.close()


# =========================================================================
# 3. Plugin extension — add your own audit section
# =========================================================================

from netpicker_cli.commands.audit import register_section, AuditSection


@register_section
def check_firmware_versions(cli, settings, options):
    """Example custom section: flag devices with outdated firmware.

    This section is automatically included whenever ``netpicker audit report``
    runs, because it was registered via ``@register_section``.
    """
    section = AuditSection(name="firmware_check")

    try:
        resp = cli.get(
            f"/api/v1/devices/{settings.tenant}",
            params={"size": 1000, "page": 1},
        ).json()

        devices = resp if isinstance(resp, list) else resp.get("items", [])
        outdated = []

        # Example: flag any device whose firmware field contains "15.2"
        for d in devices:
            fw = d.get("firmware", "") or ""
            if "15.2" in fw:
                outdated.append({
                    "ip": d.get("ipaddress"),
                    "name": d.get("name"),
                    "firmware": fw,
                })

        section.summary = {
            "total_checked": len(devices),
            "outdated": len(outdated),
        }
        section.items = outdated
        if outdated:
            section.status = "warning"

    except Exception as exc:
        section.status = "error"
        section.errors.append(str(exc))

    return section


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("NetPicker Audit — Programmatic Example")
    print("=" * 60)
    print()
    run_audit_programmatically()
