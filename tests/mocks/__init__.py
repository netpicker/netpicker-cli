"""
Mock objects and utilities for Netpicker CLI tests.

Provides:
- Pre-built mock objects for common API responses
- Mock generators for creating test data
- Mock context managers for patching
"""

from unittest.mock import MagicMock, AsyncMock, patch
import json
from typing import Dict, Any, List


# ============================================================================
# Mock API Client Responses
# ============================================================================

class MockApiClient:
    """Mock API client for testing."""
    
    def __init__(self, base_url: str = "https://api.example.com"):
        self.base_url = base_url
        self.tenant = "test-tenant"
        self.token = "test-token"
    
    def get(self, endpoint: str, params: Dict = None):
        """Mock GET request."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"items": [], "success": True}
        return response
    
    def post(self, endpoint: str, json: Dict = None):
        """Mock POST request."""
        response = MagicMock()
        response.status_code = 201
        response.json.return_value = {"success": True, "id": "mock-123"}
        return response
    
    def put(self, endpoint: str, json: Dict = None):
        """Mock PUT request."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"success": True}
        return response
    
    def delete(self, endpoint: str):
        """Mock DELETE request."""
        response = MagicMock()
        response.status_code = 204
        return response


class MockAsyncApiClient(MockApiClient):
    """Mock async API client for testing."""
    
    async def get(self, endpoint: str, params: Dict = None):
        """Mock async GET request."""
        response = MagicMock()
        response.status_code = 200
        response.json = AsyncMock(return_value={"items": [], "success": True})
        return response
    
    async def post(self, endpoint: str, json: Dict = None):
        """Mock async POST request."""
        response = MagicMock()
        response.status_code = 201
        response.json = AsyncMock(return_value={"success": True, "id": "mock-123"})
        return response


# ============================================================================
# Mock Data Generators
# ============================================================================

def create_mock_device(
    device_id: str = "device-1",
    name: str = "router1",
    ip: str = "192.168.1.1",
    platform: str = "cisco_ios",
    tags: List[str] = None
) -> Dict[str, Any]:
    """Create a mock device object."""
    return {
        "id": device_id,
        "name": name,
        "ipaddress": ip,
        "platform": platform,
        "port": 22,
        "vault": "netpicker",
        "tags": tags or ["production"],
        "firmware": "15.6(2)T"
    }


def create_mock_backup(
    backup_id: str = "backup-1",
    device_id: str = "device-1",
    size: int = 2048
) -> Dict[str, Any]:
    """Create a mock backup object."""
    return {
        "id": backup_id,
        "device_id": device_id,
        "upload_date": "2026-01-07T10:30:00Z",
        "upload_agent": "netpicker-agent",
        "file_size": size,
        "digest": "a1b2c3d4e5f6g7h8i9j0",
        "commit": "abc123def456ghi789jkl"
    }


def create_mock_policy(
    policy_id: str = "policy-1",
    name: str = "cis_benchmark",
    rule_count: int = 5
) -> Dict[str, Any]:
    """Create a mock policy object."""
    rules = [
        {
            "name": f"rule_{i}",
            "description": f"Test rule {i}",
            "severity": "HIGH" if i % 2 == 0 else "MEDIUM"
        }
        for i in range(1, rule_count + 1)
    ]
    
    return {
        "id": policy_id,
        "name": name,
        "description": f"Policy {name}",
        "rules": rules,
        "created_at": "2026-01-07T10:00:00Z"
    }


def create_mock_job(
    job_id: str = "job-1",
    name: str = "backup-job",
    status: str = "ready"
) -> Dict[str, Any]:
    """Create a mock job object."""
    return {
        "id": job_id,
        "name": name,
        "description": f"Job {name}",
        "status": status,
        "created_at": "2026-01-07T10:00:00Z",
        "variables": {}
    }


# ============================================================================
# Mock Response Builders
# ============================================================================

def build_devices_response(count: int = 3) -> Dict[str, Any]:
    """Build a mock devices list response."""
    return {
        "items": [
            create_mock_device(
                device_id=f"device-{i}",
                name=f"device{i}",
                ip=f"192.168.1.{i}"
            )
            for i in range(1, count + 1)
        ],
        "total": count
    }


