"""
Property-based tests for network validators using Hypothesis.
"""

import ipaddress
from hypothesis import given, strategies as st, assume

from netpicker_cli.utils.validation import validate_ip_address, ValidationError


def _is_valid_ip(value: str) -> bool:
    """Safe boolean wrapper around `validate_ip_address`.
    Returns True for valid IPv4/IPv6 strings, False otherwise, without raising.
    """
    try:
        _ = validate_ip_address(value)
        return True
    except ValidationError:
        return False


@given(st.ip_addresses())
def test_validate_ip_accepts_valid_ipv4_and_ipv6(addr):
    """Validator accepts all valid IPv4/IPv6 addresses and normalizes them."""
    s = str(addr)
    normalized = validate_ip_address(s)
    # Round-trip through stdlib to ensure normalization matches canonical form
    assert ipaddress.ip_address(normalized) == ipaddress.ip_address(s)


@given(st.text())
def test_validate_ip_rejects_random_non_ip_strings(s):
    """Validator never crashes and returns False for non-IP strings."""
    # Skip inputs that are actually valid IPs per stdlib
    try:
        ipaddress.ip_address(s.strip())
        assume(False)
    except ValueError:
        assume(True)

    assert _is_valid_ip(s) is False
