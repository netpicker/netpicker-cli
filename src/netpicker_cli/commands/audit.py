"""
Audit command — one-command network health report.

Orchestrates existing NetPicker API endpoints to produce a combined
inventory + compliance + backup-freshness report in a single invocation.

Usage:
    netpicker audit report
    netpicker audit report --tag production
    netpicker audit report --format json --output monday-report.json
    netpicker audit report --stale-days 3

Plugin support:
    Custom audit sections can be registered via ``register_section()``.
    Each section is a callable ``(cli, settings, options) -> AuditSection``.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Final, List, Optional, Sequence

import typer

from ..api.client import ApiClient, AsyncApiClient
from ..api.errors import ApiError
from ..utils.cache import get_session_cache
from ..utils.cli_helpers import handle_api_errors
from ..utils.config import Settings, load_settings
from ..utils.helpers import extract_items_from_response, format_tags_for_display
from ..utils.logging import get_logger, log_error_with_context, output_message
from ..utils.output import OutputFormat, OutputFormatter

logger = get_logger("netpicker_cli.commands.audit")

app = typer.Typer(add_completion=False)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_PAGE_SIZE: Final[int] = 1000
"""Hard cap on items fetched per API call (server-enforced)."""

_MAX_STALE_DAYS: Final[int] = 365
"""Upper bound for --stale-days to prevent nonsensical values."""

_MAX_DISPLAY_ITEMS: Final[int] = 15
"""Max notable items shown in table mode before truncation."""


class SectionStatus(str, Enum):
    """Possible statuses for an audit section."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AuditSection:
    """One section of an audit report (e.g. inventory, compliance, backups)."""

    name: str
    status: str = SectionStatus.OK
    summary: Dict[str, Any] = field(default_factory=dict)
    items: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Complete audit report aggregating multiple sections."""

    tenant: str
    generated_at: str = ""
    tag_filter: Optional[str] = None
    sections: List[AuditSection] = field(default_factory=list)

    def overall_status(self) -> str:
        """Return worst status across all sections."""
        for level in (SectionStatus.ERROR, SectionStatus.WARNING):
            if any(s.status == level for s in self.sections):
                return level
        return SectionStatus.OK

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON / YAML output."""
        return {
            "tenant": self.tenant,
            "generated_at": self.generated_at,
            "tag_filter": self.tag_filter,
            "overall_status": self.overall_status(),
            "sections": [
                {
                    "name": s.name,
                    "status": s.status,
                    "summary": s.summary,
                    "items": s.items,
                    "errors": s.errors,
                }
                for s in self.sections
            ],
        }


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

# Relaxed pattern: alphanumeric, hyphens, underscores, dots, colons.
_TAG_RE: Final[re.Pattern[str]] = re.compile(r"^[\w\-.:]+$")


def _validate_tag(tag: Optional[str]) -> Optional[str]:
    """Sanitise and validate a tag string.

    Returns the tag unchanged if valid, ``None`` if empty, or raises
    ``typer.BadParameter`` for illegal characters.
    """
    if not tag:
        return None
    tag = tag.strip()
    if not tag:
        return None
    if not _TAG_RE.match(tag):
        raise typer.BadParameter(
            f"Tag contains invalid characters: {tag!r}. "
            "Only alphanumeric, hyphens, underscores, dots, and colons are allowed."
        )
    return tag


def _validate_stale_days(days: int) -> int:
    """Ensure stale-days is within a sane range."""
    if days < 1:
        raise typer.BadParameter("--stale-days must be at least 1")
    if days > _MAX_STALE_DAYS:
        raise typer.BadParameter(f"--stale-days must be at most {_MAX_STALE_DAYS}")
    return days


# ---------------------------------------------------------------------------
# Plugin registry
# ---------------------------------------------------------------------------

SectionFactory = Callable[
    [ApiClient, Settings, Dict[str, Any]],  # (cli, settings, options)
    AuditSection,
]

_section_registry: List[SectionFactory] = []


