"""
Pytest configuration and shared fixtures for Netpicker CLI tests.

This file provides:
- CLI test runner fixture
- Mock settings fixtures
- Mock network configuration fixtures
- Mock AI response fixtures
- Mock API response generators
"""

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, AsyncMock
from netpicker_cli.utils.config import Settings
from netpicker_cli.ai.router import QueryRouter
import json
import asyncio


# ============================================================================
# CLI & Runner Fixtures
# ============================================================================

@pytest.fixture
def runner():
    """Provides a Typer CLI test runner."""
    return CliRunner()


# ============================================================================
# Settings & Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_settings():
    """Provides mock Netpicker settings."""
    return Settings(
        base_url="https://api.example.com",
        tenant="test-tenant",
        token="test-token"
    )


@pytest.fixture
def mock_settings_sandbox():
    """Provides mock Netpicker settings for sandbox environment."""
    return Settings(
        base_url="https://sandbox.netpicker.io",
        tenant="default",
        token="sandbox-token"
    )


@pytest.fixture
def mock_settings_custom(request):
    """Provides customizable mock settings via indirect parametrization."""
    return Settings(
        base_url=getattr(request, "param", {}).get("base_url", "https://api.example.com"),
        tenant=getattr(request, "param", {}).get("tenant", "test-tenant"),
        token=getattr(request, "param", {}).get("token", "test-token")
    )


# ============================================================================
# Network Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_cisco_ios_config():
    """Sample Cisco IOS configuration."""
    return """version 15.6
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
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
 network 10.0.0.0 0.0.0.255 area 0
!
line vty 0 4
 exec-timeout 0 0
 transport input ssh
!
end
"""


@pytest.fixture
def mock_arista_eos_config():
    """Sample Arista EOS configuration."""
    return """!
version 4.27.0F
!
hostname eos1
!
ip domain-name example.com
dns domain-name example.com
!
interface Ethernet1
   description WAN Interface
   ip address 192.168.1.5/24
!
interface Ethernet2
   description LAN Interface
   ip address 10.0.0.5/24
!
router ospf 1
   router-id 192.168.1.5
   network 192.168.1.0/24 area 0
   network 10.0.0.0/24 area 0
!
management api http-commands
   protocol https
   no shutdown
!
end
"""


@pytest.fixture
def mock_juniper_config():
    """Sample Juniper Junos configuration."""
    return """version 20.4R1-S1.4;
system {
    hostname juniper-router;
    domain-name example.com;
    time-zone UTC;
    authentication-order password;
    root-authentication {
        encrypted-password "$1$y/fXw8dj$YJePt.M9UZnl.LOjJ.h1J1";
    }
}
interfaces {
    ge-0/0/0 {
        description "WAN Interface";
        unit 0 {
            family inet {
                address 192.168.1.10/24;
            }
        }
    }
    ge-0/0/1 {
        description "LAN Interface";
        unit 0 {
            family inet {
                address 10.0.0.10/24;
            }
        }
    }
}
routing-options {
    router-id 192.168.1.10;
}
protocols {
    ospf {
        area 0.0.0.0 {
            interface ge-0/0/0.0;
            interface ge-0/0/1.0;
        }
    }
}
"""


@pytest.fixture
def sample_network_configs():
    """Provides a collection of sample network configurations."""
    return {
        "cisco_ios": """
hostname cisco-router
ip route 0.0.0.0 0.0.0.0 192.168.1.254
interface Gi0/0
 ip address 192.168.1.100 255.255.255.0
 no shutdown
""",
        "arista_eos": """
hostname arista-switch
ip route 0.0.0.0/0 192.168.1.254
interface Ethernet1
 ip address 192.168.1.101/24
""",
        "juniper": """
set interfaces ge-0/0/0 unit 0 family inet address 192.168.1.102/24
set routing-options static route 0.0.0.0/0 next-hop 192.168.1.254
""",
        "fortios": """
config system interface
    edit "port1"
        set ip 192.168.1.103 255.255.255.0
    next
end
""",
        "nxos": """
hostname nxos-switch
feature ospf
interface Ethernet1/1
  ip address 192.168.1.104 255.255.255.0
  no shutdown
"""
    }


# ============================================================================
# Device Fixtures
# ============================================================================

@pytest.fixture
def mock_device():
    """Sample device object."""
    return {
        "id": "device-123",
        "name": "router1",
        "ipaddress": "192.168.1.1",
        "platform": "cisco_ios",
        "port": 22,
        "vault": "netpicker",
        "tags": ["production", "core"],
        "firmware": "15.6(2)T"
    }


