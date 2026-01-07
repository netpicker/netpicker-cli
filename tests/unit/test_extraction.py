"""
Unit tests for network configuration extraction logic.

Tests extraction of IP addresses, VLAN IDs, and interface names from raw configuration strings.
Uses pytest.mark.parametrize to test multiple vendor configuration patterns.
"""

import pytest
from netpicker_cli.utils.config_extraction import (
    extract_ip_addresses,
    extract_vlan_ids,
    extract_interface_names,
    extract_hostnames,
    extract_all,
    extract_by_platform,
    ExtractedConfig,
)


# ============================================================================
# Sample Network Configurations for Different Vendors
# ============================================================================

CISCO_IOS_CONFIG = """
version 15.6
hostname router1
!
ip domain-name example.com
!
interface GigabitEthernet0/0
 description WAN Interface
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
interface GigabitEthernet0/1
 description LAN Interface
 ip address 10.0.0.1 255.255.255.0
 no shutdown
!
interface Vlan100
 ip address 172.16.10.1 255.255.255.0
!
vlan 100
 name management
!
vlan 200
 name production
!
interface FastEthernet1/1
 switchport mode access
 switchport access vlan 100
!
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
!
end
"""

JUNIPER_JUNOS_CONFIG = """
set system host-name juniper-router1
set interfaces ge-0/0/0 unit 0 family inet address 10.1.1.1/24
set interfaces ge-0/0/1 unit 0 family inet address 10.2.2.1/24
set interfaces xe-1/0/0 unit 0 family inet address 192.168.100.1/24
set interfaces ae0 unit 0 family inet address 172.20.0.1/24
set vlans vlan-100 vlan-id 100
set vlans vlan-200 vlan-id 200
set vlans vlan-300 vlan-id 300
"""

ARISTA_EOS_CONFIG = """
!
hostname arista-switch1
!
vlan 10
   name guest
!
vlan 20
   name employee
!
vlan 30-40
   name range-vlans
!
interface Ethernet1
   description Uplink
   ip address 10.10.10.1/24
!
interface Ethernet2
   switchport access vlan 10
!
interface Management1
   ip address 192.168.99.1/24
!
interface Vlan10
   ip address 10.0.10.1/24
!
"""

PALO_ALTO_CONFIG = """
set deviceconfig system hostname palo-fw1
set network interface ethernet ethernet1/1 layer3 ip 192.168.50.1/24
set network interface ethernet ethernet1/2 layer3 ip 10.50.50.1/24
set network interface ethernet ethernet2/1 layer3 ip 172.30.0.1/24
set zone internal network layer3 ethernet1/1
set zone external network layer3 ethernet1/2
"""

CISCO_NXOS_CONFIG = """
hostname nexus-switch1
!
feature vpc
!
vlan 10,20,30
  name data-vlans
!
vlan 100
  name management
!
interface Ethernet1/1
  description Server Port
  switchport access vlan 10
!
interface Vlan10
  ip address 10.10.10.1/24
!
interface Vlan100
  ip address 192.168.100.1/24
!
interface mgmt0
  ip address 172.16.0.1/24
"""


# ============================================================================
# Test IP Address Extraction
# ============================================================================