def register_section(factory: SectionFactory) -> SectionFactory:
    """Register a custom audit section factory (plugin hook).

    Usage::

        from netpicker_cli.commands.audit import register_section, AuditSection

        @register_section
        def my_custom_check(cli, settings, options):
            # ... gather data ...
            return AuditSection(name="custom", summary={"check": "passed"})
    """
    _section_registry.append(factory)
    return factory


# ---------------------------------------------------------------------------
# Built-in section collectors
# ---------------------------------------------------------------------------

def _collect_inventory(
    cli: ApiClient, s: Settings, opts: Dict[str, Any],
) -> AuditSection:
    """Gather device inventory summary."""
    section = AuditSection(name="inventory")
    tag: Optional[str] = opts.get("tag")

    logger.debug("Collecting inventory (tag=%s)", tag)
    t0 = time.monotonic()

    try:
        if tag:
            resp = cli.post(
                f"/api/v1/devices/{s.tenant}/by_tags",
                json={"tags": [tag], "size": _MAX_PAGE_SIZE, "page": 1},
            ).json()
        else:
            resp = cli.get(
                f"/api/v1/devices/{s.tenant}",
                params={"size": _MAX_PAGE_SIZE, "page": 1},
            ).json()

        devices: List[Dict[str, Any]] = extract_items_from_response(resp)

        # Platform breakdown
        platforms: Dict[str, int] = {}
        for d in devices:
            plat: str = d.get("platform", "unknown")
            platforms[plat] = platforms.get(plat, 0) + 1

        section.summary = {
            "total_devices": len(devices),
            "platforms": platforms,
        }
        section.items = [
            {
                "ipaddress": d.get("ipaddress"),
                "name": d.get("name"),
                "platform": d.get("platform"),
                "tags": format_tags_for_display(d.get("tags")),
            }
            for d in devices
        ]
        logger.debug(
            "Inventory collected: %d devices in %.2fs",
            len(devices), time.monotonic() - t0,
        )
    except ApiError as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Failed to fetch devices: {exc}")
        log_error_with_context(exc, "audit.inventory")
    except Exception as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Unexpected error fetching devices: {exc}")
        log_error_with_context(exc, "audit.inventory")

    return section


def _collect_compliance(
    cli: ApiClient, s: Settings, opts: Dict[str, Any],
) -> AuditSection:
    """Gather compliance overview."""
    section = AuditSection(name="compliance")

    logger.debug("Collecting compliance overview")
    t0 = time.monotonic()

    try:
        data: Dict[str, Any] = cli.get(
            f"/api/v1/compliance/{s.tenant}/overview",
        ).json()

        devices_summary: Dict[str, Any] = data.get("devices", {}) or {}
        policies_summary: Dict[str, Any] = data.get("policies", {}) or {}

        section.summary = {
            "devices": devices_summary,
            "policies": policies_summary,
        }

        # Determine status from compliance data
        failed: int = devices_summary.get("failed", 0) or devices_summary.get(
            "critical", 0,
        )
        if failed:
            section.status = SectionStatus.WARNING

        logger.debug(
            "Compliance collected: failed=%d in %.2fs",
            failed, time.monotonic() - t0,
        )
    except ApiError as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Failed to fetch compliance overview: {exc}")
        log_error_with_context(exc, "audit.compliance")
    except Exception as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Unexpected error fetching compliance: {exc}")
        log_error_with_context(exc, "audit.compliance")

    return section


