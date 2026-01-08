"""
Tests for ApiClient context manager refactoring.
Verifies lazy initialization and proper resource cleanup.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from netpicker_cli.api.client import ApiClient, AsyncApiClient
from netpicker_cli.utils.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.base_url = "https://api.example.com"
    settings.auth_headers.return_value = {"Authorization": "Bearer token"}
    settings.timeout = 30.0
    settings.insecure = False
    return settings


class TestApiClientContextManager:
    """Test sync ApiClient context manager behavior."""

    def test_lazy_initialization_on_context_enter(self, mock_settings):
        """Client should not be initialized until __enter__ is called."""
        with patch("netpicker_cli.api.client.httpx.Client"):
            client = ApiClient(mock_settings)
            # Client should not be initialized yet
            assert client._client is None
            assert not client._initialized

    def test_client_initialized_on_enter(self, mock_settings):
        """Client should be initialized when entering context."""
        with patch("netpicker_cli.api.client.httpx.Client") as mock_http_client:
            with ApiClient(mock_settings) as client:
                # Client should be initialized after __enter__
                assert client._initialized
                mock_http_client.assert_called_once()

    def test_client_closed_on_exit(self, mock_settings):
        """Client should be closed when exiting context."""
        mock_http_client_instance = MagicMock()
        with patch("netpicker_cli.api.client.httpx.Client", return_value=mock_http_client_instance):
            with ApiClient(mock_settings) as client:
                assert client._initialized
            
            # After exiting context, client should be closed
            mock_http_client_instance.close.assert_called_once()
            assert not client._initialized

    def test_lazy_initialization_on_first_request(self, mock_settings):
        """Client should initialize lazily on first request if not in context."""
        mock_http_client_instance = MagicMock()
        mock_http_client_instance.request.return_value = MagicMock(status_code=200)
        
        with patch("netpicker_cli.api.client.httpx.Client", return_value=mock_http_client_instance):
            client = ApiClient(mock_settings)
            assert not client._initialized
            
            # First request should trigger initialization
            client.get("/api/test")
            assert client._initialized
            mock_http_client_instance.request.assert_called_once()

    def test_explicit_close(self, mock_settings):
        """Explicit close() should clean up resources."""
        mock_http_client_instance = MagicMock()
        with patch("netpicker_cli.api.client.httpx.Client", return_value=mock_http_client_instance):
            client = ApiClient(mock_settings)
            client._ensure_initialized()
            assert client._initialized
            
            client.close()
            mock_http_client_instance.close.assert_called_once()
            assert not client._initialized


class TestAsyncApiClientContextManager:
    """Test async ApiClient context manager behavior."""

    @pytest.mark.asyncio
    async def test_lazy_initialization_on_context_enter(self, mock_settings):
        """Async client should not be initialized until __aenter__ is called."""
        with patch("netpicker_cli.api.client.httpx.AsyncClient"):
            client = AsyncApiClient(mock_settings)
            # Client should not be initialized yet
            assert client._client is None
            assert not client._initialized

    @pytest.mark.asyncio
    async def test_client_initialized_on_aenter(self, mock_settings):
        """Async client should be initialized when entering context."""
        mock_http_client_instance = AsyncMock()
        with patch("netpicker_cli.api.client.httpx.AsyncClient", return_value=mock_http_client_instance) as mock_http_client:
            async with AsyncApiClient(mock_settings) as client:
                # Client should be initialized after __aenter__
                assert client._initialized
                mock_http_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_closed_on_aexit(self, mock_settings):
        """Async client should be closed when exiting context."""
        mock_http_client_instance = AsyncMock()
        with patch("netpicker_cli.api.client.httpx.AsyncClient", return_value=mock_http_client_instance):
            async with AsyncApiClient(mock_settings) as client:
                assert client._initialized
            
            # After exiting context, client should be closed
            mock_http_client_instance.aclose.assert_called_once()
            assert not client._initialized

    @pytest.mark.asyncio
    async def test_lazy_initialization_on_first_request(self, mock_settings):
        """Async client should initialize lazily on first request if not in context."""
        mock_http_client_instance = AsyncMock()
        mock_http_client_instance.request = AsyncMock(return_value=MagicMock(status_code=200))
        
        with patch("netpicker_cli.api.client.httpx.AsyncClient", return_value=mock_http_client_instance):
            client = AsyncApiClient(mock_settings)
            assert not client._initialized
            
            # First request should trigger initialization
            await client.get("/api/test")
            assert client._initialized
            mock_http_client_instance.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_close(self, mock_settings):
        """Explicit close() should clean up async resources."""
        mock_http_client_instance = AsyncMock()
        with patch("netpicker_cli.api.client.httpx.AsyncClient", return_value=mock_http_client_instance):
            client = AsyncApiClient(mock_settings)
            await client._ensure_initialized()
            assert client._initialized
            
            await client.close()
            mock_http_client_instance.aclose.assert_called_once()
            assert not client._initialized
