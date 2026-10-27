import json
import pytest
import respx
from unittest import mock
from typer.testing import CliRunner
from netpicker_cli.cli import app
from netpicker_cli.utils.config import Settings
from netpicker_cli.utils.helpers import NEVER_EXPIRES_SECONDS

BASE = "https://api.example.com"
TOKENS_URL = f"{BASE}/api/v1/auth/api-token"

# Realistic JWTs: identical header AND identical payload, differing only in
# the trailing signature. Live data looks exactly like this — tokens minted
# for one user share over 100 leading characters — so fixtures that differ
# early would let prefix-based matching pass a test it fails in practice.
_JWT_HEAD = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiI0OTA0NjEyNjQwNTYyNjI2NTYiLCJjbGFpbXMiOnsiZW1haWwiOiJhZG1pbkBhZG1pbi5jb20ifX0"
)
TOKEN_A = f"{_JWT_HEAD}.LVgER6p_tA-LtMzA"
TOKEN_B = f"{_JWT_HEAD}.Ng3Ca2FP_fAE7fac"


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_settings():
    return Settings(base_url=BASE, tenant="test-tenant", token="test-token")


def _paged(items, total=None, page=1, size=50):
    total = len(items) if total is None else total
    pages = max(1, -(-total // size))
    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


def _token_entry(token, revoked=False, scopes=("devices:read",)):
    return {
        "token": token,
        "expires": "2027-01-01T00:00:00Z",
        "revoked": revoked,
        "scopes": list(scopes),
        "claims": {"persistent_token": True},
        "user": "admin@admin.com",
        "exp": 1800000000,
    }


def _patch_settings(mock_settings):
    return mock.patch(
        "netpicker_cli.commands.auth.load_settings", return_value=mock_settings
    )


class TestTokenCreate:
    """netpicker auth token create"""

    @respx.mock
    def test_sends_explicit_ttl_in_seconds(self, runner, mock_settings):
        """A duration is converted to seconds and sent as the ttl query param."""
        route = respx.post(TOKENS_URL).respond(json=_token_entry(TOKEN_A))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create", "--ttl", "90d"])

        assert result.exit_code == 0, result.output
        assert route.calls.last.request.url.params["ttl"] == str(90 * 86400)

    @respx.mock
    def test_defaults_to_90d_not_the_api_default(self, runner, mock_settings):
        """Omitting --ttl must not fall through to the API's 15-second default."""
        route = respx.post(TOKENS_URL).respond(json=_token_entry(TOKEN_A))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create"])

        assert result.exit_code == 0, result.output
        assert route.calls.last.request.url.params["ttl"] == str(90 * 86400)

    @respx.mock
    def test_ttl_never_uses_api_maximum(self, runner, mock_settings):
        """--ttl never maps to the API's maximum lifetime."""
        route = respx.post(TOKENS_URL).respond(json=_token_entry(TOKEN_A))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create", "--ttl", "never"])

        assert result.exit_code == 0, result.output
        assert route.calls.last.request.url.params["ttl"] == str(NEVER_EXPIRES_SECONDS)

    @respx.mock
    def test_scopes_are_sent_as_a_list(self, runner, mock_settings):
        """Comma-separated scopes become a JSON list in the body."""
        route = respx.post(TOKENS_URL).respond(
            json=_token_entry(TOKEN_A, scopes=("devices:read", "jobs:read"))
        )

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "create", "--scopes", "devices:read, jobs:read",
            ])

        assert result.exit_code == 0, result.output
        body = json.loads(route.calls.last.request.content)
        assert body["scopes"] == ["devices:read", "jobs:read"]

    @respx.mock
    def test_prints_the_token_value(self, runner, mock_settings):
        """The created token is printed so it can be captured."""
        respx.post(TOKENS_URL).respond(json=_token_entry(TOKEN_A))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create"])

        assert result.exit_code == 0
        assert TOKEN_A in result.output

    @respx.mock
    def test_warns_when_requested_scopes_were_dropped(self, runner, mock_settings):
        """The API intersects scopes with the caller's own; say so when it does."""
        respx.post(TOKENS_URL).respond(json=_token_entry(TOKEN_A, scopes=("devices:read",)))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "create", "--scopes", "devices:read,admin",
            ])

        assert result.exit_code == 0
        assert "admin" in result.output
        assert "not granted" in result.output

    @respx.mock
    def test_json_output_is_machine_readable(self, runner, mock_settings):
        respx.post(TOKENS_URL).respond(json=_token_entry(TOKEN_A))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create", "--format", "json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout)["token"] == TOKEN_A

    def test_rejects_an_invalid_ttl(self, runner, mock_settings):
        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create", "--ttl", "banana"])

        assert result.exit_code != 0
        assert "banana" in result.output

    def test_rejects_a_non_positive_ttl(self, runner, mock_settings):
        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "create", "--ttl", "0"])

        assert result.exit_code != 0


