# src/netpicker_cli/commands/auth.py
from __future__ import annotations
from typing import Optional
import typer

from ..api.client import ApiClient
from ..api.errors import ApiError, NotFound
from ..utils.config import load_settings, save_config, clear_config
from ..utils.command_base import TyperCommand
from ..utils.helpers import (
    extract_items_from_response,
    format_duration,
    parse_duration,
)
from ..utils.output import OutputFormatter

app = typer.Typer(add_completion=False, no_args_is_help=True)

token_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(token_app, name="token", help="Create, list and revoke API tokens")

# Tokens are identified by their trailing characters, not their leading ones:
# every JWT shares the same header, and these all share a subject and claim
# set, so even a 100-character prefix fails to tell two tokens apart. The
# signature at the end is the only reliably distinguishing part.
_TOKEN_SUFFIX_LEN = 16


class LoginCommand(TyperCommand):
    """Command for user authentication and credential storage."""

    def __init__(self, base_url: str, tenant: str, token: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.tenant = tenant
        self.token = token

    def validate_args(self) -> None:
        """Validate login arguments."""
        if not self.base_url.strip():
            raise typer.BadParameter("Base URL cannot be empty")

    def execute(self) -> dict[str, str]:
        """Execute login logic and return credentials info."""
        if not self.token:
            self.token = typer.prompt("Enter API token", hide_input=True)

        # Normalize base URL
        self.base_url = self._normalize_base_url(self.base_url)

        # Persist credentials (returns True if saved to keyring)
        keyring_saved = save_config(base_url=self.base_url, tenant=self.tenant, token=self.token)

        return {
            "base_url": self.base_url,
            "tenant": self.tenant,
            "keyring_saved": keyring_saved,
        }

    def format_output(self, result: dict[str, str]) -> None:
        """Format and display login results."""
        typer.secho("✓ config saved", fg=typer.colors.GREEN)
        typer.echo(f"  Base URL: {result['base_url']}")
        typer.echo(f"  Tenant  : {result['tenant']}")
        typer.echo("")
        
        if result.get("keyring_saved"):
            typer.secho("✓ token saved to keyring", fg=typer.colors.GREEN)
        else:
            typer.secho("⚠ keyring not available - set token via environment variable:", fg=typer.colors.YELLOW)
            typer.echo(f"  export NETPICKER_TOKEN=\"<your-token>\"")
            typer.echo("")
        typer.echo("Tip: run `netpicker whoami` to verify.")

    @staticmethod
    def _normalize_base_url(u: str) -> str:
        u = (u or "").strip()
        if not u:
            return u
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        return u.rstrip("/")


class LogoutCommand(TyperCommand):
    """Command for removing stored authentication credentials."""

    def __init__(self, base_url: Optional[str] = None, tenant: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.base_url = base_url
        self.tenant = tenant

    def validate_args(self) -> None:
        """Validate logout arguments."""
        # base_url and tenant are optional now - if not provided, we just clear the config file
        pass

    def execute(self) -> dict[str, str]:
        """Execute logout logic."""
        removed_keyring = False
        removed_config = False
        
        # If base_url and tenant provided, try to remove from keyring
        if self.base_url and self.tenant:
            self.base_url = self._normalize_base_url(self.base_url)
            try:
                import keyring
                key = f"{self.base_url}:{self.tenant}"
                keyring.delete_password("netpicker-cli", key)
                removed_keyring = True
            except Exception:
                # Keyring not available or password doesn't exist
                pass
        
        # Always clear the config file
        removed_config = clear_config()

        return {
            "base_url": self.base_url or "",
            "tenant": self.tenant or "",
            "removed_keyring": removed_keyring,
            "removed_config": removed_config,
        }

    def format_output(self, result: dict[str, str]) -> None:
        """Format and display logout results."""
        if result.get("removed_keyring"):
            typer.secho("✓ token removed from keyring", fg=typer.colors.GREEN)
        if result.get("removed_config"):
            typer.secho("✓ config file cleared", fg=typer.colors.GREEN)
        if not result.get("removed_keyring") and not result.get("removed_config"):
            typer.echo("Nothing to clear")

    @staticmethod
    def _normalize_base_url(u: str) -> str:
        u = (u or "").strip()
        if not u:
            return u
        if not (u.startswith("http://") or u.startswith("https://")):
            u = "https://" + u
        return u.rstrip("/")


@app.command("login")
def login(
    base_url: str = typer.Option(..., "--base-url", help="API base URL (e.g., https://sandbox.netpicker.io)"),
    tenant: str = typer.Option(..., "--tenant", help="Tenant name (e.g., default)"),
    token: Optional[str] = typer.Option(None, "--token", help="Bearer token"),
) -> None:
    """
    Save credentials to the OS keyring and remember base_url/tenant for this CLI.
    """
    cmd = LoginCommand(base_url=base_url, tenant=tenant, token=token)
    cmd.run()


@app.command("logout")
def logout(
    base_url: Optional[str] = typer.Option(None, "--base-url", help="API base URL (optional, for keyring cleanup)"),
    tenant: Optional[str] = typer.Option(None, "--tenant", help="Tenant name (optional, for keyring cleanup)"),
) -> None:
    """
    Remove saved credentials. Clears the config file and optionally removes token from keyring.
    
    If --base-url and --tenant are provided, also removes the token from the OS keyring.
    """
    cmd = LogoutCommand(base_url=base_url, tenant=tenant)
    cmd.run()


_MAX_PAGE_SIZE = 1000


def _fetch_tokens_page(cli: ApiClient, params: dict) -> tuple[list[dict], int]:
    """Fetch one page of API tokens, returning its items and the overall total."""
    data = cli.get("/api/v1/auth/api-token", params=params).json()
    total = data.get("total", 0) if isinstance(data, dict) else 0
    return extract_items_from_response(data), total


def _fetch_tokens(cli: ApiClient, params: dict) -> list[dict]:
    """Fetch API tokens, following pagination until every token is collected.

    Used where completeness matters more than page size, such as resolving a
    partial token: a match sitting on page two is still a match.
    """
    params = {**params, "size": min(params.get("size", _MAX_PAGE_SIZE), _MAX_PAGE_SIZE)}
    collected: list[dict] = []
    page = 1
    while True:
        items, total = _fetch_tokens_page(cli, {**params, "page": page})
        collected.extend(items)
        if not items or len(collected) >= total:
            return collected
        page += 1


def _summarize_scopes(scopes: list | None, limit: int = 3) -> str:
    """Summarize a scope list so one wide-scoped token cannot blow up the table."""
    scopes = scopes or []
    if not scopes:
        return "-"
    if len(scopes) <= limit:
        return ", ".join(scopes)
    return f"{', '.join(scopes[:limit])} +{len(scopes) - limit} more"


def _token_label(token: str) -> str:
    """Abbreviate a token to its distinguishing trailing characters."""
    token = token or ""
    if len(token) <= _TOKEN_SUFFIX_LEN:
        return token
    return f"…{token[-_TOKEN_SUFFIX_LEN:]}"


def _resolve_token(cli: ApiClient, needle: str) -> str:
    """Resolve a partial token to the one full token it identifies.

    Tokens carry no name or id, so the token's own text is the only handle.
    Matching prefers the trailing characters, since that is what listings show
    and what actually differs between tokens; a leading fragment is accepted
    too, for the case where someone pastes the start of a token.
    """
    needle = needle.lstrip("…")
    tokens = [item.get("token", "") for item in _fetch_tokens(cli, {"size": 1000})]
    if needle in tokens:
        return needle

    matches = [t for t in tokens if t.endswith(needle)]
    if not matches:
        matches = [t for t in tokens if t.startswith(needle)]

    if not matches:
        typer.secho(f"No API token matches '{needle}'", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if len(matches) > 1:
        typer.secho(
            f"'{needle}' matches {len(matches)} tokens; use more trailing characters "
            "to narrow it (see: netpicker auth token list).",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    return matches[0]


@token_app.command("create")
def create_token(
    ttl: str = typer.Option(
        "90d", "--ttl",
        help="Lifetime as 30m/12h/90d/2w, a number of seconds, or 'never'",
    ),
    scopes: Optional[str] = typer.Option(
        None, "--scopes",
        help="Comma-separated scopes to grant (default: your own scopes). See: netpicker auth scopes",
    ),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
) -> None:
    """
    Create an API token.

    Calls POST /api/v1/auth/api-token. A lifetime is always sent explicitly:
    the API's own default is 15 seconds, which would make the token unusable.

    Scopes are capped by your own: requesting more than you hold grants only
    the overlap, so the token can never exceed your access.
    """
    try:
        ttl_seconds = parse_duration(ttl)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--ttl")

    requested = [s.strip() for s in scopes.split(",") if s.strip()] if scopes else None

    s = load_settings()
    cli = ApiClient(s)

    payload: dict = {}
    if requested:
        payload["scopes"] = requested

    try:
        data = cli.post(
            "/api/v1/auth/api-token", json=payload, params={"ttl": ttl_seconds}
        ).json()
    except ApiError as e:
        typer.secho(f"Failed to create API token: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
        return

    granted = data.get("scopes") or []
    typer.secho("✓ API token created", fg=typer.colors.GREEN)
    typer.echo(f"  Expires : {data.get('expires', '')} ({format_duration(ttl_seconds)})")
    typer.echo(f"  Scopes  : {', '.join(granted) if granted else '(none)'}")
    typer.echo("")
    typer.echo(data.get("token", ""))
    typer.echo("")
    if requested and set(requested) - set(granted):
        dropped = ", ".join(sorted(set(requested) - set(granted)))
        typer.secho(
            f"⚠ not granted (outside your own scopes): {dropped}",
            fg=typer.colors.YELLOW,
        )
    typer.echo("Tip: export NETPICKER_TOKEN=\"<token>\" or run `netpicker auth login --token <token>`")


@token_app.command("list")
def list_tokens(
    revoked: Optional[bool] = typer.Option(
        None, "--revoked/--active", help="Show only revoked, or only active, tokens",
    ),
    page: int = typer.Option(1, "--page", help="Page number"),
    size: int = typer.Option(50, "--size", help="Page size"),
    all_: bool = typer.Option(False, "--all", help="Fetch all pages"),
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
) -> None:
    """
    List API tokens.

    Calls GET /api/v1/auth/api-token. Table output abbreviates each token to
    the trailing characters that `netpicker auth token revoke` accepts; use
    --format json for the full values.

    Tokens have no creation timestamp, so the API cannot order them by age and
    a newly created token may not land on the first page. Use --all when you
    need the complete set.
    """
    s = load_settings()
    cli = ApiClient(s)

    params: dict = {}
    if revoked is not None:
        params["revoked"] = revoked

    total = 0
    try:
        if all_:
            items = _fetch_tokens(cli, params)
            total = len(items)
        else:
            items, total = _fetch_tokens_page(
                cli, {**params, "page": page, "size": size}
            )
    except ApiError as e:
        typer.secho(f"Failed to list API tokens: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(items)
        return

    if not items:
        typer.echo("No API tokens found.")
        return

    rows = [
        {
            "token": _token_label(it.get("token", "")),
            "user": it.get("user", ""),
            "expires": it.get("expires", ""),
            "status": "revoked" if it.get("revoked") else "active",
            "scopes": _summarize_scopes(it.get("scopes")),
        }
        for it in items
    ]
    OutputFormatter(format="table").output(
        rows, headers=["token", "user", "expires", "status", "scopes"]
    )
    typer.echo("")
    typer.echo("Tokens are shown by their last characters; pass one to `auth token revoke`.")
    if not all_ and total > len(items):
        typer.echo(
            f"Showing {len(items)} of {total} tokens — use --all to see the rest."
        )


@token_app.command("revoke")
def revoke_token(
    token: str = typer.Argument(..., help="Full token, or enough of its end to be unique"),
    force: bool = typer.Option(False, "--force", "-f", help="Do not ask for confirmation"),
) -> None:
    """
    Revoke an API token.

    Calls DELETE /api/v1/auth/api-token/{token}. A partial token is resolved
    against the token listing first, and must match exactly one token.
    """
    s = load_settings()
    cli = ApiClient(s)

    try:
        full_token = _resolve_token(cli, token)
    except ApiError as e:
        typer.secho(f"Failed to look up API token: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if not force:
        typer.confirm(f"Revoke API token {_token_label(full_token)}?", abort=True)

    try:
        cli.delete(f"/api/v1/auth/api-token/{full_token}")
    except NotFound:
        typer.secho("API token not found (already revoked?)", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except ApiError as e:
        typer.secho(f"Failed to revoke API token: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"✓ revoked {_token_label(full_token)}", fg=typer.colors.GREEN)


@app.command("scopes")
def scopes(
    json_out: bool = typer.Option(False, "--json", "--json-out", help="[DEPRECATED: use --format json] Output JSON"),
    format: str = typer.Option("table", "--format", help="Output format: table, json, csv, yaml"),
    output_file: Optional[str] = typer.Option(None, "--output", help="Write output to file"),
) -> None:
    """
    List the scopes the server accepts.

    Calls GET /api/v1/auth/scopes. Useful for picking values for
    `netpicker auth token create --scopes`.
    """
    s = load_settings()
    cli = ApiClient(s)

    try:
        data = cli.get("/api/v1/auth/scopes").json()
    except ApiError as e:
        typer.secho(f"Failed to list scopes: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    if json_out:
        format = "json"
    if format != "table" or output_file:
        OutputFormatter(format=format, output_file=output_file).output(data)
        return

    if not data:
        typer.echo("No scopes reported.")
        return
    for scope in data:
        typer.echo(scope)