class TestIPAddressExtraction:
    """Test IP address extraction from various configuration formats."""

    @pytest.mark.parametrize("config,expected_ips", [
        # Cisco IOS format
        (CISCO_IOS_CONFIG, ["10.0.0.1", "172.16.10.1", "192.168.1.0", "192.168.1.1"]),
        # Juniper Junos format
        (JUNIPER_JUNOS_CONFIG, ["10.1.1.1", "10.2.2.1", "172.20.0.1", "192.168.100.1"]),
        # Arista EOS format
        (ARISTA_EOS_CONFIG, ["10.0.10.1", "10.10.10.1", "192.168.99.1"]),
        # Palo Alto PAN-OS format
        (PALO_ALTO_CONFIG, ["10.50.50.1", "172.30.0.1", "192.168.50.1"]),
        # Cisco NX-OS format
        (CISCO_NXOS_CONFIG, ["10.10.10.1", "172.16.0.1", "192.168.100.1"]),
    ])
    def test_extract_ip_from_vendor_configs(self, config, expected_ips):
        """Test IP extraction from different vendor configurations."""
        result = extract_ip_addresses(config)
        assert sorted(result) == sorted(expected_ips)

    def test_extract_cisco_ios_ip_addresses(self):
        """Test Cisco IOS 'ip address X.X.X.X 255.255.255.0' format."""
        config = """
        interface GigabitEthernet0/0
         ip address 192.168.1.1 255.255.255.0
        interface GigabitEthernet0/1
         ip address 10.0.0.1 255.255.255.0
        """
        result = extract_ip_addresses(config)
        assert "192.168.1.1" in result
        assert "10.0.0.1" in result

    def test_extract_cidr_notation_ips(self):
        """Test CIDR notation 'ip address X.X.X.X/YY' format."""
        config = """
        interface Ethernet1
         ip address 172.16.0.1/24
        interface Ethernet2
         address 10.10.10.1/16
        """
        result = extract_ip_addresses(config)
        assert "172.16.0.1" in result
        assert "10.10.10.1" in result

    def test_extract_no_ips_from_empty_config(self):
        """Test that empty config returns no IPs."""
        result = extract_ip_addresses("")
        assert result == []

    def test_extract_validates_ip_octets(self):
        """Test that invalid IPs (octets > 255) are filtered out."""
        config = "ip address 999.999.999.999 255.255.255.0"
        result = extract_ip_addresses(config)
        # Should not include invalid IP
        assert "999.999.999.999" not in result

    def test_extract_multiple_ips_same_interface(self):
        """Test extraction when multiple IPs configured on same interface."""
        config = """
        interface GigabitEthernet0/0
         ip address 192.168.1.1 255.255.255.0
         ip address 192.168.1.2 255.255.255.0 secondary
        """
        result = extract_ip_addresses(config)
        assert "192.168.1.1" in result
        assert "192.168.1.2" in result

    def test_extract_deduplicates_ips(self):
        """Test that duplicate IPs are returned only once."""
        config = """
        interface Gi0/0
         ip address 10.0.0.1 255.255.255.0
        interface Gi0/1
         ip address 10.0.0.1 255.255.255.0
        """
        result = extract_ip_addresses(config)
        assert result.count("10.0.0.1") == 1


# ============================================================================
# Test VLAN ID Extraction
# ============================================================================

class TestVLANExtraction:
    """Test VLAN ID extraction from various configuration formats."""

    @pytest.mark.parametrize("config,expected_vlans", [
        # Cisco IOS format
        (CISCO_IOS_CONFIG, [100, 200]),
        # Juniper Junos format
        (JUNIPER_JUNOS_CONFIG, [100, 200, 300]),
        # Arista EOS format (includes range)
        (ARISTA_EOS_CONFIG, [10, 20, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40]),
        # Cisco NX-OS format (comma-separated)
        (CISCO_NXOS_CONFIG, [10, 20, 30, 100]),
    ])
    def test_extract_vlans_from_vendor_configs(self, config, expected_vlans):
        """Test VLAN extraction from different vendor configurations."""
        result = extract_vlan_ids(config)
        assert sorted(result) == sorted(expected_vlans)

    def test_extract_cisco_vlan_definitions(self):
        """Test extraction of 'vlan XXX' global definitions."""
        config = """
        vlan 100
         name management
        vlan 200
         name production
        vlan 999
         name guest
        """
        result = extract_vlan_ids(config)
        assert 100 in result
        assert 200 in result
        assert 999 in result

    def test_extract_switchport_access_vlan(self):
        """Test extraction of 'switchport access vlan XXX'."""
        config = """
        interface FastEthernet1/1
         switchport mode access
         switchport access vlan 50
        interface FastEthernet1/2
         switchport access vlan 60
        """
        result = extract_vlan_ids(config)
        assert 50 in result
        assert 60 in result

    def test_extract_juniper_vlan_id(self):
        """Test extraction of Juniper 'vlan-id XXX' format."""
        config = """
        set vlans employee vlan-id 10
        set vlans guest vlan-id 20
        set vlans iot vlan-id 30
        """
        result = extract_vlan_ids(config)
        assert sorted(result) == [10, 20, 30]

    def test_extract_vlan_ranges(self):
        """Test extraction of VLAN ranges like '30-40'."""
        config = """
        vlan 10-15
         name range1
        vlan 100,200,300-305
         name mixed
        """
        result = extract_vlan_ids(config)
        # Should include 10,11,12,13,14,15,100,200,300,301,302,303,304,305
        assert 10 in result
        assert 15 in result
        assert 100 in result
        assert 200 in result
        assert 300 in result
        assert 305 in result
        assert len([v for v in result if 10 <= v <= 15]) == 6

    def test_extract_vlan_comma_separated(self):
        """Test extraction of comma-separated VLANs."""
        config = "vlan 10,20,30,40"
        result = extract_vlan_ids(config)
        assert sorted(result) == [10, 20, 30, 40]

    def test_extract_no_vlans_from_empty_config(self):
        """Test that empty config returns no VLANs."""
        result = extract_vlan_ids("")
        assert result == []

    def test_extract_deduplicates_vlans(self):
        """Test that duplicate VLANs are returned only once."""
        config = """
        vlan 100
        vlan 100
        switchport access vlan 100
        """
        result = extract_vlan_ids(config)
        assert result.count(100) == 1


