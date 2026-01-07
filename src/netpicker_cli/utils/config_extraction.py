"""
Network configuration extraction utilities.

Extracts structured data (IP addresses, VLANs, interfaces) from raw network device configurations.
Supports multiple vendor platforms: Cisco IOS/NX-OS, Juniper Junos, Arista EOS, Palo Alto PAN-OS, etc.
"""

import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class ExtractedConfig:
    """Container for extracted configuration parameters."""
    ip_addresses: List[str]
    vlan_ids: List[int]
    interface_names: List[str]
    hostnames: List[str]
    raw_data: Dict[str, Any]


def extract_ip_addresses(config: str) -> List[str]:
    """
    Extract all IP addresses from a network configuration.
    
    Supports various formats:
    - Cisco IOS: ip address 192.168.1.1 255.255.255.0
    - Juniper: address 10.0.0.1/24
    - Arista: ip address 172.16.0.1/24
    
    Args:
        config: Raw network configuration string
        
    Returns:
        List of IP addresses found in the configuration
    """
    ip_addresses = set()
    
    # Pattern 1: Cisco-style "ip address X.X.X.X"
    cisco_pattern = r'\bip\s+address\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    for match in re.finditer(cisco_pattern, config, re.IGNORECASE):
        ip = match.group(1)
        # Validate octets
        octets = [int(x) for x in ip.split('.')]
        if all(0 <= octet <= 255 for octet in octets):
            ip_addresses.add(ip)
    
    # Pattern 2: CIDR notation "address X.X.X.X/YY" or "ip address X.X.X.X/YY"
    cidr_pattern = r'\b(?:address|ip\s+address|layer3\s+ip)\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/\d{1,2}'
    for match in re.finditer(cidr_pattern, config, re.IGNORECASE):
        ip = match.group(1)
        # Validate octets
        octets = [int(x) for x in ip.split('.')]
        if all(0 <= octet <= 255 for octet in octets):
            ip_addresses.add(ip)
    
    # Pattern 3: Standalone IP addresses (more generic, used as fallback)
    # Only match if not part of a larger pattern
    standalone_pattern = r'(?:^|\s)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?:\s|$|;)'
    for match in re.finditer(standalone_pattern, config, re.MULTILINE):
        ip = match.group(1)
        # Basic validation: octets should be 0-255
        octets = [int(x) for x in ip.split('.')]
        if all(0 <= octet <= 255 for octet in octets):
            ip_addresses.add(ip)
    
    return sorted(list(ip_addresses))


def extract_vlan_ids(config: str) -> List[int]:
    """
    Extract VLAN IDs from a network configuration.
    
    Supports various formats:
    - Cisco IOS: vlan 100, switchport access vlan 10
    - Juniper: vlan-id 200
    - Arista: vlan 300
    
    Args:
        config: Raw network configuration string
        
    Returns:
        List of VLAN IDs found in the configuration
    """
    vlan_ids = set()
    
    # Pattern 1: "vlan XXX" (global VLAN definition)
    vlan_def_pattern = r'^\s*vlan\s+(\d+)'
    for match in re.finditer(vlan_def_pattern, config, re.MULTILINE):
        vlan_ids.add(int(match.group(1)))
    
    # Pattern 2: "switchport access vlan XXX" or "switchport trunk allowed vlan XXX"
    switchport_pattern = r'\bswitchport\s+(?:access|trunk\s+allowed)\s+vlan\s+(\d+)'
    for match in re.finditer(switchport_pattern, config, re.IGNORECASE):
        vlan_ids.add(int(match.group(1)))
    
    # Pattern 3: Juniper "vlan-id XXX"
    juniper_pattern = r'\bvlan-id\s+(\d+)'
    for match in re.finditer(juniper_pattern, config, re.IGNORECASE):
        vlan_ids.add(int(match.group(1)))
    
    # Pattern 4: VLAN ranges like "vlan 10,20,30-40"
    range_pattern = r'\bvlan\s+([\d,\-\s]+)'
    for match in re.finditer(range_pattern, config, re.IGNORECASE):
        vlan_spec = match.group(1)
        # Parse comma-separated and range syntax
        for part in vlan_spec.split(','):
            part = part.strip()
            if '-' in part:
                # Range: 30-40
                    range_parts = part.split('-')
                    if len(range_parts) == 2 and range_parts[0].strip() and range_parts[1].strip():
                        try:
                            start = int(range_parts[0].strip())
                            end = int(range_parts[1].strip())
                            vlan_ids.update(range(start, end + 1))
                        except ValueError:
                            # Skip malformed range
                            pass
            elif part.isdigit():
                vlan_ids.add(int(part))
    
    return sorted(list(vlan_ids))


