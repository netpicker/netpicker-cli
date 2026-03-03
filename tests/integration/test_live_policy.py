"""
Live integration tests for compliance-policy commands against a real Netpicker
environment.

Prerequisites:
  1. Authenticate first:
       netpicker auth login --base-url <URL> --tenant <TENANT> --token <TOKEN>
  2. Run with:
       python -m pytest tests/integration/test_live_policy.py -v -s

These tests cover ALL 9 policy subcommands:
  - list           – list all policies
  - show           – show a single policy
  - create         – create a new policy
  - update         – partial-update a policy (PATCH)
  - replace        – full replace a policy (PUT)
  - add-rule       – add a rule to a policy
  - remove-rule    – remove a rule from a policy
  - test-rule      – test/debug a rule against a config
  - execute-rules  – execute rules against devices

The tests create a temporary policy, manipulate it, then clean it up.

To skip in CI: ``-m "not live"``
"""

import json
import uuid
import pytest
from typer.testing import CliRunner
from netpicker_cli.cli import app

pytestmark = pytest.mark.live

runner = CliRunner()

# Unique identifiers — policy ids must match ^[^0-9]\w*$ (no hyphens)
_SUFFIX = uuid.uuid4().hex[:8]
TEST_POLICY_ID = f"pytest_{_SUFFIX}"
TEST_POLICY_NAME = f"Pytest Policy {_SUFFIX}"
TEST_RULE_NAME = f"rule_pytest_{_SUFFIX}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ensure_auth():
    """Verify credentials are configured before running any test."""
    result = runner.invoke(app, ["whoami", "--format", "json"])
    if result.exit_code != 0:
        pytest.skip(
            "Not authenticated — run `netpicker auth login` first.\n"
            f"  output: {result.output}"
        )
    return json.loads(result.output)


@pytest.fixture(scope="module")
def existing_policy(ensure_auth):
    """Discover an existing policy from the tenant for read-only tests.

    Returns the policy dict (id, name, ...).
    """
    result = runner.invoke(app, ["policy", "list", "--format", "json", "--no-cache"])
    assert result.exit_code == 0, f"policy list failed:\n{result.output}"
    policies = json.loads(result.output)
    if not policies:
        pytest.skip("No policies in tenant — cannot run read-only policy tests")
    return policies[0]


@pytest.fixture(scope="module")
def compliant_device(ensure_auth):
    """Find a device IP with compliance data for test-rule / execute-rules.

    Falls back to the first device in the compliance devices list.
    """
    result = runner.invoke(app, [
        "compliance", "devices", "--format", "json", "--size", "1",
    ])
    if result.exit_code != 0 or not result.output.strip():
        pytest.skip("No compliance devices available for test-rule/execute-rules")
    devices = json.loads(result.output)
    if not devices:
        pytest.skip("No compliance devices available")
    return devices[0]