# ============================================================================
# Test Interface Name Extraction
# ============================================================================

class TestInterfaceExtraction:
    """Test interface name extraction from various configuration formats."""

    @pytest.mark.parametrize("config,expected_interfaces", [
        # Cisco IOS format
        (CISCO_IOS_CONFIG, ["FastEthernet1/1", "GigabitEthernet0/0", "GigabitEthernet0/1", "Vlan100"]),
        # Juniper Junos format
        (JUNIPER_JUNOS_CONFIG, ["ae0", "ge-0/0/0", "ge-0/0/1", "xe-1/0/0"]),
        # Arista EOS format
        (ARISTA_EOS_CONFIG, ["Ethernet1", "Ethernet2", "Management1", "Vlan10"]),
        # Palo Alto format
        (PALO_ALTO_CONFIG, ["ethernet1/1", "ethernet1/2", "ethernet2/1"]),
        # Cisco NX-OS format
        (CISCO_NXOS_CONFIG, ["Ethernet1/1", "Vlan10", "Vlan100", "mgmt0"]),
    ])
    def test_extract_interfaces_from_vendor_configs(self, config, expected_interfaces):
        """Test interface extraction from different vendor configurations."""
        result = extract_interface_names(config)
        assert sorted(result) == sorted(expected_interfaces)

    def test_extract_cisco_interface_names(self):
        """Test extraction of Cisco-style 'interface <name>'."""
        config = """
        interface GigabitEthernet0/0
         description WAN
        interface GigabitEthernet0/1
         description LAN
        interface Vlan100
         ip address 10.0.0.1 255.255.255.0
        """
        result = extract_interface_names(config)
        assert "GigabitEthernet0/0" in result
        assert "GigabitEthernet0/1" in result
        assert "Vlan100" in result

    def test_extract_juniper_interface_names(self):
        """Test extraction of Juniper 'set interfaces <name>'."""
        config = """
        set interfaces ge-0/0/0 unit 0 family inet address 10.0.0.1/24
        set interfaces xe-1/2/3 unit 0 description "Uplink"
        set interfaces ae0 aggregated-ether-options lacp active
        """
        result = extract_interface_names(config)
        assert "ge-0/0/0" in result
        assert "xe-1/2/3" in result
        assert "ae0" in result

    def test_extract_interface_with_special_chars(self):
        """Test extraction of interfaces with dots, slashes, dashes."""
        config = """
        interface Port-Channel1.100
        interface Tunnel0
        interface Loopback0
        interface Ten-GigabitEthernet1/1/1
        """
        result = extract_interface_names(config)
        assert "Port-Channel1.100" in result
        assert "Tunnel0" in result
        assert "Loopback0" in result
        assert "Ten-GigabitEthernet1/1/1" in result

    def test_extract_no_interfaces_from_empty_config(self):
        """Test that empty config returns no interfaces."""
        result = extract_interface_names("")
        assert result == []

    def test_extract_deduplicates_interfaces(self):
        """Test that duplicate interfaces are returned only once."""
        config = """
        interface GigabitEthernet0/0
         description First mention
        interface GigabitEthernet0/0
         description Duplicate
        """
        result = extract_interface_names(config)
        assert result.count("GigabitEthernet0/0") == 1


# ============================================================================
# Test Hostname Extraction
# ============================================================================

class TestHostnameExtraction:
    """Test hostname extraction from various configuration formats."""

    @pytest.mark.parametrize("config,expected_hostname", [
        (CISCO_IOS_CONFIG, "router1"),
        (JUNIPER_JUNOS_CONFIG, "juniper-router1"),
        (ARISTA_EOS_CONFIG, "arista-switch1"),
        (PALO_ALTO_CONFIG, "palo-fw1"),
        (CISCO_NXOS_CONFIG, "nexus-switch1"),
    ])
    def test_extract_hostname_from_vendor_configs(self, config, expected_hostname):
        """Test hostname extraction from different vendor configurations."""
        result = extract_hostnames(config)
        assert expected_hostname in result

    def test_extract_cisco_hostname(self):
        """Test extraction of Cisco 'hostname <name>'."""
        config = "hostname router1"
        result = extract_hostnames(config)
        assert "router1" in result

    def test_extract_juniper_hostname(self):
        """Test extraction of Juniper 'set system host-name <name>'."""
        config = "set system host-name edge-router"
        result = extract_hostnames(config)
        assert "edge-router" in result

    def test_extract_no_hostname_from_empty_config(self):
        """Test that empty config returns no hostnames."""
        result = extract_hostnames("")
        assert result == []


# ============================================================================
# Test Complete Extraction
# ============================================================================

