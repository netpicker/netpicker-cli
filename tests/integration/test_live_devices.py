"""
Live integration tests against a real Netpicker environment.

Prerequisites:
  1. Authenticate first:  netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
  2. Run with:  python -m pytest tests/integration/test_live_devices.py -v -s

These tests create a temporary device, verify it appears in the listing,
show its details, and then clean it up by deleting it.  The device IP
uses a TEST-NET-3 address (203.0.113.0/24, RFC 5737) to avoid collisions.

To skip these tests in CI, the marker ``live`` is applied — add
``-m "not live"`` to your pytest invocation.
"""

import json
import uuid
import pytest
from typer.testing import CliRunner
from netpicker_cli.cli import app

# ---------------------------------------------------------------------------
# Markers & fixtures
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.live  # allows: pytest -m "not live" to skip

runner = CliRunner()

# Generate a unique IP in TEST-NET-3 range so parallel runs don't collide
_SUFFIX = uuid.uuid4().int % 200 + 10          # 10-209
TEST_IP = f"203.0.113.{_SUFFIX}"
TEST_NAME = f"pytest-live-{uuid.uuid4().hex[:8]}"
TEST_PLATFORM = "cisco_ios"
TEST_VAULT = "default"
TEST_TAG = "pytest-live"


@pytest.fixture(scope="module")
def ensure_auth():
    """Verify that credentials are configured before running any test."""
    result = runner.invoke(app, ["whoami", "--format", "json"])
    if result.exit_code != 0:
        pytest.skip(
            "Not authenticated — run `netpicker auth login` first.\n"
            f"  output: {result.output}"
        )
    data = json.loads(result.output)
    assert data.get("base_url"), "base_url is empty — check your auth config"
    return data


# ---------------------------------------------------------------------------
# Tests — ordered as a natural workflow
# ---------------------------------------------------------------------------

class TestLiveDeviceWorkflow:
    """End-to-end: create → list → show → delete a device on a real instance."""

    # -- Step 1: Create -------------------------------------------------------

    def test_01_create_device(self, ensure_auth):
        """Create a test device and verify the CLI reports success."""
        result = runner.invoke(app, [
            "devices", "create", TEST_IP,
            "--name", TEST_NAME,
            "--platform", TEST_PLATFORM,
            "--vault", TEST_VAULT,
            "--tags", TEST_TAG,
            "--format", "json",
        ])
        assert result.exit_code == 0, f"create failed:\n{result.output}"
        data = json.loads(result.output)
        # The API may return a dict or wrap in a list — normalise
        item = data[0] if isinstance(data, list) else data
        assert item.get("ipaddress") == TEST_IP or TEST_IP in result.output

    # -- Step 2: Verify device exists via show --------------------------------

    def test_02_device_exists_via_show(self, ensure_auth):
        """The device we just created must be retrievable via `devices show`."""
        result = runner.invoke(app, [
            "devices", "show", TEST_IP, "--format", "json",
        ])
        assert result.exit_code == 0, f"show failed:\n{result.output}"
        data = json.loads(result.output)
        # show may return a dict or a single-element list
        item = data[0] if isinstance(data, list) else data
        assert item.get("ipaddress") == TEST_IP

    # -- Step 3: Show details -------------------------------------------------

    def test_03_show_device(self, ensure_auth):
        """Fetching the device by IP should return its details."""
        result = runner.invoke(app, [
            "devices", "show", TEST_IP, "--format", "json",
        ])
        assert result.exit_code == 0, f"show failed:\n{result.output}"
        data = json.loads(result.output)
        # show may return a dict or a single-element list
        item = data[0] if isinstance(data, list) else data
        assert item.get("ipaddress") == TEST_IP
        assert item.get("name") == TEST_NAME

    # -- Step 3b: Tag filtering -----------------------------------------------

    def test_03b_list_by_tag_returns_results(self, ensure_auth):
        """devices list --tag should return devices when tag exists.

        Note: the by_tags index is eventually consistent, so we test with
        tags already present in the tenant rather than our freshly-created
        test device.  We first discover an existing tag from the default
        device page, then query by it.
        """
        # Discover a real tag from the first page of devices
        discover = runner.invoke(app, [
            "devices", "list", "--format", "json", "--no-cache",
        ])
        assert discover.exit_code == 0
        devices = json.loads(discover.output)
        existing_tag = None
        for d in devices:
            tags = d.get("tags") or []
            if tags:
                existing_tag = tags[0] if isinstance(tags, list) else tags.split(",")[0]
                break
        if existing_tag is None:
            pytest.skip("No tagged devices in tenant — cannot test tag filter")

        # Now query by that tag
        result = runner.invoke(app, [
            "devices", "list", "--tag", existing_tag, "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0, f"list --tag failed:\n{result.output}"
        filtered = json.loads(result.output)
        assert len(filtered) > 0, f"--tag {existing_tag} returned no devices"

    def test_03c_list_by_nonexistent_tag_empty(self, ensure_auth):
        """devices list --tag with a bogus tag should return an empty list."""
        result = runner.invoke(app, [
            "devices", "list", "--tag", "no-such-tag-xyz-999", "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0
        devices = json.loads(result.output)
        assert devices == [], f"expected empty list, got {len(devices)} devices"

    # -- Step 4: Delete -------------------------------------------------------

    def test_04_delete_device(self, ensure_auth):
        """Delete the test device with --force (no interactive prompt)."""
        result = runner.invoke(app, [
            "devices", "delete", TEST_IP, "--force",
        ])
        assert result.exit_code == 0, f"delete failed:\n{result.output}"
        assert "deleted" in result.output.lower()

    # -- Step 5: Verify gone ---------------------------------------------------

    def test_05_device_gone_after_delete(self, ensure_auth):
        """After deletion the device should no longer be accessible."""
        result = runner.invoke(app, [
            "devices", "show", TEST_IP, "--format", "json",
        ])
        assert result.exit_code != 0, f"device still exists after delete:\n{result.output}"


# ---------------------------------------------------------------------------
# Safety net — cleanup even if a test fails mid-way
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def cleanup_device(ensure_auth):
    """Ensure the test device is deleted, even if a test assertion fails."""
    yield
    # Best-effort cleanup
    runner.invoke(app, ["devices", "delete", TEST_IP, "--force"])