class TestTokenList:
    """netpicker auth token list"""

    @respx.mock
    def test_lists_tokens(self, runner, mock_settings):
        respx.get(TOKENS_URL).respond(
            json=_paged([_token_entry(TOKEN_A), _token_entry(TOKEN_B, revoked=True)])
        )

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list"])

        assert result.exit_code == 0, result.output
        assert "active" in result.output
        assert "revoked" in result.output
        assert "admin@admin.com" in result.output

    @respx.mock
    def test_table_shows_the_distinguishing_suffix(self, runner, mock_settings):
        """Table output abbreviates to the trailing characters, not the shared head."""
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A)]))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list"])

        assert result.exit_code == 0
        assert TOKEN_A not in result.output
        assert TOKEN_A[-16:] in result.output

    @respx.mock
    def test_wide_scope_list_is_truncated(self, runner, mock_settings):
        """A token with many scopes must not blow up the table width."""
        many = [f"scope{i}:read" for i in range(26)]
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A, scopes=many)]))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list"])

        assert result.exit_code == 0
        assert "+23 more" in result.output
        assert "scope25:read" not in result.output

    @respx.mock
    def test_json_output_keeps_full_tokens(self, runner, mock_settings):
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A)]))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list", "--format", "json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout)[0]["token"] == TOKEN_A

    @respx.mock
    def test_revoked_filter_is_forwarded(self, runner, mock_settings):
        route = respx.get(TOKENS_URL).respond(json=_paged([]))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list", "--revoked"])

        assert result.exit_code == 0
        assert route.calls.last.request.url.params["revoked"] == "true"

    @respx.mock
    def test_warns_when_results_are_truncated(self, runner, mock_settings):
        """A tenant with more tokens than one page must say so."""
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A)], total=62))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list"])

        assert result.exit_code == 0, result.output
        assert "Showing 1 of 62 tokens" in result.output
        assert "--all" in result.output

    @respx.mock
    def test_all_follows_pagination(self, runner, mock_settings):
        """--all collects every page, not just the first."""
        page_one = _paged([_token_entry(TOKEN_A)], total=2, page=1, size=1)
        page_two = _paged([_token_entry(TOKEN_B)], total=2, page=2, size=1)
        respx.get(TOKENS_URL).mock(
            side_effect=[
                respx.MockResponse(200, json=page_one),
                respx.MockResponse(200, json=page_two),
            ]
        )

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "list", "--all", "--format", "json",
            ])

        assert result.exit_code == 0, result.output
        tokens = [t["token"] for t in json.loads(result.stdout)]
        assert tokens == [TOKEN_A, TOKEN_B]

    @respx.mock
    def test_empty_listing_is_not_an_error(self, runner, mock_settings):
        respx.get(TOKENS_URL).respond(json=_paged([]))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "list"])

        assert result.exit_code == 0
        assert "No API tokens found" in result.output