def _collect_backups(
    cli: ApiClient, s: Settings, opts: Dict[str, Any],
) -> AuditSection:
    """Gather recent-backup freshness, flag stale devices."""
    section = AuditSection(name="backups")
    stale_days: int = opts.get("stale_days", 7)

    logger.debug("Collecting backups (stale_days=%d)", stale_days)
    t0 = time.monotonic()

    try:
        data = cli.get(
            f"/api/v1/devices/{s.tenant}/recent-configs/",
            params={"limit": _MAX_PAGE_SIZE},
        ).json()
        items: List[Dict[str, Any]] = extract_items_from_response(data)

        now: datetime = datetime.now(timezone.utc)
        stale: List[Dict[str, Any]] = []
        errored: List[Dict[str, Any]] = []
        fresh: int = 0

        for it in items:
            ts_str: str = it.get("created_at") or it.get("upload_date") or ""
            device_name: str = (
                it.get("name") or it.get("device") or it.get("ipaddress", "")
            )
            ip: str = it.get("ipaddress", "")

            if it.get("readout_error"):
                errored.append({
                    "device": device_name,
                    "ip": ip,
                    "error": "readout_error",
                })
                continue

            if ts_str:
                try:
                    ts: datetime = datetime.fromisoformat(
                        ts_str.replace("Z", "+00:00"),
                    )
                    age_days: int = (now - ts).days
                    if age_days > stale_days:
                        stale.append({
                            "device": device_name,
                            "ip": ip,
                            "last_backup": ts_str,
                            "age_days": age_days,
                        })
                    else:
                        fresh += 1
                except (ValueError, TypeError):
                    logger.debug(
                        "Unparsable timestamp for device=%s: %r",
                        device_name, ts_str,
                    )
                    fresh += 1  # can't parse — be lenient
            else:
                fresh += 1

        section.summary = {
            "total_recent": len(items),
            "fresh": fresh,
            "stale": len(stale),
            "errored": len(errored),
            "stale_threshold_days": stale_days,
        }
        section.items = stale  # only include stale devices for attention
        if stale or errored:
            section.status = SectionStatus.WARNING

        logger.debug(
            "Backups collected: fresh=%d stale=%d errored=%d in %.2fs",
            fresh, len(stale), len(errored), time.monotonic() - t0,
        )
    except ApiError as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Failed to fetch recent configs: {exc}")
        log_error_with_context(exc, "audit.backups")
    except Exception as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Unexpected error fetching backups: {exc}")
        log_error_with_context(exc, "audit.backups")

    return section


def _collect_policies(
    cli: ApiClient, s: Settings, opts: Dict[str, Any],
) -> AuditSection:
    """List compliance policies and their enabled/disabled state."""
    section = AuditSection(name="policies")

    logger.debug("Collecting policies")
    t0 = time.monotonic()

    try:
        data = cli.get(f"/api/v1/policy/{s.tenant}").json()
        policies: List[Dict[str, Any]] = (
            data if isinstance(data, list)
            else extract_items_from_response(data)
        )

        enabled: int = sum(1 for p in policies if p.get("enabled"))
        disabled: int = len(policies) - enabled

        section.summary = {
            "total": len(policies),
            "enabled": enabled,
            "disabled": disabled,
        }
        section.items = [
            {
                "id": p.get("id", ""),
                "name": p.get("name", ""),
                "enabled": "Yes" if p.get("enabled") else "No",
            }
            for p in policies
        ]
        logger.debug(
            "Policies collected: %d total (%d enabled) in %.2fs",
            len(policies), enabled, time.monotonic() - t0,
        )
    except ApiError as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Failed to fetch policies: {exc}")
        log_error_with_context(exc, "audit.policies")
    except Exception as exc:
        section.status = SectionStatus.ERROR
        section.errors.append(f"Unexpected error fetching policies: {exc}")
        log_error_with_context(exc, "audit.policies")

    return section


# Built-in section factories in execution order
_BUILTIN_SECTIONS: Final[List[SectionFactory]] = [
    _collect_inventory,
    _collect_compliance,
    _collect_backups,
    _collect_policies,
]


# ---------------------------------------------------------------------------
# Async parallel collector
# ---------------------------------------------------------------------------

