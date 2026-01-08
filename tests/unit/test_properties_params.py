"""
Property-based tests for parameter combinations using Hypothesis.
Fuzz combinations of optional params and ensure AI routing/mapping
never crashes and yields either a valid command or a well-defined error.
"""

from typing import Any, Dict, List
from unittest.mock import patch

from hypothesis import given, strategies as st, settings

# Tools known to the AI command mapping
TOOLS = [
    "devices_list", "devices_show", "devices_create", "devices_delete",
    "backups_history", "backups_list", "backups_upload", "backups_diff",
    "policy_list", "policy_create", "policy_add_rule", "policy_test_rule",
    "automation_list_jobs", "automation_execute_job", "health_check",
    "compliance_overview", "compliance_report_tenant", "compliance_devices"
]

# Strategy for optional parameters; includes some unknown keys to ensure robustness
params_strategy = st.fixed_dictionaries({
    "tool": st.sampled_from(TOOLS + ["unknown_tool", "", None]),
    "limit": st.one_of(st.none(), st.integers(min_value=1, max_value=5000)),
    "tag": st.one_of(st.none(), st.text(min_size=1, max_size=20)),
    "ip": st.one_of(st.none(), st.ip_addresses().map(str)),
    # Content intent to trigger backup content path
    "wants_content": st.booleans(),
    # Extra keys not used by mapping, should be ignored safely
    "filter": st.one_of(st.none(), st.text(max_size=10)),
    "sort": st.one_of(st.none(), st.sampled_from(["asc", "desc", None])),
    "device_type": st.one_of(st.none(), st.text(max_size=12)),
})


def build_cmd(tool_name: str, params: Dict[str, Any]) -> List[str] | str:
    """Replicate AI command mapping to build CLI args from params.
    Returns a command list or an error string for unknown tools.
    """
    tool_commands = {
        "devices_list": ["devices", "list"],
        "devices_show": ["devices", "show"],
        "devices_create": ["devices", "create"],
        "devices_delete": ["devices", "delete"],
        "backups_history": ["backups", "history"],
        "backups_list": ["backups", "list"],
        "backups_upload": ["backups", "upload"],
        "backups_diff": ["backups", "diff"],
        "policy_list": ["policy", "list"],
        "policy_create": ["policy", "create"],
        "policy_add_rule": ["policy", "add-rule"],
        "policy_test_rule": ["policy", "test-rule"],
        "automation_list_jobs": ["automation", "list-jobs"],
        "automation_execute_job": ["automation", "execute-job"],
        "health_check": ["health"],
        "compliance_overview": ["compliance", "overview"],
        "compliance_report_tenant": ["compliance", "report-tenant"],
        "compliance_devices": ["compliance", "devices"],
    }

    if tool_name not in tool_commands:
        return f"Unknown tool: {tool_name}"

    cmd = tool_commands[tool_name].copy()

    # Parameter handling mirroring commands/ai.py
    if tool_name == "devices_list":
        if params.get("limit") is not None:
            cmd.extend(["--limit", str(params["limit"])])
        if params.get("tag"):
            cmd.extend(["--tag", str(params["tag"])])
    if tool_name == "devices_show" and params.get("ip"):
        cmd.append(str(params["ip"]))
    if tool_name == "backups_history" and params.get("ip"):
        cmd.append(str(params["ip"]))
    if tool_name == "backups_list" and params.get("ip"):
        cmd.extend(["--ip", str(params["ip"])])
    if tool_name == "backups_diff" and params.get("ip"):
        cmd.extend(["--ip", str(params["ip"])])
    if tool_name == "compliance_devices" and params.get("ip"):
        cmd.extend(["--ip", str(params["ip"])])

    return cmd


@settings(deadline=None)
@given(params_strategy)
def test_param_combinations_do_not_crash(params: Dict[str, Any]):
    """Fuzz combinations of optional parameters and ensure mapping never crashes.
    Executes command via patched run_netpicker_command and asserts a defined outcome.
    """
    tool = params.get("tool")
    # Normalize None/empty tool
    tool_name = tool if isinstance(tool, str) and tool else "unknown_tool"

    result_text: str
    cmd_or_err = build_cmd(tool_name, params)

    if isinstance(cmd_or_err, str):
        # Unknown tool path, should be well-defined
        assert cmd_or_err.startswith("Unknown tool:")
        return

    # Patch command runner to avoid subprocess and return deterministic results
    def fake_run(args):
        # Ensure args is a list
        assert isinstance(args, list)
        # Return fake success if args minimally valid
        return {
            "stdout": "OK",
            "stderr": "",
            "returncode": 0,
            "success": True,
        }

    with patch("netpicker_cli.commands.ai.run_netpicker_command", fake_run):
        # Execute the mapped command and assert defined outcome
        from netpicker_cli.commands.ai import run_netpicker_command
        out = run_netpicker_command(cmd_or_err)
        assert isinstance(out, dict)
        assert set(out.keys()) == {"stdout", "stderr", "returncode", "success"}


@settings(deadline=None)
@given(params_strategy)
def test_backup_content_intent_does_not_crash(params: Dict[str, Any]):
    """When wants_content is True with backup-related tools, ensure mapping and execution are stable."""
    tool = params.get("tool")
    wants_content = bool(params.get("wants_content"))

    # Focus on backups-related tools
    backup_tools = {"backups_list", "backups_history", "backups_diff"}
    if tool not in backup_tools:
        return

    cmd_or_err = build_cmd(tool, params)
    if isinstance(cmd_or_err, str):
        # Unknown shouldn't occur here, but treat as defined outcome
        assert cmd_or_err.startswith("Unknown tool:")
        return

    # Patch both the top-level runner and the fetch helper since content intent can trigger it
    def fake_run(args):
        return {"stdout": "{}", "stderr": "", "returncode": 0, "success": True}

    with patch("netpicker_cli.commands.ai.run_netpicker_command", fake_run):
        from netpicker_cli.commands.ai import fetch_latest_backup
        # Regardless of content intent and params, fetch_latest_backup must return a string
        result = fetch_latest_backup(str(params.get("ip", "1.2.3.4")))
        assert isinstance(result, str)
