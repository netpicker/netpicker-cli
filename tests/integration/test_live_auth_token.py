"""
Live integration tests for API token management.

Prerequisites:
  1. Authenticate first:  netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
  2. Run with:  python -m pytest tests/integration/test_live_auth_token.py -v -s

These tests create short-lived API tokens and revoke them again. Revocation is
a soft delete server-side, so revoked tokens remain listed with
``revoked: true``; nothing else in the tenant is touched.

To skip these tests in CI, the marker ``live`` is applied — add
``-m "not live"`` to your pytest invocation.
"""

import json
import os
from contextlib import contextmanager
import pytest
from typer.testing import CliRunner
from netpicker_cli.cli import app

pytestmark = pytest.mark.live

runner = CliRunner()


@contextmanager
def using_token(token):
    """Run a block authenticated as ``token``, then restore the caller's own.

    Restoring matters: clearing NETPICKER_TOKEN outright would also drop the
    ambient credential, leaving the cleanup that follows unauthenticated — and
    silently leaking the token it was meant to revoke.
    """
    previous = os.environ.get("NETPICKER_TOKEN")
    os.environ["NETPICKER_TOKEN"] = token
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("NETPICKER_TOKEN", None)
        else:
            os.environ["NETPICKER_TOKEN"] = previous


@pytest.fixture(scope="module")
def ensure_auth():
    """Verify the CLI can reach the API before exercising token commands."""
    result = runner.invoke(app, ["whoami", "--format", "json"])
    if result.exit_code != 0:
        pytest.skip(f"not authenticated: {result.output}")
    return json.loads(result.stdout)


def _create(*args):
    """Create a token, returning the parsed response."""
    result = runner.invoke(app, [
        "auth", "token", "create", "--format", "json", *args,
    ])
    assert result.exit_code == 0, f"create failed:\n{result.output}"
    return json.loads(result.stdout)


def _revoke(token, required=True):
    """Revoke a token by its trailing characters.

    Asserts success by default so a failed cleanup surfaces as a test failure
    rather than quietly leaving a usable credential behind.
    """
    result = runner.invoke(app, ["auth", "token", "revoke", token[-16:], "--force"])
    if required:
        assert result.exit_code == 0, f"cleanup failed to revoke token:\n{result.output}"
    return result


class TestScopes:
    """netpicker auth scopes"""

    def test_01_scopes_lists_known_values(self, ensure_auth):
        """The server reports a non-empty scope list."""
        result = runner.invoke(app, ["auth", "scopes", "--format", "json"])
        assert result.exit_code == 0, result.output
        scopes = json.loads(result.stdout)
        assert isinstance(scopes, list) and scopes
        assert "devices:read" in scopes


