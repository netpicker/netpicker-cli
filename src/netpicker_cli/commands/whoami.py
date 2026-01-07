import base64
import json
import datetime
import typer
from typing import Optional

from ..utils.config import load_settings
from ..utils.logging import output_message
from ..utils.output import OutputFormatter, OutputFormat

def _decode_jwt_unverified(token: str) -> dict:
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
    s = load_settings()

    # Re-obtain token the same way Settings.auth_headers() does (env > keyring)
    import os
    import keyring
    token = s.token or os.environ.get("NETPICKER_TOKEN") or keyring.get_password(
        "netpicker-cli", f"{s.base_url}:{s.tenant}"
    )

    claims = _decode_jwt_unverified(token or "")
    # Try a few common claim shapes
    email = (
        claims.get("claims", {}).get("email")
        or claims.get("email")
        or claims.get("sub")  # fallback
    )
    scopes = claims.get("scopes", []) or claims.get("claim", {}).get("scopes", [])
    exp = claims.get("exp")
    exp_iso = None
    if isinstance(exp, (int, float)):
        try:
            exp_iso = datetime.datetime.utcfromtimestamp(exp).isoformat()
        except Exception:
            pass

    row = {
        "base_url": s.base_url,
        "tenant": s.tenant,
        "email": email,
        "scopes": scopes,
        "token_expires": exp_iso,
    }

    if json_out:
        format = "json"

    formatter = OutputFormatter(format=format, output_file=output_file)
    if format in [OutputFormat.TABLE, OutputFormat.CSV]:
        headers = list(row.keys())
        formatter.output([row], headers=headers)
    else:
        formatter.output(row)
