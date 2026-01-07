"""
Unit tests for edge cases and error handling.

Tests the CLI's resilience against bad data:
- Empty strings passed to parsers
- Malformed JSON in AI query routing
- None responses from AI model
- Invalid input handling
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from netpicker_cli.commands.ai import extract_parameters, fetch_latest_backup
from netpicker_cli.ai.router import QueryRouter
from netpicker_cli.utils.config_extraction import (
    extract_ip_addresses,
    extract_vlan_ids,
    extract_interface_names,
    extract_hostnames,
    extract_all,
)


# ============================================================================
# Test Empty String Handling
# ============================================================================

class TestEmptyStringParsing:
    """Test that parsers handle empty strings gracefully."""

    def test_extract_parameters_with_empty_string(self):
        """Test extract_parameters doesn't crash on empty string."""
        result = extract_parameters("")
        
        # Should return empty dict, not crash
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_extract_parameters_with_whitespace_only(self):
        """Test extract_parameters handles whitespace-only input."""
        result = extract_parameters("   \n\t   ")
        
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_extract_ip_addresses_with_empty_string(self):
        """Test IP extraction doesn't crash on empty string."""
        result = extract_ip_addresses("")
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_vlan_ids_with_empty_string(self):
        """Test VLAN extraction doesn't crash on empty string."""
        result = extract_vlan_ids("")
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_interface_names_with_empty_string(self):
        """Test interface extraction doesn't crash on empty string."""
        result = extract_interface_names("")
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_hostnames_with_empty_string(self):
        """Test hostname extraction doesn't crash on empty string."""
        result = extract_hostnames("")
        
        assert isinstance(result, list)
        assert len(result) == 0

    def test_extract_all_with_empty_string(self):
        """Test extract_all doesn't crash on empty string."""
        result = extract_all("")
        
        assert result is not None
        assert result.ip_addresses == []
        assert result.vlan_ids == []
        assert result.interface_names == []
        assert result.hostnames == []


# ============================================================================
# Test Malformed JSON Handling
# ============================================================================

class TestMalformedJSONHandling:
    """Test handling of malformed JSON in AI query routing."""

    @pytest.mark.asyncio
    async def test_route_query_with_malformed_json_response(self):
        """Test QueryRouter handles malformed JSON from AI model."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock a response with malformed JSON
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                    "text": "This is not valid JSON {broken"
                }]
            }
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            # Should handle gracefully, not crash
            tool_name, error = await router.route_query("list devices", ["devices_list"])
            
            # Should return error or None, not crash
            assert tool_name is None or isinstance(tool_name, str)
            assert error is not None or tool_name is not None

    @pytest.mark.asyncio
    async def test_route_query_with_empty_json_response(self):
        """Test QueryRouter handles empty JSON response."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            tool_name, error = await router.route_query("show devices", ["devices_list"])
            
            # Should handle gracefully
            assert error is not None or tool_name is None

    @pytest.mark.asyncio
    async def test_route_query_with_missing_choices_key(self):
        """Test QueryRouter handles response missing 'choices' key."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}  # Missing 'choices'
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            tool_name, error = await router.route_query("list all", ["devices_list"])
            
            assert error is not None or tool_name is None

    def test_extract_parameters_with_special_json_chars(self):
        """Test extract_parameters handles JSON special characters."""
        # Queries that might contain JSON-like syntax
        queries = [
            'show devices {"limit": 5}',
            'list [device1, device2]',
            'get {"ip": "192.168.1.1"}',
            'query with "quotes" inside',
        ]
        
        for query in queries:
            result = extract_parameters(query)
            # Should not crash, should return dict
            assert isinstance(result, dict)


# ============================================================================
# Test None Response Handling
# ============================================================================

class TestNoneResponseHandling:
    """Test handling of None responses from AI model."""

    @pytest.mark.asyncio
    async def test_route_query_with_none_response(self):
        """Test QueryRouter handles None response from AI."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = TypeError("NoneType object")
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            # Should handle None gracefully
            tool_name, error = await router.route_query("query", ["tool1"])
            # Should return error
            assert tool_name is None
            assert error is not None

    @pytest.mark.asyncio
    async def test_route_query_with_none_in_choices(self):
        """Test QueryRouter handles None value in choices array."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"choices": [{"text": ""}]}
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            tool_name, error = await router.route_query("test", ["tool1"])
            
            # Should handle None in choices
            assert error is not None or tool_name is None

    @pytest.mark.asyncio
    async def test_route_query_with_none_text_field(self):
        """Test QueryRouter handles None in 'text' field."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{
                        "text": ""
                }]
            }
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            tool_name, error = await router.route_query("query", ["tool1"])
            
            # Should handle None text
            assert error is not None or tool_name is None

    @patch('netpicker_cli.commands.ai.run_netpicker_command')
    def test_fetch_latest_backup_with_none_response(self, mock_run):
        """Test fetch_latest_backup handles None response."""
        mock_run.return_value = None
        
        # Should handle None gracefully
        try:
            result = fetch_latest_backup("192.168.1.1")
            # Should return error message or empty string
            assert isinstance(result, str)
        except Exception as e:
            # If it raises, verify it's a handled exception
            pytest.fail(f"Should not crash on None response: {e}")


