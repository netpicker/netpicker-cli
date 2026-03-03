from __future__ import annotations

import asyncio
import logging
import random
import time
from types import TracebackType
from typing import Any, Dict, Final, Optional, Type, Union

import httpx

from .errors import ApiError, Unauthorized, TooManyRequests, ServerError
from ..utils.config import Settings
from ..utils.logging import get_logger, log_api_call, log_api_response, log_error_with_context
from ..utils.proxy import should_bypass_proxy

_MAX_RETRIES: Final[int] = 3
_INITIAL_BACKOFF: Final[float] = 0.5
_JITTER_MAX: Final[float] = 0.3
_BODY_SNIPPET_LEN: Final[int] = 500

class AsyncApiClient:
    """Async HTTP client wrapping httpx.AsyncClient with retry logic."""

    def __init__(self, settings: Settings) -> None:
        self.s: Settings = settings
        self.logger: logging.Logger = get_logger('netpicker_cli.api.async')
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized: bool = False

    async def _ensure_initialized(self) -> None:
        """Lazily initialize the async client on first use."""
        if not self._initialized:
            client_kwargs = dict(
                base_url=self.s.base_url,
                headers=self.s.auth_headers(),
                timeout=self.s.timeout,
                verify=self.s.ssl_verify,
            )
            # Proxy is disabled by default (internal service).
            # When use_proxy is True, allow httpx env-var proxy detection
            # but still honour CIDR entries in no_proxy.
            if not self.s.use_proxy:
                client_kwargs["proxy"] = None
            elif should_bypass_proxy(self.s.base_url):
                self.logger.debug("Bypassing proxy for %s (CIDR match in no_proxy)", self.s.base_url)
                client_kwargs["proxy"] = None
            self._client = httpx.AsyncClient(**client_kwargs)
            self._initialized = True

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Ensure client is initialized before making requests."""
        await self._ensure_initialized()
        retries: int = _MAX_RETRIES
        backoff: float = _INITIAL_BACKOFF
        for attempt in range(retries + 1):
            start_time: float = time.time()
            try:
                log_api_call(method, url, **kwargs)
                r = await self._client.request(method, url, **kwargs)
                response_time = time.time() - start_time
                log_api_response(r.status_code, response_time)

                if r.status_code == 401:
                    log_error_with_context(Unauthorized("Unauthorized (check token)"), f"URL: {url}")
                    raise Unauthorized("Unauthorized (check token)")
                if r.status_code == 404:
                    from .errors import NotFound
                    log_error_with_context(NotFound("Resource not found"), f"URL: {url}")
                    raise NotFound("Resource not found")
                if r.status_code == 429:
                    log_error_with_context(TooManyRequests("Rate limited"), f"URL: {url}")
                    raise TooManyRequests("Rate limited")
                if 500 <= r.status_code < 600:
                    body = ""
                    try:
                        body = r.text
                    except Exception:
                        body = "<unavailable>"
                    snippet = (body[:_BODY_SNIPPET_LEN] + "...") if len(body) > _BODY_SNIPPET_LEN else body
                    error = ServerError(f"Server error {r.status_code}: {snippet}")
                    log_error_with_context(error, f"URL: {url}")
                    raise error
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as e:
                    from .errors import ApiError
                    body = ""
                    try:
                        body = r.text
                    except Exception:
                        body = "<unavailable>"
                    snippet = (body[:_BODY_SNIPPET_LEN] + "...") if len(body) > _BODY_SNIPPET_LEN else body
                    error = ApiError(f"{str(e)}: {snippet}")
                    log_error_with_context(error, f"URL: {url}")
                    raise error from e
                return r
            except (TooManyRequests, ServerError):
                if attempt == retries:
                    raise
                wait: float = backoff + random.random() * _JITTER_MAX
                self.logger.warning(
                    "Retrying in %.1fs (attempt %d/%d)", wait, attempt + 1, retries + 1,
                )
                await asyncio.sleep(wait)
                backoff *= 2
        raise ApiError("retries exhausted")

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return await self._request("GET", url, params=params)

    async def get_binary(self, url: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        r = await self._request("GET", url, params=params)
        return r.content

    async def post(self, url: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return await self._request("POST", url, json=json, params=params)

    async def post_file(
        self,
        url: str,
        filename: str,
        content: Union[str, bytes],
        content_type: str = "text/plain",
        data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Upload a file via multipart/form-data.

        The default Content-Type header (application/json) set on the client is
        removed so that httpx can generate the correct multipart boundary.
        """
        file_bytes = content.encode("utf-8") if isinstance(content, str) else content
        files = {"file": (filename, file_bytes, content_type)}
        return await self._request(
            "POST", url, files=files, data=data or {},
        )

    async def put(self, url: str, json: Dict[str, Any]) -> httpx.Response:
        return await self._request("PUT", url, json=json)

    async def patch(self, url: str, json: Dict[str, Any]) -> httpx.Response:
        return await self._request("PATCH", url, json=json)

    async def delete(self, url: str, params: dict | None = None) -> httpx.Response:
        return await self._request("DELETE", url, params=params)

    async def close(self) -> None:
        """Close the async client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._initialized = False

    async def __aenter__(self) -> AsyncApiClient:
        """Enter async context manager: initialize client."""
        await self._ensure_initialized()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit async context manager: close client."""
        await self.close()