def extract_interface_names(config: str) -> List[str]:
    """
    Extract interface names from a network configuration.
    
    Supports various vendor formats:
    - Cisco IOS: GigabitEthernet0/0, Ethernet1/1, Vlan100
    - Juniper: ge-0/0/0, xe-1/2/3, ae0
    - Arista: Ethernet1, Management1
    - Palo Alto: ethernet1/1
    
    Args:
        config: Raw network configuration string
        
    Returns:
        List of interface names found in the configuration
    """
    interface_names = set()
    
    # Pattern 1: Cisco-style "interface <name>"
    cisco_pattern = r'^\s*interface\s+([\w/\-\.]+)'
    for match in re.finditer(cisco_pattern, config, re.MULTILINE | re.IGNORECASE):
        interface_names.add(match.group(1))
    
    # Pattern 2: Juniper-style interface names in "set interfaces <name>"
    juniper_pattern = r'\bset\s+interfaces\s+([\w\-/\.]+)'
    for match in re.finditer(juniper_pattern, config, re.IGNORECASE):
        interface_names.add(match.group(1))
    
    # Pattern 4: Palo Alto-style "set network interface ethernet X/Y"
    palo_pattern = r'\bset\s+network\s+interface\s+ethernet\s+([\w\-/\.]+)'
    for match in re.finditer(palo_pattern, config, re.IGNORECASE):
        # Match already includes "ethernet" prefix (e.g., "ethernet1/1")
        interface_names.add(match.group(1))
    
    # Pattern 3: Interface references in various contexts (e.g., "on interface Gi0/0")
    ref_pattern = r'\bon\s+interface\s+([\w/\-\.]+)'
    for match in re.finditer(ref_pattern, config, re.IGNORECASE):
        interface_names.add(match.group(1))
    
    return sorted(list(interface_names))


def extract_hostnames(config: str) -> List[str]:
    """
    Extract hostname(s) from a network configuration.
    
    Supports:
    - Cisco IOS: hostname router1
    - Juniper: set system host-name router1
    - Arista: hostname switch1
    
    Args:
        config: Raw network configuration string
        
    Returns:
        List of hostnames found in the configuration
    """
    hostnames = set()
    
    # Pattern 1: Cisco/Arista "hostname <name>"
    cisco_pattern = r'^\s*hostname\s+([\w\-\.]+)'
    for match in re.finditer(cisco_pattern, config, re.MULTILINE | re.IGNORECASE):
        hostnames.add(match.group(1))
    
    # Pattern 2: Juniper "set system host-name <name>"
    juniper_pattern = r'\bset\s+system\s+host-name\s+([\w\-\.]+)'
    for match in re.finditer(juniper_pattern, config, re.IGNORECASE):
        hostnames.add(match.group(1))
    
    # Pattern 3: Palo Alto "set deviceconfig system hostname <name>"
    palo_pattern = r'\bset\s+deviceconfig\s+system\s+hostname\s+([\w\-\.]+)'
    for match in re.finditer(palo_pattern, config, re.IGNORECASE):
        hostnames.add(match.group(1))
    
    return sorted(list(hostnames))


def extract_all(config: str) -> ExtractedConfig:
    """
    Extract all configuration parameters from a network configuration.
    
    Convenience function that extracts IP addresses, VLANs, interfaces, and hostnames.
    
    Args:
        config: Raw network configuration string
        
    Returns:
        ExtractedConfig object containing all extracted data
    """
    return ExtractedConfig(
        ip_addresses=extract_ip_addresses(config),
        vlan_ids=extract_vlan_ids(config),
        interface_names=extract_interface_names(config),
        hostnames=extract_hostnames(config),
        raw_data={
            "config_length": len(config),
            "line_count": len(config.splitlines()),
        }
    )


def extract_by_platform(config: str, platform: str) -> ExtractedConfig:
    """
    Extract configuration parameters with platform-specific optimizations.
    
    Args:
        config: Raw network configuration string
        platform: Platform identifier (cisco_ios, juniper_junos, arista_eos, etc.)
        
    Returns:
        ExtractedConfig object containing extracted data
    """
    # For now, use the same extraction logic for all platforms
    # Future enhancement: Platform-specific parsing optimizations
    result = extract_all(config)
    result.raw_data["platform"] = platform
    return result