class TestTokenLifecycle:
    """create → list → revoke, against the real API"""

    def test_02_create_returns_a_usable_token(self, ensure_auth):
        """A created token carries the requested scope and a future expiry."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        try:
            assert data["token"]
            assert data["scopes"] == ["devices:read"]
            assert data["expires"]
        finally:
            _revoke(data["token"])

    def test_03_created_token_authenticates(self, ensure_auth):
        """The token actually works for the scope it was granted."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        try:
            with using_token(data["token"]):
                result = runner.invoke(app, ["devices", "list", "--format", "json"])
            assert result.exit_code == 0, result.output
        finally:
            _revoke(data["token"])

    def test_03b_created_token_is_scope_limited(self, ensure_auth):
        """A devices:read token must be refused a write operation."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        try:
            with using_token(data["token"]):
                result = runner.invoke(app, [
                    "devices", "create", "203.0.113.251",
                    "--name", "scope-probe", "--platform", "cisco_ios",
                    "--vault", "default",
                ])
            assert result.exit_code != 0, "write succeeded without devices:write"
        finally:
            _revoke(data["token"])

    def test_04_scopes_cannot_exceed_the_callers_own(self, ensure_auth):
        """Requested scopes are intersected with what the caller holds."""
        own = set(ensure_auth.get("scopes") or [])
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        try:
            assert set(data["scopes"]) <= own or not own
        finally:
            _revoke(data["token"])

    def test_05_token_appears_in_the_listing(self, ensure_auth):
        """--all is needed: tokens have no creation order, so a new one may
        not be on page 1 of a tenant with many tokens."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        try:
            result = runner.invoke(app, [
                "auth", "token", "list", "--all", "--format", "json",
            ])
            assert result.exit_code == 0, result.output
            tokens = [t["token"] for t in json.loads(result.stdout)]
            assert data["token"] in tokens
        finally:
            _revoke(data["token"])

    def test_06_revoke_marks_the_token_revoked(self, ensure_auth):
        """Revocation is a soft delete: the token stays listed, flagged revoked."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        result = _revoke(data["token"])
        assert result.exit_code == 0, result.output

        # --all is required: revoked tokens accumulate past one page, and there
        # is no creation order that would put the newest first.
        listing = runner.invoke(app, [
            "auth", "token", "list", "--revoked", "--all", "--format", "json",
        ])
        assert listing.exit_code == 0
        revoked = [t["token"] for t in json.loads(listing.stdout)]
        assert data["token"] in revoked

    def test_07_revoked_token_no_longer_authenticates(self, ensure_auth):
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        _revoke(data["token"])

        with using_token(data["token"]):
            result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code != 0, "a revoked token must not authenticate"


class TestTokenResolution:
    """Partial-token matching against real JWTs"""

    def test_08_shared_jwt_header_is_ambiguous(self, ensure_auth):
        """Every JWT starts the same way, so a leading fragment must be refused.

        This is the case mocked fixtures miss: real tokens for one user share
        over a hundred leading characters.
        """
        result = runner.invoke(app, [
            "auth", "token", "revoke", "eyJhbGciOiJIUzI1NiIsInR5", "--force",
        ])
        assert result.exit_code == 1
        assert "matches" in result.output

    def test_09_unknown_token_is_refused(self, ensure_auth):
        result = runner.invoke(app, [
            "auth", "token", "revoke", "definitely-not-a-real-token", "--force",
        ])
        assert result.exit_code == 1
        assert "No API token matches" in result.output

    def test_10_listing_abbreviates_to_the_suffix(self, ensure_auth):
        """Table output shows trailing characters, never the whole JWT."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        try:
            result = runner.invoke(app, ["auth", "token", "list", "--all"])
            assert result.exit_code == 0, result.output
            assert data["token"] not in result.output
            assert data["token"][-16:] in result.output
        finally:
            _revoke(data["token"])

    def test_11_revoke_finds_tokens_beyond_the_first_page(self, ensure_auth):
        """Resolution pages through the listing, so position cannot hide a token."""
        data = _create("--ttl", "1h", "--scopes", "devices:read")
        listing = runner.invoke(app, [
            "auth", "token", "list", "--all", "--format", "json",
        ])
        assert listing.exit_code == 0
        tokens = [t["token"] for t in json.loads(listing.stdout)]
        if len(tokens) <= 50:
            _revoke(data["token"])
            pytest.skip("fewer than one page of tokens; nothing to prove")
        _revoke(data["token"])


class TestTtlHandling:
    """--ttl must never fall through to the API's 15-second default"""

    def test_12_default_ttl_is_far_beyond_the_api_default(self, ensure_auth):
        """Omitting --ttl yields a long-lived token, not a 15-second one."""
        from datetime import datetime, timezone

        data = _create()
        try:
            expires = datetime.fromisoformat(
                data["expires"].replace("Z", "+00:00")
            )
            remaining = (expires - datetime.now(tz=timezone.utc)).total_seconds()
            assert remaining > 86400, f"token expires in {remaining}s — too soon"
        finally:
            _revoke(data["token"])

    def test_13_ttl_never_is_effectively_permanent(self, ensure_auth):
        data = _create("--ttl", "never")
        try:
            assert data["expires"].startswith(("2", "3")), data["expires"]
            year = int(data["expires"][:4])
            assert year > 2100, f"expected a far-future expiry, got {year}"
        finally:
            _revoke(data["token"])