class TestCompleteExtraction:
    """Test extraction of all configuration parameters together."""

    def test_extract_all_from_cisco_config(self):
        """Test extracting all parameters from a Cisco IOS config."""
        result = extract_all(CISCO_IOS_CONFIG)
        
        assert isinstance(result, ExtractedConfig)
        assert len(result.ip_addresses) > 0
        assert len(result.vlan_ids) > 0
        assert len(result.interface_names) > 0
        assert len(result.hostnames) > 0
        assert "router1" in result.hostnames
        assert 100 in result.vlan_ids
        assert "GigabitEthernet0/0" in result.interface_names

    def test_extract_all_from_juniper_config(self):
        """Test extracting all parameters from a Juniper Junos config."""
        result = extract_all(JUNIPER_JUNOS_CONFIG)
        
        assert isinstance(result, ExtractedConfig)
        assert "juniper-router1" in result.hostnames
        assert 100 in result.vlan_ids
        assert "ge-0/0/0" in result.interface_names
        assert "10.1.1.1" in result.ip_addresses

    def test_extract_all_raw_data_populated(self):
        """Test that raw_data contains metadata."""
        result = extract_all(CISCO_IOS_CONFIG)
        
        assert "config_length" in result.raw_data
        assert "line_count" in result.raw_data
        assert result.raw_data["config_length"] > 0
        assert result.raw_data["line_count"] > 0

    def test_extract_by_platform_cisco_ios(self):
        """Test platform-specific extraction for Cisco IOS."""
        result = extract_by_platform(CISCO_IOS_CONFIG, "cisco_ios")
        
        assert result.raw_data["platform"] == "cisco_ios"
        assert "router1" in result.hostnames
        assert len(result.ip_addresses) > 0

    def test_extract_by_platform_juniper_junos(self):
        """Test platform-specific extraction for Juniper Junos."""
        result = extract_by_platform(JUNIPER_JUNOS_CONFIG, "juniper_junos")
        
        assert result.raw_data["platform"] == "juniper_junos"
        assert "juniper-router1" in result.hostnames


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestExtractionEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_from_minimal_config(self):
        """Test extraction from a minimal config with no parameters."""
        config = "! Minimal config\nend"
        result = extract_all(config)
        
        assert result.ip_addresses == []
        assert result.vlan_ids == []
        assert result.interface_names == []
        assert result.hostnames == []

    def test_extract_from_malformed_config(self):
        """Test that malformed config doesn't crash extraction."""
        config = "this is not a valid config\n###garbage###\n!@#$%"
        result = extract_all(config)
        
        # Should not crash, just return empty results
        assert isinstance(result, ExtractedConfig)

    def test_extract_with_unicode_characters(self):
        """Test extraction from config with unicode characters."""
        config = """
        hostname routér1
        interface GigabitEthernet0/0
         description Ñetwork Interface
         ip address 192.168.1.1 255.255.255.0
        """
        result = extract_all(config)
        
        assert "192.168.1.1" in result.ip_addresses
        assert "GigabitEthernet0/0" in result.interface_names

    def test_extract_handles_very_long_lines(self):
        """Test extraction from config with very long lines."""
        long_description = "A" * 10000
        config = f"""
        interface GigabitEthernet0/0
         description {long_description}
         ip address 10.0.0.1 255.255.255.0
        """
        result = extract_all(config)
        
        assert "10.0.0.1" in result.ip_addresses
        assert "GigabitEthernet0/0" in result.interface_names

    def test_extract_case_insensitive(self):
        """Test that extraction is case-insensitive."""
        config1 = "INTERFACE GigabitEthernet0/0\n IP ADDRESS 192.168.1.1 255.255.255.0"
        config2 = "interface gigabitethernet0/0\n ip address 192.168.1.1 255.255.255.0"
        
        result1 = extract_all(config1)
        result2 = extract_all(config2)
        
        assert "192.168.1.1" in result1.ip_addresses
        assert "192.168.1.1" in result2.ip_addresses


# ============================================================================
# Test Performance with Large Configs
# ============================================================================

class TestExtractionPerformance:
    """Test extraction performance with large configurations."""

    def test_extract_from_large_config(self):
        """Test extraction from a very large configuration."""
        # Generate a large config with 1000 interfaces
        large_config = "\n".join([
            f"interface GigabitEthernet{i}/0\n ip address 10.{i//256}.{i%256}.1 255.255.255.0"
            for i in range(1000)
        ])
        
        result = extract_all(large_config)
        
        # Should handle large configs without performance issues
        assert len(result.interface_names) == 1000
        assert len(result.ip_addresses) > 0

    def test_extract_deduplication_performance(self):
        """Test deduplication with many duplicate entries."""
        # Config with 1000 duplicate entries
        config = "\n".join(["vlan 100"] * 1000)
        
        result = extract_vlan_ids(config)
        
        # Should deduplicate efficiently
        assert result == [100]