async def _collect_sections_parallel(
    settings: Settings,
    opts: Dict[str, Any],
    factories: Sequence[SectionFactory],
) -> List[AuditSection]:
    """Run section collectors concurrently using asyncio threads.

    Each collector uses a sync ``ApiClient`` internally, so we off-load them
    to the thread-pool executor via ``asyncio.to_thread``.

    Exceptions in individual collectors are caught and surfaced as
    error-status sections rather than crashing the entire audit.
    """
    loop = asyncio.get_running_loop()

    async def _run(factory: SectionFactory) -> AuditSection:
        cli = ApiClient(settings)
        try:
            return await loop.run_in_executor(None, factory, cli, settings, opts)
        except Exception as exc:
            # Graceful degradation: return an error section instead of
            # letting one failure blow up the entire parallel gather.
            name = getattr(factory, "__name__", "unknown").replace("_collect_", "")
            logger.warning("Parallel collector %s failed: %s", name, exc)
            return AuditSection(
                name=name,
                status=SectionStatus.ERROR,
                errors=[f"Collection failed: {exc}"],
            )
        finally:
            cli.close()

    tasks = [_run(f) for f in factories]
    return list(await asyncio.gather(*tasks, return_exceptions=False))


# ---------------------------------------------------------------------------
# Report rendering (table mode)
# ---------------------------------------------------------------------------

_STATUS_COLORS: Final[Dict[str, Any]] = {
    "ok": typer.colors.GREEN,
    "warning": typer.colors.YELLOW,
    "error": typer.colors.RED,
    "skipped": typer.colors.WHITE,
}

_STATUS_ICONS: Final[Dict[str, str]] = {
    "ok": "OK",
    "warning": "WARN",
    "error": "ERR",
    "skipped": "SKIP",
}


def _render_table(report: AuditReport) -> None:
    """Render the audit report as a human-readable table to stdout."""
    overall: str = report.overall_status()
    color = _STATUS_COLORS.get(overall, typer.colors.WHITE)
    icon: str = _STATUS_ICONS.get(overall, "?")

    typer.echo("")
    typer.secho(
        f"  NetPicker Audit Report — tenant: {report.tenant}",
        bold=True,
    )
    if report.tag_filter:
        typer.echo(f"  Tag filter: {report.tag_filter}")
    typer.echo(f"  Generated: {report.generated_at}")
    typer.secho(f"  Overall status: [{icon}]", fg=color, bold=True)
    typer.echo("")

    for section in report.sections:
        sec_color = _STATUS_COLORS.get(section.status, typer.colors.WHITE)
        sec_icon: str = _STATUS_ICONS.get(section.status, "?")
        typer.secho(
            f"  [{sec_icon}] {section.name.upper()}",
            fg=sec_color,
            bold=True,
        )

        # Print summary key-value pairs
        for key, val in section.summary.items():
            if isinstance(val, dict):
                typer.echo(f"      {key}:")
                for k2, v2 in val.items():
                    typer.echo(f"        {k2}: {v2}")
            else:
                typer.echo(f"      {key}: {val}")

        # Print errors if any
        for err in section.errors:
            typer.secho(f"      ! {err}", fg=typer.colors.RED)

        # Print notable items (stale backups, etc.) — cap to _MAX_DISPLAY_ITEMS
        if section.items and section.name == "backups":
            typer.echo(
                f"      Stale devices "
                f"(>{section.summary.get('stale_threshold_days', 7)}d):",
            )
            for it in section.items[:_MAX_DISPLAY_ITEMS]:
                typer.secho(
                    f"        {it.get('ip', '')} ({it.get('device', '')}) "
                    f"— last backup {it.get('age_days', '?')}d ago",
                    fg=typer.colors.YELLOW,
                )
            if len(section.items) > _MAX_DISPLAY_ITEMS:
                typer.echo(
                    f"        ... and {len(section.items) - _MAX_DISPLAY_ITEMS} more",
                )

        typer.echo("")

    typer.echo("  Tip: use --format json for machine-readable output")
    typer.echo("")


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Show help when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        typer.echo("Netpicker Audit Commands:")
        typer.echo("")
        typer.echo("Available commands:")
        typer.echo("  report    Generate a full network health audit report")
        typer.echo("")
        typer.echo("Examples:")
        typer.echo("  netpicker audit report")
        typer.echo("  netpicker audit report --tag production")
        typer.echo("  netpicker audit report --format json --output report.json")
        typer.echo("")
        typer.echo("Use 'netpicker audit report --help' for more information.")
        raise typer.Exit()