def build_backups_response(device_id: str = "device-1", count: int = 5) -> Dict[str, Any]:
    """Build a mock backups list response."""
    return {
        "items": [
            create_mock_backup(
                backup_id=f"backup-{i}",
                device_id=device_id
            )
            for i in range(1, count + 1)
        ]
    }


def build_search_results(device_count: int = 2, matches_per_device: int = 3) -> Dict[str, Any]:
    """Build mock config search results."""
    results = []
    
    for d in range(1, device_count + 1):
        device = create_mock_device(device_id=f"device-{d}")
        matches = [
            {
                "line_number": i * 10,
                "content": f"config line {i}"
            }
            for i in range(1, matches_per_device + 1)
        ]
        
        results.append({
            "device": device,
            "matches": matches
        })
    
    return {"results": results}


# ============================================================================
# Mock Context Managers
# ============================================================================

class MockApiPatch:
    """Context manager for mocking API client."""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.patcher = None
    
    def __enter__(self):
        self.patcher = patch("netpicker_cli.api.client.ApiClient", MockApiClient)
        self.patcher.__enter__()
        return MockApiClient(**self.kwargs)
    
    def __exit__(self, *args):
        if self.patcher:
            self.patcher.__exit__(*args)


class MockSettingsPatch:
    """Context manager for mocking settings."""
    
    def __init__(self, **settings):
        self.settings = settings
        self.patcher = None
    
    def __enter__(self):
        from netpicker_cli.utils.config import Settings
        mock_settings = Settings(**self.settings)
        self.patcher = patch("netpicker_cli.commands.devices.load_settings")
        mock_func = self.patcher.__enter__()
        mock_func.return_value = mock_settings
        return mock_settings
    
    def __exit__(self, *args):
        if self.patcher:
            self.patcher.__exit__(*args)


# ============================================================================
# Mock Error Responses
# ============================================================================

class MockErrorResponse:
    """Mock error API response."""
    
    def __init__(self, status_code: int = 400, detail: str = "Bad request"):
        self.status_code = status_code
        self.detail = detail
    
    def json(self):
        return {
            "detail": self.detail,
            "status_code": self.status_code
        }
    
    def raise_for_status(self):
        from netpicker_cli.api.errors import ApiError
        raise ApiError(self.detail, self.status_code)


def create_404_response():
    """Create a 404 Not Found response."""
    return MockErrorResponse(404, "Resource not found")


def create_401_response():
    """Create a 401 Unauthorized response."""
    return MockErrorResponse(401, "Unauthorized")


def create_500_response():
    """Create a 500 Internal Server Error response."""
    return MockErrorResponse(500, "Internal server error")


# ============================================================================
# Mock Configuration Data
# ============================================================================

MOCK_CISCO_CONFIG = """version 15.6
hostname router1
!
ip domain-name example.com
!
interface GigabitEthernet0/0
 description WAN Interface
 ip address 192.168.1.1 255.255.255.0
 no shutdown
!
router ospf 1
 network 192.168.1.0 0.0.0.255 area 0
!
end
"""

MOCK_ARISTA_CONFIG = """!
version 4.27.0F
!
hostname eos1
!
interface Ethernet1
   description WAN Interface
   ip address 192.168.1.5/24
!
router ospf 1
   router-id 192.168.1.5
!
end
"""

# ============================================================================
# Mock Compliance Data
# ============================================================================

MOCK_COMPLIANCE_RULES = [
    {
        "id": "rule_1_1",
        "name": "Set the MOTD banner",
        "severity": "HIGH",
        "policy": "cis_cisco_ios"
    },
    {
        "id": "rule_1_2",
        "name": "Set the login banner",
        "severity": "HIGH",
        "policy": "cis_cisco_ios"
    },
    {
        "id": "rule_2_1",
        "name": "Enable AAA",
        "severity": "MEDIUM",
        "policy": "cis_cisco_ios"
    }
]

MOCK_COMPLIANCE_REPORT = {
    "device_id": "device-1",
    "device_name": "router1",
    "policy": "cis_cisco_ios",
    "passed": 45,
    "failed": 3,
    "total": 48,
    "compliance_percentage": 93.75,
    "timestamp": "2026-01-07T10:30:00Z",
    "failed_rules": ["rule_1_1", "rule_2_1"]
}