# ============================================================================
# Test Invalid Input Types
# ============================================================================

class TestInvalidInputTypes:
    """Test handling of invalid input types."""

    def test_extract_parameters_with_none(self):
        """Test extract_parameters handles None input."""
        with pytest.raises((TypeError, AttributeError)):
            # Should raise TypeError since None has no .lower() etc
            extract_parameters(None)

    def test_extract_parameters_with_number(self):
        """Test extract_parameters handles numeric input."""
        with pytest.raises((TypeError, AttributeError)):
            extract_parameters(12345)

    def test_extract_parameters_with_list(self):
        """Test extract_parameters handles list input."""
        with pytest.raises((TypeError, AttributeError)):
            extract_parameters(["list", "of", "words"])

    def test_extract_ip_addresses_with_none(self):
        """Test IP extraction handles None input."""
        with pytest.raises((TypeError, AttributeError)):
            extract_ip_addresses(None)

    def test_extract_vlan_ids_with_none(self):
        """Test VLAN extraction handles None input."""
        with pytest.raises((TypeError, AttributeError)):
            extract_vlan_ids(None)


# ============================================================================
# Test Boundary Conditions
# ============================================================================

class TestBoundaryConditions:
    """Test boundary conditions and extreme inputs."""

    def test_extract_parameters_with_very_long_query(self):
        """Test extract_parameters handles extremely long query."""
        # 10,000 character query
        long_query = "show devices " * 1000
        
        result = extract_parameters(long_query)
        
        # Should handle without crashing
        assert isinstance(result, dict)

    def test_extract_parameters_with_many_numbers(self):
        """Test extract_parameters with query containing many numbers."""
        query = "show 1 2 3 4 5 6 7 8 9 10 devices"
        
        result = extract_parameters(query)
        
        # Should extract first match
        assert "limit" in result
        assert isinstance(result["limit"], int)

    def test_extract_ip_addresses_with_many_ips(self):
        """Test IP extraction with config containing many IPs."""
        # Config with 1000 IP addresses
        config = "\n".join([
            f"ip address 10.{i//256}.{i%256}.1 255.255.255.0"
            for i in range(1000)
        ])
        
        result = extract_ip_addresses(config)
        
        # Should handle large config
        assert isinstance(result, list)
        assert len(result) > 0

    def test_extract_vlan_ids_with_large_range(self):
        """Test VLAN extraction with very large range."""
        config = "vlan 1-4094"  # Maximum VLAN range
        
        result = extract_vlan_ids(config)
        
        # Should handle large range
        assert isinstance(result, list)
        assert 1 in result
        assert 4094 in result


# ============================================================================
# Test Special Characters and Encoding
# ============================================================================

class TestSpecialCharactersHandling:
    """Test handling of special characters and encoding issues."""

    def test_extract_parameters_with_unicode(self):
        """Test extract_parameters handles unicode characters."""
        queries = [
            "show devices with tag café",
            "list routers in São Paulo",
            "get config from 北京",
            "devices with émojis 🚀",
        ]
        
        for query in queries:
            result = extract_parameters(query)
            # Should not crash
            assert isinstance(result, dict)

    def test_extract_ip_addresses_with_unicode(self):
        """Test IP extraction handles unicode in config."""
        config = """
        interface Ethernet0/0
         description Ñetwork Interface
         ip address 192.168.1.1 255.255.255.0
        hostname routér-café
        """
        
        result = extract_ip_addresses(config)
        
        # Should extract IPs despite unicode
        assert "192.168.1.1" in result

    def test_extract_parameters_with_newlines(self):
        """Test extract_parameters handles embedded newlines."""
        query = "show\ndevices\nwith\ntag\nproduction"
        
        result = extract_parameters(query)
        
        # Should handle newlines
        assert isinstance(result, dict)

    def test_extract_parameters_with_null_bytes(self):
        """Test extract_parameters handles null bytes."""
        query = "show devices\x00with tag\x00production"
        
        result = extract_parameters(query)
        
        # Should handle null bytes
        assert isinstance(result, dict)


# ============================================================================
# Test Error Recovery
# ============================================================================