@pytest.fixture
def mock_device_list():
    """List of sample devices."""
    return {
        "items": [
            {
                "id": "device-123",
                "name": "router1",
                "ipaddress": "192.168.1.1",
                "platform": "cisco_ios",
                "tags": ["production"]
            },
            {
                "id": "device-456",
                "name": "switch1",
                "ipaddress": "192.168.1.2",
                "platform": "arista_eos",
                "tags": ["production", "switching"]
            },
            {
                "id": "device-789",
                "name": "fw1",
                "ipaddress": "192.168.1.3",
                "platform": "fortios",
                "tags": ["security"]
            }
        ],
        "total": 3,
        "page": 1,
        "size": 50
    }


# ============================================================================
# Backup Fixtures
# ============================================================================

@pytest.fixture
def mock_backup():
    """Sample backup object."""
    return {
        "id": "backup-123",
        "device_id": "device-123",
        "upload_date": "2026-01-07T10:30:00Z",
        "upload_agent": "netpicker-agent",
        "file_size": 2048,
        "digest": "a1b2c3d4e5f6g7h8i9j0",
        "commit": "abc123def456ghi789jkl"
    }


@pytest.fixture
def mock_backup_list():
    """List of sample backups."""
    return {
        "items": [
            {
                "id": "backup-001",
                "device_id": "device-123",
                "upload_date": "2026-01-07T10:30:00Z",
                "file_size": 2048
            },
            {
                "id": "backup-002",
                "device_id": "device-123",
                "upload_date": "2026-01-06T10:30:00Z",
                "file_size": 2048
            }
        ]
    }


@pytest.fixture
def mock_search_results():
    """Sample config search results."""
    return {
        "results": [
            {
                "device": {
                    "id": "device-123",
                    "name": "router1",
                    "ipaddress": "192.168.1.1"
                },
                "matches": [
                    {
                        "line_number": 5,
                        "content": "hostname router1"
                    },
                    {
                        "line_number": 12,
                        "content": "ip route 0.0.0.0 0.0.0.0 192.168.1.254"
                    }
                ]
            }
        ]
    }


# ============================================================================
# Compliance & Policy Fixtures
# ============================================================================

@pytest.fixture
def mock_policy():
    """Sample compliance policy."""
    return {
        "id": "policy-123",
        "name": "cis_cisco_ios",
        "description": "CIS Cisco IOS Benchmark",
        "rules": [
            {
                "name": "rule_1_1",
                "description": "Set the MOTD banner",
                "severity": "HIGH"
            }
        ]
    }


@pytest.fixture
def mock_compliance_report():
    """Sample compliance report."""
    return {
        "device_id": "device-123",
        "device_name": "router1",
        "policy": "cis_cisco_ios",
        "passed": 45,
        "failed": 3,
        "total": 48,
        "compliance_percentage": 93.75,
        "timestamp": "2026-01-07T10:30:00Z"
    }


# ============================================================================
# Automation Fixtures
# ============================================================================

@pytest.fixture
def mock_job():
    """Sample automation job."""
    return {
        "id": "job-123",
        "name": "backup-job",
        "description": "Daily backup job",
        "status": "running",
        "created_at": "2026-01-07T10:00:00Z"
    }


@pytest.fixture
def mock_job_execution():
    """Sample job execution result."""
    return {
        "id": "exec-123",
        "job_id": "job-123",
        "status": "success",
        "devices_affected": 5,
        "timestamp": "2026-01-07T10:30:00Z",
        "output": "Successfully executed on 5 devices"
    }


# ============================================================================
# AI & Query Fixtures
# ============================================================================

@pytest.fixture
def mock_ai_response():
    """Sample AI router response."""
    return {
        "tool": "devices_list",
        "reasoning": "User asked to list devices, selected devices_list tool",
        "success": True,
        "parameters": {
            "limit": 10,
            "tag": "production"
        }
    }


