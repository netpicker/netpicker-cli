# src/netpicker_cli/commands/health.py
from __future__ import annotations
import time
from typing import Any, Optional
import typer

from ..utils.config import load_settings
from ..utils.logging import output_message
from ..api.client import ApiClient
from ..utils.command_base import TyperCommand


class HealthCommand(TyperCommand):
    """Command for checking system health and API connectivity."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def validate_args(self) -> None:
        """Validate health check arguments."""
        # No arguments to validate for health check
        pass

    def execute(self) -> dict[str, Any]:
        """Execute health check and return status data."""
        s = load_settings()
        client = ApiClient(s)
        t0 = time.perf_counter()
        data = client.get("/api/v1/status").json()
        ms = int((time.perf_counter() - t0) * 1000)

        return {
            "response_time_ms": ms,
            "api_base": data.get("api_base", s.base_url),
            "timezone": data.get("tz") or data.get("scheduler_timezone") or "UTC",
            "status": "OK",
        }

    def format_output(self, result: dict[str, Any]) -> None:
        """Format and display health check results."""
        output_message(
            f"{result['status']} ({result['response_time_ms']} ms) — "
            f"api_base={result['api_base']} tz={result['timezone']}"
        )


def do_health() -> None:
    """Perform a health check against the API."""
    cmd = HealthCommand()
    cmd.run()