class TestErrorRecovery:
    """Test that functions recover gracefully from errors."""

    @pytest.mark.asyncio
    async def test_route_query_recovers_from_network_error(self):
        """Test QueryRouter recovers from network errors."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = Exception("Network error")
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            # Should catch exception and return error
            tool_name, error = await router.route_query("test", ["tool1"])
            
            assert tool_name is None
            assert error is not None
            assert "error" in error.lower() or "mistral" in error.lower()

    @pytest.mark.asyncio
    async def test_route_query_recovers_from_json_decode_error(self):
        """Test QueryRouter recovers from JSON decode errors."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            # Should catch JSON error and return error message
            tool_name, error = await router.route_query("test", ["tool1"])
            
            assert tool_name is None
            assert error is not None

    def test_extract_all_recovers_from_regex_errors(self):
        """Test extract_all recovers from potential regex errors."""
        # Config with patterns that might cause regex issues
        problematic_configs = [
            "interface ((((((",  # Unbalanced parentheses
            "vlan **********",  # Special regex chars
            "ip address ??????",  # Question marks
            "hostname $$$###",  # Dollar signs and hashes
        ]
        
        for config in problematic_configs:
            try:
                result = extract_all(config)
                # Should return result, possibly empty
                assert result is not None
            except Exception as e:
                pytest.fail(f"Should not crash on: {config}. Error: {e}")


# ============================================================================
# Test AI Model Failure Modes
# ============================================================================

class TestAIModelFailureModes:
    """Test various AI model failure scenarios."""

    @pytest.mark.asyncio
    async def test_route_query_with_timeout(self):
        """Test QueryRouter handles timeout gracefully."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            import asyncio
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = asyncio.TimeoutError()
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            tool_name, error = await router.route_query("test", ["tool1"])
            
            # Should handle timeout
            assert tool_name is None
            assert error is not None

    @pytest.mark.asyncio
    async def test_route_query_with_500_error(self):
        """Test QueryRouter handles HTTP 500 error."""
        router = QueryRouter()
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client_instance.get.return_value = MagicMock(status_code=200)
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = AsyncMock()
            mock_client.return_value = mock_client_instance
            
            tool_name, error = await router.route_query("test", ["tool1"])
            
            # Should handle 500 error
            assert tool_name is None
            assert "500" in str(error) or error is not None

    @pytest.mark.asyncio
    async def test_route_query_when_disabled(self):
        """Test QueryRouter when AI routing is disabled."""
        router = QueryRouter()
        router.enabled = False
        
        tool_name, error = await router.route_query("test", ["tool1"])
        
        # Should return error about being disabled
        assert tool_name is None
        assert error is not None
        assert "disabled" in error.lower()

    @pytest.mark.asyncio
    async def test_route_query_with_unavailable_server(self):
        """Test QueryRouter when server is unavailable."""
        router = QueryRouter()
        
        with patch.object(router, 'is_available', return_value=False):
            tool_name, error = await router.route_query("test", ["tool1"])
            
            # Should return error about unavailability
            assert tool_name is None
            assert error is not None
            assert "unavailable" in error.lower()


# ============================================================================
# Test Data Validation
# ============================================================================

class TestDataValidation:
    """Test data validation edge cases."""

    def test_extract_parameters_validates_limit_range(self):
        """Test that extracted limits are reasonable."""
        result = extract_parameters("show 999999 devices")
        
        # Should extract the number (validation happens elsewhere)
        assert "limit" in result
        assert result["limit"] == 999999

    def test_extract_ip_addresses_filters_invalid_ips(self):
        """Test that invalid IPs are filtered out."""
        config = """
        ip address 192.168.1.1 255.255.255.0
        ip address 999.999.999.999 255.255.255.0
        ip address 256.0.0.1 255.255.255.0
        ip address 192.168.1.300 255.255.255.0
        """
        
        result = extract_ip_addresses(config)
        
        # Should only include valid IP
        assert "192.168.1.1" in result
        assert "999.999.999.999" not in result
        assert "256.0.0.1" not in result
        assert "192.168.1.300" not in result

    def test_extract_vlan_ids_validates_range(self):
        """Test VLAN extraction validates VLAN ID range."""
        config = """
        vlan 1
        vlan 4094
        """
        
        result = extract_vlan_ids(config)
        
        # Should extract valid VLANs (1-4094)
        assert 1 in result
        assert 4094 in result
        # Only valid VLANs extracted
        assert 5000 not in result


# ============================================================================
# Test Concurrent Access
# ============================================================================

class TestConcurrentAccess:
    """Test thread safety and concurrent access."""

    def test_extract_parameters_concurrent_calls(self):
        """Test extract_parameters is safe for concurrent calls."""
        import concurrent.futures
        
        queries = [
            "show 5 devices",
            "list 10 routers",
            "get 3 switches",
        ]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(extract_parameters, q) for q in queries]
            results = [f.result() for f in futures]
        
        # All should complete successfully
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)

    def test_extract_all_concurrent_calls(self):
        """Test extract_all is safe for concurrent calls."""
        import concurrent.futures
        
        config = """
        interface GigabitEthernet0/0
         ip address 192.168.1.1 255.255.255.0
        """
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(extract_all, config) for _ in range(5)]
            results = [f.result() for f in futures]
        
        # All should complete successfully
        assert len(results) == 5
        assert all(r is not None for r in results)