@app.command("report")
@handle_api_errors
def audit_report(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter devices by tag"),
    stale_days: int = typer.Option(
        7, "--stale-days", help="Days after which a backup is considered stale",
    ),
    parallel: bool = typer.Option(
        True, "--parallel/--no-parallel",
        help="Fetch audit sections in parallel (default: enabled)",
    ),
    json_out: bool = typer.Option(
        False, "--json", "--json-out",
        help="[DEPRECATED: use --format json] Output JSON",
    ),
    format: str = typer.Option(
        "table", "--format",
        help="Output format: table, json, csv, yaml",
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output",
        help="Write output to file",
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
) -> None:
    """
    Generate a full network health audit report.

    Gathers inventory, compliance posture, backup freshness, and policy
    status in one command. Ideal for morning stand-ups and management
    reports.

    Examples:

        netpicker audit report

        netpicker audit report --tag production --stale-days 3

        netpicker audit report --format json --output monday-report.json

        netpicker audit report --format csv --output audit.csv
    """
    # --- Input validation ---------------------------------------------------
    tag = _validate_tag(tag)
    stale_days = _validate_stale_days(stale_days)

    if format not in ("table", "json", "csv", "yaml"):
        raise typer.BadParameter(
            f"Unsupported format: {format!r}. Choose from: table, json, csv, yaml.",
        )

    s: Settings = load_settings()
    logger.info("Starting audit report for tenant=%s tag=%s", s.tenant, tag)

    opts: Dict[str, Any] = {
        "tag": tag,
        "stale_days": stale_days,
        "no_cache": no_cache,
    }

    if json_out:
        format = "json"

    # Collect all sections (built-in + plugins)
    factories: List[SectionFactory] = list(_BUILTIN_SECTIONS) + list(_section_registry)

    # Only show progress on stdout for table format; for structured formats
    # skip the message so it doesn't pollute the machine-readable output.
    is_structured: bool = format in ("json", "csv", "yaml")
    if not is_structured:
        typer.echo("Collecting audit data...")

    t0 = time.monotonic()

    if parallel:
        try:
            sections: List[AuditSection] = asyncio.run(
                _collect_sections_parallel(s, opts, factories),
            )
        except Exception as exc:
            # Fallback to sequential if async fails
            logger.warning(
                "Parallel collection failed (%s), falling back to sequential", exc,
            )
            cli = ApiClient(s)
            try:
                sections = [f(cli, s, opts) for f in factories]
            finally:
                cli.close()
    else:
        cli = ApiClient(s)
        try:
            sections = [f(cli, s, opts) for f in factories]
        finally:
            cli.close()

    elapsed = time.monotonic() - t0
    logger.info(
        "Audit collection completed: %d sections in %.2fs", len(sections), elapsed,
    )

    # Build report
    report = AuditReport(
        tenant=s.tenant,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        tag_filter=tag,
        sections=sections,
    )

    # Output
    if format in ("json", "csv", "yaml"):
        formatter = OutputFormatter(format=format, output_file=output_file)
        if format == "csv":
            # Flatten sections into rows for CSV
            rows: List[Dict[str, Any]] = []
            for sec in report.sections:
                for key, val in sec.summary.items():
                    rows.append({
                        "section": sec.name,
                        "status": sec.status,
                        "metric": key,
                        "value": str(val),
                    })
            headers: List[str] = ["section", "status", "metric", "value"]
            formatter.output(rows, headers=headers)
        else:
            formatter.output(report.to_dict())
    else:
        # Human-friendly table rendering
        _render_table(report)
        if output_file:
            # Also write a JSON snapshot when table + --output
            formatter = OutputFormatter(format="json", output_file=output_file)
            formatter.output(report.to_dict())
            typer.echo(f"  Report saved to {output_file}")

    logger.debug("Overall status: %s", report.overall_status())

    # Exit code reflects overall status
    if report.overall_status() == SectionStatus.ERROR:
        raise typer.Exit(code=2)
