"""
Property-based tests for JSON parsing resilience using Hypothesis.
Targets parsers for AI responses and MCP/CLI tool outputs.
"""

import json
from typing import Any

from hypothesis import given, strategies as st
from hypothesis.strategies import composite

from netpicker_cli.utils.validation import validate_json_payload, ValidationError
from netpicker_cli.commands.ai import fetch_latest_backup


# Base JSON primitives (avoid NaN/Infinity which are not JSON)
json_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50),
)

# Recursive JSON-like generator: deeply nested dicts/lists of scalars
json_like = st.recursive(
    json_scalar,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=30), children, max_size=5),
    ),
    max_leaves=20,
)


@given(json_like)
def test_validate_json_payload_handles_nested_structures(data: Any):
    """validate_json_payload should gracefully handle nested JSON-like inputs.
    - If given a dict, it should return the dict or raise ValidationError (never TypeError/KeyError).
    - If given a JSON string, it should parse or raise ValidationError without TypeError/KeyError.
    - If given a non-object JSON (list/primitive), it should raise ValidationError, not crash.
    """
    # Case 1: direct dict input
    if isinstance(data, dict):
        try:
            out = validate_json_payload(data)
            assert isinstance(out, dict)
        except ValidationError:
            # Acceptable: validation rejects unexpected structures
            pass

    # Case 2: JSON string input
    s = json.dumps(data)
    try:
        out = validate_json_payload(s)
        # Only valid if top-level is an object
        if isinstance(data, dict):
            assert isinstance(out, dict)
        else:
            # Non-object JSON should not succeed
            assert False, "Non-object JSON unexpectedly parsed as object"
    except ValidationError:
        # Expected for non-object or malformed cases
        pass


@given(json_like)
def test_fetch_latest_backup_never_raises_on_random_json(data: Any):
    """fetch_latest_backup should not crash on arbitrary JSON stdout from CLI.
    It should return a string message regardless of structure depth.
    """
    # Monkeypatch run_netpicker_command to simulate CLI output
    from unittest.mock import patch

    def fake_run(args):
        return {
            "stdout": json.dumps(data),
            "stderr": "",
            "returncode": 0,
            "success": True,
        }
    with patch("netpicker_cli.commands.ai.run_netpicker_command", fake_run):
        # Execute and ensure no TypeError/KeyError; function returns a string message/content
        result = fetch_latest_backup("1.2.3.4")
        assert isinstance(result, str)
