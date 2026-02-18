"""Tests for CIDR-aware no_proxy bypass and CA bundle support."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from netpicker_cli.utils.proxy import (
    _get_no_proxy_entries,
    _host_from_url,
    _parse_cidr_networks,
    _parse_plain_ips,
    should_bypass_proxy,
)
from netpicker_cli.utils.config import Settings, load_settings


# ---------------------------------------------------------------------------
# proxy.py helpers
# ---------------------------------------------------------------------------

class TestGetNoProxyEntries:
    def test_empty_when_unset(self, monkeypatch):
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert _get_no_proxy_entries() == []

    def test_reads_lowercase(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "10.0.0.0/8, .example.com")
        monkeypatch.delenv("NO_PROXY", raising=False)
        entries = _get_no_proxy_entries()
        assert "10.0.0.0/8" in entries
        assert ".example.com" in entries

    def test_reads_uppercase(self, monkeypatch):
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.setenv("NO_PROXY", "172.16.0.0/12")
        assert _get_no_proxy_entries() == ["172.16.0.0/12"]

    def test_lowercase_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "10.0.0.0/8")
        monkeypatch.setenv("NO_PROXY", "192.168.0.0/16")
        # Python os.environ.get picks the lowercase first in our impl
        entries = _get_no_proxy_entries()
        assert "10.0.0.0/8" in entries


class TestParseCidrNetworks:
    def test_valid_cidr(self):
        nets = _parse_cidr_networks(["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])
        assert len(nets) == 3

    def test_ignores_non_cidr(self):
        nets = _parse_cidr_networks(["example.com", "10.1.2.3", ".local"])
        assert nets == []

    def test_ignores_invalid_cidr(self):
        nets = _parse_cidr_networks(["not/a/cidr", "999.999.999.999/8"])
        assert nets == []

    def test_ipv6_cidr(self):
        nets = _parse_cidr_networks(["fd00::/8"])
        assert len(nets) == 1


class TestParsePlainIps:
    def test_valid_ips(self):
        ips = _parse_plain_ips(["10.1.2.3", "192.168.1.1"])
        assert len(ips) == 2

    def test_ignores_hostnames(self):
        ips = _parse_plain_ips(["example.com", ".local"])
        assert ips == []

    def test_ignores_cidr(self):
        ips = _parse_plain_ips(["10.0.0.0/8"])
        assert ips == []


class TestHostFromUrl:
    def test_https(self):
        assert _host_from_url("https://10.1.2.3:8443/api") == "10.1.2.3"

    def test_http(self):
        assert _host_from_url("http://myhost.local") == "myhost.local"

    def test_no_scheme(self):
        # urlparse needs a scheme to correctly parse the host
        host = _host_from_url("10.1.2.3:8080")
        # Without scheme, urlparse may not parse host correctly, but our
        # function should still return something reasonable
        assert host is not None


# ---------------------------------------------------------------------------
# should_bypass_proxy – integration-style with IP-based base_url
# ---------------------------------------------------------------------------

class TestShouldBypassProxy:
    """Test the main bypass decision function using IP-literal URLs
    (avoids DNS resolution in tests)."""

    def test_bypass_cidr_match(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "10.0.0.0/8")
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert should_bypass_proxy("https://10.1.2.3:8443") is True

    def test_no_bypass_cidr_miss(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "10.0.0.0/8")
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert should_bypass_proxy("https://172.20.1.1:443") is False

    def test_bypass_plain_ip_match(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "192.168.1.100")
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert should_bypass_proxy("https://192.168.1.100") is True

    def test_bypass_wildcard(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "*")
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert should_bypass_proxy("https://anything.example.com") is True

    def test_no_bypass_when_unset(self, monkeypatch):
        monkeypatch.delenv("no_proxy", raising=False)
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert should_bypass_proxy("https://10.1.2.3") is False

    def test_bypass_multiple_cidrs(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16")
        monkeypatch.delenv("NO_PROXY", raising=False)
        assert should_bypass_proxy("https://172.20.5.6") is True
        assert should_bypass_proxy("https://192.168.100.1") is True
        assert should_bypass_proxy("https://8.8.8.8") is False

    def test_bypass_mixed_entries(self, monkeypatch):
        monkeypatch.setenv("no_proxy", "10.0.0.0/8, .example.com, 192.168.1.1")
        monkeypatch.delenv("NO_PROXY", raising=False)
        # CIDR match
        assert should_bypass_proxy("https://10.50.60.70") is True
        # Plain IP match
        assert should_bypass_proxy("https://192.168.1.1") is True
        # hostname – not a CIDR concern, would return False from our check
        # (httpx handles .example.com natively)
        assert should_bypass_proxy("https://8.8.8.8") is False


# ---------------------------------------------------------------------------
# Settings.ssl_verify property
# ---------------------------------------------------------------------------

class TestSslVerify:
    def test_default_is_true(self):
        s = Settings(base_url="https://x", tenant="t")
        assert s.ssl_verify is True

    def test_insecure_overrides_ca_bundle(self):
        s = Settings(base_url="https://x", tenant="t", insecure=True, ca_bundle="/some/ca.pem")
        assert s.ssl_verify is False

    def test_ca_bundle_used_when_not_insecure(self):
        s = Settings(base_url="https://x", tenant="t", ca_bundle="/etc/ssl/internal-ca.pem")
        assert s.ssl_verify == "/etc/ssl/internal-ca.pem"

    def test_insecure_without_ca_bundle(self):
        s = Settings(base_url="https://x", tenant="t", insecure=True)
        assert s.ssl_verify is False


# ---------------------------------------------------------------------------
# load_settings picks up NETPICKER_CA_BUNDLE
# ---------------------------------------------------------------------------

class TestLoadSettingsCaBundle:
    def test_ca_bundle_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://x")
        monkeypatch.setenv("NETPICKER_TENANT", "t")
        monkeypatch.setenv("NETPICKER_TOKEN", "tok")
        monkeypatch.setenv("NETPICKER_CA_BUNDLE", "/etc/ssl/my-ca.pem")
        s = load_settings()
        assert s.ca_bundle == "/etc/ssl/my-ca.pem"
        assert s.ssl_verify == "/etc/ssl/my-ca.pem"

    def test_no_ca_bundle(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://x")
        monkeypatch.setenv("NETPICKER_TENANT", "t")
        monkeypatch.setenv("NETPICKER_TOKEN", "tok")
        monkeypatch.delenv("NETPICKER_CA_BUNDLE", raising=False)
        s = load_settings()
        assert s.ca_bundle is None
        assert s.ssl_verify is True


# ---------------------------------------------------------------------------
# use_proxy setting (disabled by default)
# ---------------------------------------------------------------------------

class TestUseProxy:
    def test_default_is_false(self):
        s = Settings(base_url="https://x", tenant="t")
        assert s.use_proxy is False

    def test_explicit_true(self):
        s = Settings(base_url="https://x", tenant="t", use_proxy=True)
        assert s.use_proxy is True

    def test_load_settings_default_no_proxy(self, monkeypatch):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://x")
        monkeypatch.setenv("NETPICKER_TENANT", "t")
        monkeypatch.setenv("NETPICKER_TOKEN", "tok")
        monkeypatch.delenv("NETPICKER_USE_PROXY", raising=False)
        s = load_settings()
        assert s.use_proxy is False

    def test_load_settings_proxy_enabled(self, monkeypatch):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://x")
        monkeypatch.setenv("NETPICKER_TENANT", "t")
        monkeypatch.setenv("NETPICKER_TOKEN", "tok")
        monkeypatch.setenv("NETPICKER_USE_PROXY", "1")
        s = load_settings()
        assert s.use_proxy is True

    def test_load_settings_proxy_disabled_explicitly(self, monkeypatch):
        monkeypatch.setenv("NETPICKER_BASE_URL", "https://x")
        monkeypatch.setenv("NETPICKER_TENANT", "t")
        monkeypatch.setenv("NETPICKER_TOKEN", "tok")
        monkeypatch.setenv("NETPICKER_USE_PROXY", "false")
        s = load_settings()
        assert s.use_proxy is False