class TestTokenRevoke:
    """netpicker auth token revoke"""

    @respx.mock
    def test_revokes_by_unique_suffix(self, runner, mock_settings):
        """A trailing fragment is resolved to the full token before the DELETE."""
        respx.get(TOKENS_URL).respond(
            json=_paged([_token_entry(TOKEN_A), _token_entry(TOKEN_B)])
        )
        route = respx.delete(f"{TOKENS_URL}/{TOKEN_A}").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "revoke", TOKEN_A[-16:], "--force",
            ])

        assert result.exit_code == 0, result.output
        assert route.called

    @respx.mock
    def test_accepts_the_label_shown_in_listings(self, runner, mock_settings):
        """The '…abc' form printed by `list` can be pasted straight into revoke."""
        respx.get(TOKENS_URL).respond(
            json=_paged([_token_entry(TOKEN_A), _token_entry(TOKEN_B)])
        )
        route = respx.delete(f"{TOKENS_URL}/{TOKEN_A}").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "revoke", f"…{TOKEN_A[-16:]}", "--force",
            ])

        assert result.exit_code == 0, result.output
        assert route.called

    @respx.mock
    def test_resolves_a_token_on_a_later_page(self, runner, mock_settings):
        """Resolution pages through the listing, so a token's position in it
        cannot make it unrevokable."""
        page_one = _paged([_token_entry(TOKEN_A)], total=2, page=1, size=1)
        page_two = _paged([_token_entry(TOKEN_B)], total=2, page=2, size=1)
        respx.get(TOKENS_URL).mock(
            side_effect=[
                respx.MockResponse(200, json=page_one),
                respx.MockResponse(200, json=page_two),
            ]
        )
        route = respx.delete(f"{TOKENS_URL}/{TOKEN_B}").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "revoke", TOKEN_B[-16:], "--force",
            ])

        assert result.exit_code == 0, result.output
        assert route.called, "a token on page 2 must still be revokable"

    @respx.mock
    def test_long_shared_prefix_is_refused(self, runner, mock_settings):
        """Regression: real tokens share >100 leading chars, so a long prefix
        must still be treated as ambiguous rather than matching arbitrarily."""
        respx.get(TOKENS_URL).respond(
            json=_paged([_token_entry(TOKEN_A), _token_entry(TOKEN_B)])
        )
        delete_route = respx.delete(url__startswith=f"{TOKENS_URL}/").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "revoke", TOKEN_A[:100], "--force",
            ])

        assert result.exit_code == 1
        assert not delete_route.called, "a shared prefix must not resolve to one token"

    @respx.mock
    def test_revokes_by_full_token(self, runner, mock_settings):
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A)]))
        route = respx.delete(f"{TOKENS_URL}/{TOKEN_A}").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "revoke", TOKEN_A, "--force"])

        assert result.exit_code == 0, result.output
        assert route.called

    @respx.mock
    def test_ambiguous_match_is_refused(self, runner, mock_settings):
        """The shared JWT header matches every token, so it must be refused."""
        respx.get(TOKENS_URL).respond(
            json=_paged([_token_entry(TOKEN_A), _token_entry(TOKEN_B)])
        )
        delete_route = respx.delete(url__startswith=f"{TOKENS_URL}/").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "revoke", "eyJhbGciOiJIUzI1NiIsInR5", "--force",
            ])

        assert result.exit_code == 1
        assert "matches 2 tokens" in result.output
        assert not delete_route.called, "must not delete on an ambiguous match"

    @respx.mock
    def test_unknown_token_is_refused(self, runner, mock_settings):
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A)]))

        with _patch_settings(mock_settings):
            result = runner.invoke(app, [
                "auth", "token", "revoke", "nope-not-a-token", "--force",
            ])

        assert result.exit_code == 1
        assert "No API token matches" in result.output

    @respx.mock
    def test_confirms_before_revoking(self, runner, mock_settings):
        """Without --force the user is asked, and declining aborts."""
        respx.get(TOKENS_URL).respond(json=_paged([_token_entry(TOKEN_A)]))
        delete_route = respx.delete(f"{TOKENS_URL}/{TOKEN_A}").respond(status_code=204)

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "token", "revoke", TOKEN_A], input="n\n")

        assert result.exit_code != 0
        assert not delete_route.called


class TestScopes:
    """netpicker auth scopes"""

    @respx.mock
    def test_lists_available_scopes(self, runner, mock_settings):
        respx.get(f"{BASE}/api/v1/auth/scopes").respond(
            json=["devices:read", "devices:write", "jobs:read"]
        )

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "scopes"])

        assert result.exit_code == 0, result.output
        assert "devices:read" in result.output
        assert "jobs:read" in result.output

    @respx.mock
    def test_json_output(self, runner, mock_settings):
        respx.get(f"{BASE}/api/v1/auth/scopes").respond(json=["devices:read"])

        with _patch_settings(mock_settings):
            result = runner.invoke(app, ["auth", "scopes", "--format", "json"])

        assert result.exit_code == 0
        assert json.loads(result.stdout) == ["devices:read"]