class ApiClient:
    """Sync HTTP client wrapping httpx.Client with retry logic."""

    def __init__(self, settings: Settings) -> None:
        self.s: Settings = settings
        self.logger: logging.Logger = get_logger('netpicker_cli.api')
        self._client: Optional[httpx.Client] = None
        self._initialized: bool = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize the sync client on first use."""
        if not self._initialized:
            client_kwargs = dict(
                base_url=self.s.base_url,
                headers=self.s.auth_headers(),
                timeout=self.s.timeout,
                verify=self.s.ssl_verify,
            )
            # Proxy is disabled by default (internal service).
            # When use_proxy is True, allow httpx env-var proxy detection
            # but still honour CIDR entries in no_proxy.
            if not self.s.use_proxy:
                client_kwargs["proxy"] = None
            elif should_bypass_proxy(self.s.base_url):
                self.logger.debug("Bypassing proxy for %s (CIDR match in no_proxy)", self.s.base_url)
                client_kwargs["proxy"] = None
            self._client = httpx.Client(**client_kwargs)
            self._initialized = True

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Ensure client is initialized before making requests."""
        self._ensure_initialized()
        retries: int = _MAX_RETRIES
        backoff: float = _INITIAL_BACKOFF
        for attempt in range(retries + 1):
            start_time: float = time.time()
            try:
                log_api_call(method, url, **kwargs)
                r = self._client.request(method, url, **kwargs)
                response_time: float = time.time() - start_time
                log_api_response(r.status_code, response_time)

                if r.status_code == 401:
                    error = Unauthorized("Unauthorized (check token)")
                    log_error_with_context(error, f"URL: {url}")
                    raise error
                if r.status_code == 404:
                    from .errors import NotFound
                    error = NotFound("Resource not found")
                    log_error_with_context(error, f"URL: {url}")
                    raise error
                if r.status_code == 429:
                    error = TooManyRequests("Rate limited")
                    log_error_with_context(error, f"URL: {url}")
                    raise error
                if 500 <= r.status_code < 600:
                    body = ""
                    try:
                        body = r.text
                    except Exception:
                        body = "<unavailable>"
                    snippet = (body[:_BODY_SNIPPET_LEN] + "...") if len(body) > _BODY_SNIPPET_LEN else body
                    srv_error = ServerError(f"Server error {r.status_code}: {snippet}")
                    log_error_with_context(srv_error, f"URL: {url}")
                    raise srv_error
            # For any other 4xx that slipped through, raise as ApiError after raise_for_status
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as e:
                    from .errors import ApiError
                    # include a short response body snippet when available
                    body = ""
                    try:
                        body = r.text
                    except Exception:
                        body = "<unavailable>"
                    snippet = (body[:_BODY_SNIPPET_LEN] + "...") if len(body) > _BODY_SNIPPET_LEN else body
                    raise ApiError(f"{str(e)}: {snippet}") from e
                return r
            except (TooManyRequests, ServerError):
                if attempt == retries:
                    raise
                wait: float = backoff + random.random() * _JITTER_MAX
                time.sleep(wait)
                backoff *= 2
        raise ApiError("retries exhausted")

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self._request("GET", url, params=params)

    def get_binary(self, url: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        return self._request("GET", url, params=params).content

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self._request("POST", url, json=json, params=params)

    def post_file(
        self,
        url: str,
        filename: str,
        content: Union[str, bytes],
        content_type: str = "text/plain",
        data: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Upload a file via multipart/form-data.

        The default Content-Type header (application/json) set on the client is
        removed so that httpx can generate the correct multipart boundary.
        """
        file_bytes = content.encode("utf-8") if isinstance(content, str) else content
        files = {"file": (filename, file_bytes, content_type)}
        return self._request(
            "POST", url, files=files, data=data or {},
        )

    def put(self, url: str, json: Dict[str, Any]) -> httpx.Response:
        return self._request("PUT", url, json=json)

    def patch(self, url: str, json: Dict[str, Any]) -> httpx.Response:
        return self._request("PATCH", url, json=json)

    def delete(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._request("DELETE", url, params=params)

    def close(self) -> None:
        """Close the sync client connection."""
        if self._client is not None:
            self._client.close()
            self._initialized = False

    def __enter__(self) -> ApiClient:
        """Enter context manager: initialize client."""
        self._ensure_initialized()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit context manager: close client."""
        self.close()