@pytest.fixture
def mock_ai_response_object():
    """Mock AI response as MagicMock object."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{
            "message": {
                "content": "devices_list"
            }
        }]
    }
    return response


@pytest.fixture
def mock_mistral_router():
    """Mock Mistral AI router."""
    router = AsyncMock(spec=MistralRouter)
    router.route.return_value = "devices_list"
    return router


@pytest.fixture
def sample_queries():
    """Collection of sample natural language queries."""
    return {
        "list_devices": "Show me all devices",
        "list_with_limit": "List 5 devices with tag production",
        "show_device": "Show details for device 192.168.1.1",
        "show_backup_history": "Get backup history for router1",
        "compliance_check": "Check compliance for production devices",
        "execute_job": "Execute backup job on all switches",
        "unknown": "Calculate the meaning of life"
    }


# ============================================================================
# API Response Fixtures
# ============================================================================

@pytest.fixture
def mock_api_responses():
    """Collection of mock API responses for different endpoints."""
    return {
        "devices_list": {
            "items": [{"id": "1", "name": "router1", "ipaddress": "192.168.1.1"}],
            "total": 1
        },
        "device_created": {
            "success": True,
            "message": "Device created",
            "device_id": "new-123"
        },
        "device_deleted": {
            "success": True,
            "message": "Device deleted"
        },
        "backup_list": {
            "items": [{"id": "b1", "upload_date": "2026-01-07T10:30:00Z"}]
        },
        "policy_list": {
            "items": [{"id": "p1", "name": "policy1"}]
        },
        "job_list": {
            "items": [{"id": "j1", "name": "job1", "status": "ready"}]
        }
    }


def mock_api_get(endpoint):
    """Helper function to create mock GET responses."""
    responses = {
        "devices": {"items": []},
        "backups": {"items": []},
        "policies": {"items": []},
        "jobs": {"items": []}
    }
    
    for key, value in responses.items():
        if key in endpoint:
            return MagicMock(json=lambda: value)
    
    return MagicMock(json=lambda: {})


def mock_api_post(endpoint, payload):
    """Helper function to create mock POST responses."""
    return MagicMock(
        json=lambda: {"success": True, "message": f"Operation on {endpoint} successful"}
    )


@pytest.fixture
def api_response_helper():
    """Provides helper functions for API responses."""
    return {
        "get": mock_api_get,
        "post": mock_api_post
    }


# ============================================================================
# Error Fixtures
# ============================================================================

@pytest.fixture
def mock_api_errors():
    """Collection of mock API error responses."""
    return {
        "not_found": {"status_code": 404, "detail": "Resource not found"},
        "unauthorized": {"status_code": 401, "detail": "Unauthorized"},
        "forbidden": {"status_code": 403, "detail": "Forbidden"},
        "server_error": {"status_code": 500, "detail": "Internal server error"},
        "rate_limit": {"status_code": 429, "detail": "Rate limit exceeded"},
        "validation_error": {"status_code": 422, "detail": "Validation error"},
    }


# ============================================================================
# Data Validation Fixtures
# ============================================================================

@pytest.fixture
def valid_device_data():
    """Sample valid device data for creation."""
    return {
        "ip": "192.168.1.100",
        "name": "new-router",
        "platform": "cisco_ios",
        "port": 22,
        "tags": ["lab", "test"]
    }


@pytest.fixture
def invalid_device_data():
    """Collection of invalid device data."""
    return {
        "missing_ip": {
            "name": "router",
            "platform": "cisco_ios"
        },
        "invalid_ip": {
            "ip": "999.999.999.999",
            "name": "router",
            "platform": "cisco_ios"
        },
        "invalid_platform": {
            "ip": "192.168.1.1",
            "name": "router",
            "platform": "unknown_os"
        }
    }


# ============================================================================
# Async Test Support
# ============================================================================

@pytest.fixture
def event_loop():
    """Provides an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_client():
    """Provides an async HTTP client mock."""
    import httpx
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    return client


# ============================================================================
# Output Formatting Fixtures
# ============================================================================

@pytest.fixture
def output_formats():
    """Available output format options."""
    return ["table", "json", "csv", "yaml"]


@pytest.fixture
def sample_tabular_data():
    """Sample data suitable for tabular output."""
    return [
        {"id": "1", "name": "device1", "ip": "192.168.1.1", "status": "up"},
        {"id": "2", "name": "device2", "ip": "192.168.1.2", "status": "down"},
        {"id": "3", "name": "device3", "ip": "192.168.1.3", "status": "up"}
    ]


# ============================================================================
# Session Fixtures (for setup/teardown)
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Creates a temporary directory for test data."""
    return tmp_path_factory.mktemp("test_data")


@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary config file."""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "base_url": "https://api.example.com",
        "tenant": "test-tenant",
        "token": "test-token"
    }))
    return config_file


# ============================================================================
# Hooks for Test Setup/Teardown
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    yield
    # Cleanup after test if needed


# ============================================================================
# Parametrization Helpers
# ============================================================================

def pytest_generate_tests(metafunc):
    """Generate parametrized tests."""
    # Example: automatically parametrize tests with 'output_format' parameter
    if "output_format" in metafunc.fixturenames:
        metafunc.parametrize("output_format", ["table", "json", "csv", "yaml"])
