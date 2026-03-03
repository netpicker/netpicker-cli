from __future__ import annotations
# src/netpicker_cli/commands/whoami.py
import base64
import json
import datetime
import os
from typing import Any, Dict, List, Optional

import typer

try:
    import keyring as _keyring  # type: ignore[import-untyped]
except Exception:  # ImportError, NoKeyringError, etc.
    _keyring = None  # type: ignore[assignment]

from ..utils.config import load_settings
from ..utils.output import OutputFormatter, OutputFormat
from ..utils.command_base import TyperCommand


class WhoamiCommand(TyperCommand):
    """Command for displaying current user authentication information."""

    def __init__(
        self,
        json_out: bool = False,
        format: str = "table",
        output_file: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.json_out = json_out
        self.format = format
        self.output_file = output_file

    def validate_args(self) -> None:
        """Validate whoami arguments."""
        # Arguments are validated by typer options
        pass

    def execute(self) -> Dict[str, Any]:
        """Execute whoami logic and return user information."""
        s = load_settings()

        # Re-obtain token the same way Settings.auth_headers() does (env > keyring)
        token: Optional[str] = s.token or os.environ.get("NETPICKER_TOKEN")

        if token is None and _keyring is not None:
            try:
                token = _keyring.get_password(
                    "netpicker-cli", f"{s.base_url}:{s.tenant}"
                )
            except Exception:
                token = None

        claims: Dict[str, Any] = self._decode_jwt_unverified(token or "")

        email: Optional[str] = (
            claims.get("claims", {}).get("email")
            or claims.get("email")
            or claims.get("sub")  # fallback
        )
        scopes: List[str] = claims.get("scopes", []) or claims.get("claim", {}).get("scopes", [])
        exp: Any = claims.get("exp")
        exp_iso: Optional[str] = None
        if isinstance(exp, (int, float)):
            try:
                exp_iso = datetime.datetime.utcfromtimestamp(exp).isoformat()
            except Exception:
                pass

        return {
            "base_url": s.base_url,
            "tenant": s.tenant,
            "email": email,
            "scopes": scopes,
            "token_expires": exp_iso,
        }

    def format_output(self, result: dict[str, Any]) -> None:
        """Format and display user information."""
        # Handle deprecated --json flag
        if self.json_out:
            self.format = "json"

        formatter = OutputFormatter(format=self.format, output_file=self.output_file)
        if self.format in [OutputFormat.TABLE, OutputFormat.CSV]:
            headers = list(result.keys())
            formatter.output([result], headers=headers)
        else:
            formatter.output(result)

    @staticmethod
    def _decode_jwt_unverified(token: str) -> Dict[str, Any]:
        """Decode JWT payload without verification.

        WARNING: This is intentionally unverified — used only for display
        purposes (whoami). Never use for authz decisions.
        """
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1] + "==="  # padding
        try:
            data = base64.urlsafe_b64decode(payload.encode("utf-8"))
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {}


def whoami(
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
):
    """Display current user information from JWT token."""
    cmd = WhoamiCommand(
        json_out=json_out,
        format=format,
        output_file=output_file
    )
    cmd.run()