@pytest.fixture(scope="module", autouse=True)
def cleanup_policy(ensure_auth):
    """Ensure the test policy is deleted even if a test fails."""
    yield
    # Best-effort cleanup — delete the policy we created
    from netpicker_cli.utils.config import load_settings
    from netpicker_cli.api.client import ApiClient
    try:
        s = load_settings()
        cli = ApiClient(s)
        cli.delete(f"/api/v1/policy/{s.tenant}/{TEST_POLICY_ID}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests — ordered as a natural workflow
# ---------------------------------------------------------------------------

class TestLivePolicyWorkflow:
    """End-to-end: list → show → create → update → replace → add-rule →
    test-rule → remove-rule → execute-rules."""

    # -- 1: List policies (read-only) ----------------------------------------

    def test_01_list_json(self, ensure_auth):
        """policy list --format json should return a list of policies."""
        result = runner.invoke(app, [
            "policy", "list", "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0, f"list failed:\n{result.output}"
        policies = json.loads(result.output)
        assert isinstance(policies, list)
        assert len(policies) > 0, "no policies returned"
        # Each policy should have at least an id and name
        assert policies[0].get("id"), "policy missing 'id' field"

    def test_02_list_table(self, ensure_auth):
        """policy list in table format should show column headers."""
        result = runner.invoke(app, ["policy", "list", "--no-cache"])
        assert result.exit_code == 0
        lower = result.output.lower()
        assert "id" in lower or "name" in lower, (
            f"table output missing expected headers:\n{result.output[:300]}"
        )

    # -- 2: Show a policy (read-only) ----------------------------------------

    def test_03_show_json(self, ensure_auth, existing_policy):
        """policy show <id> --format json should return policy details."""
        pid = existing_policy["id"]
        result = runner.invoke(app, [
            "policy", "show", pid, "--format", "json",
        ])
        assert result.exit_code == 0, f"show failed:\n{result.output}"
        data = json.loads(result.output)
        assert data.get("id") == pid

    def test_04_show_table(self, ensure_auth, existing_policy):
        """policy show <id> in table format should produce readable output."""
        pid = existing_policy["id"]
        result = runner.invoke(app, ["policy", "show", pid])
        assert result.exit_code == 0, f"show table failed:\n{result.output}"
        assert len(result.output.strip()) > 0

    # -- 3: Create a policy --------------------------------------------------

    def test_05_create_policy(self, ensure_auth):
        """policy create should create a new policy and return its details."""
        result = runner.invoke(app, [
            "policy", "create",
            "--name", TEST_POLICY_NAME,
            "--id", TEST_POLICY_ID,
            "--description", "Pytest integration test policy",
            "--author", "pytest",
            "--format", "json",
        ])
        assert result.exit_code == 0, f"create failed:\n{result.output}"
        data = json.loads(result.output)
        # Response may be a dict or list
        item = data[0] if isinstance(data, list) else data
        assert item.get("id") == TEST_POLICY_ID or item.get("name") == TEST_POLICY_NAME

    def test_06_created_policy_in_list(self, ensure_auth):
        """The just-created policy should appear in the policy list."""
        result = runner.invoke(app, [
            "policy", "list", "--format", "json", "--no-cache",
        ])
        assert result.exit_code == 0
        policies = json.loads(result.output)
        ids = [p.get("id") for p in policies]
        assert TEST_POLICY_ID in ids, (
            f"created policy {TEST_POLICY_ID} not found in list"
        )

    # -- 4: Update (PATCH) the policy ----------------------------------------
    # NOTE: The Netpicker server currently returns 500 for PATCH on policies.
    # These tests verify the CLI handles the error gracefully.

    def test_07_update_policy_graceful(self, ensure_auth):
        """policy update should handle server errors gracefully.

        Note: The current Netpicker server returns 500 for PATCH on policies.
        This test verifies the CLI handles the error without crashing.
        """
        result = runner.invoke(app, [
            "policy", "update", TEST_POLICY_ID,
            "--description", "Updated by pytest",
            "--format", "json",
        ])
        # Accept either success (if server is fixed) or graceful error exit
        if result.exit_code == 0:
            data = json.loads(result.output)
            item = data[0] if isinstance(data, list) else data
            assert item.get("policy_id") or item.get("id") or "updated" in str(item).lower()
        else:
            # Server 500 — verify CLI exits cleanly with an error message
            assert result.exit_code == 1, (
                f"unexpected exit code {result.exit_code}:\n{result.output}"
            )
            assert "error" in result.output.lower() or "500" in result.output

    def test_08_replace_policy_after_failed_patch(self, ensure_auth):
        """Since PATCH may have failed, confirm the policy still exists."""
        result = runner.invoke(app, [
            "policy", "show", TEST_POLICY_ID, "--format", "json",
        ])
        assert result.exit_code == 0, f"policy gone after PATCH attempt:\n{result.output}"
        data = json.loads(result.output)
        assert data.get("id") == TEST_POLICY_ID

    # -- 5: Replace (PUT) the policy -----------------------------------------

    def test_09_replace_policy(self, ensure_auth):
        """policy replace should fully replace the policy."""
        result = runner.invoke(app, [
            "policy", "replace", TEST_POLICY_ID,
            "--name", TEST_POLICY_NAME,
            "--description", "Replaced by pytest",
            "--author", "pytest-replace",
            "--format", "json",
        ])
        assert result.exit_code == 0, f"replace failed:\n{result.output}"
        data = json.loads(result.output)
        item = data[0] if isinstance(data, list) else data
        assert item.get("policy_id") or item.get("id") or "replaced" in str(item).lower()

    def test_10_replace_reflected_in_show(self, ensure_auth):
        """The replace should be visible via policy show."""
        result = runner.invoke(app, [
            "policy", "show", TEST_POLICY_ID, "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data.get("description") == "Replaced by pytest"

    # -- 6: Add a rule -------------------------------------------------------

    def test_11_add_rule(self, ensure_auth):
        """policy add-rule should add a rule to our test policy."""
        result = runner.invoke(app, [
            "policy", "add-rule", TEST_POLICY_ID,
            "--name", TEST_RULE_NAME,
            "--description", "Pytest test rule",
            "--severity", "LOW",
            "--simplified-text", "hostname",
            "--format", "json",
        ])
        assert result.exit_code == 0, f"add-rule failed:\n{result.output}"
        data = json.loads(result.output)
        # Response may be a plain string (the policy_id) or a dict
        if isinstance(data, str):
            assert data == TEST_POLICY_ID or TEST_RULE_NAME in data
        else:
            item = data[0] if isinstance(data, list) else data
            assert (
                item.get("rule") == TEST_RULE_NAME
                or TEST_RULE_NAME in str(item)
                or "added" in str(item).lower()
            )

    def test_12_rule_visible_in_show(self, ensure_auth):
        """The added rule should be visible in the policy details."""
        result = runner.invoke(app, [
            "policy", "show", TEST_POLICY_ID, "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        rules = data.get("rules", []) or []
        rule_names = [r.get("name") for r in rules]
        assert TEST_RULE_NAME in rule_names, (
            f"rule {TEST_RULE_NAME} not found in policy rules: {rule_names}"
        )

    # -- 7: Test (debug) a rule ----------------------------------------------

    def test_13_test_rule(self, ensure_auth, compliant_device):
        """policy test-rule should execute a rule debug against a config."""
        ip = compliant_device.get("ipaddress", "192.168.1.1")
        config_text = "hostname test-device\ninterface Loopback0\n ip address 1.2.3.4 255.255.255.255\nend"

        result = runner.invoke(app, [
            "policy", "test-rule", TEST_POLICY_ID,
            "--name", TEST_RULE_NAME,
            "--ip", ip,
            "--config", config_text,
            "--severity", "LOW",
            "--simplified-text", "hostname",
            "--format", "json",
        ])
        assert result.exit_code == 0, f"test-rule failed:\n{result.output}"
        data = json.loads(result.output)
        # Response should have some structure (result, errors, etc.)
        assert isinstance(data, dict), f"expected dict, got {type(data)}"

    # -- 8: Remove a rule ----------------------------------------------------

    def test_14_remove_rule(self, ensure_auth):
        """policy remove-rule should remove the rule we added."""
        result = runner.invoke(app, [
            "policy", "remove-rule", TEST_POLICY_ID, TEST_RULE_NAME,
            "--format", "json",
        ])
        assert result.exit_code == 0, f"remove-rule failed:\n{result.output}"

    def test_15_rule_gone_after_remove(self, ensure_auth):
        """The removed rule should no longer appear in policy show."""
        result = runner.invoke(app, [
            "policy", "show", TEST_POLICY_ID, "--format", "json",
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        rules = data.get("rules", []) or []
        rule_names = [r.get("name") for r in rules]
        assert TEST_RULE_NAME not in rule_names, (
            f"rule {TEST_RULE_NAME} still present after removal: {rule_names}"
        )

    # -- 9: Execute rules ----------------------------------------------------

    def test_16_execute_rules_by_policy(self, ensure_auth):
        """policy execute-rules --policies should trigger execution."""
        # Use an existing policy to avoid empty execution
        result = runner.invoke(app, [
            "policy", "list", "--format", "json", "--no-cache",
        ])
        policies = json.loads(result.output)
        enabled = [p for p in policies if p.get("enabled")]
        if not enabled:
            pytest.skip("No enabled policies to execute")

        policy_name = enabled[0]["id"]
        result = runner.invoke(app, [
            "policy", "execute-rules",
            "--policies", policy_name,
            "--format", "json",
        ])
        assert result.exit_code == 0, f"execute-rules failed:\n{result.output}"

    def test_17_execute_rules_by_device(self, ensure_auth, compliant_device):
        """policy execute-rules --devices should trigger for a specific device."""
        ip = compliant_device.get("ipaddress")
        result = runner.invoke(app, [
            "policy", "execute-rules",
            "--devices", ip,
            "--format", "json",
        ])
        assert result.exit_code == 0, f"execute-rules --devices failed:\n{result.output}"

    def test_18_execute_rules_table(self, ensure_auth, compliant_device):
        """policy execute-rules in table format should produce output."""
        ip = compliant_device.get("ipaddress")
        result = runner.invoke(app, [
            "policy", "execute-rules",
            "--devices", ip,
        ])
        assert result.exit_code == 0, f"execute-rules table failed:\n{result.output}"
        assert len(result.output.strip()) > 0
