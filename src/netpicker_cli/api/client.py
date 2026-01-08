from __future__ import annotations
from typing import Any, Dict, Optional
import time
import random
import asyncio
import httpx
from .errors import Unauthorized, TooManyRequests, ServerError
from ..utils.config import Settings
from ..utils.logging import get_logger, log_api_call, log_api_response, log_error_with_context

class AsyncApiClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.logger = get_logger('netpicker_cli.api.async')
        self._client = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazily initialize the async client on first use."""
        if not self._initialized:
            self._client = httpx.AsyncClient(
                base_url=self.s.base_url,
                headers=self.s.auth_headers(),
                timeout=self.s.timeout,
                verify=not self.s.insecure,
            )
            self._initialized = True

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Ensure client is initialized before making requests."""
        await self._ensure_initialized()
        retries = 3
        backoff = 0.5
        for attempt in range(retries + 1):
            start_time = time.time()
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
                    snippet = (body[:500] + "...") if len(body) > 500 else body
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
                    snippet = (body[:500] + "...") if len(body) > 500 else body
                    error = ApiError(f"{str(e)}: {snippet}")
                    log_error_with_context(error, f"URL: {url}")
                    raise error from e
                return r
            except (TooManyRequests, ServerError):
                if attempt == retries:
                    raise
                retry_msg = f"Retrying in {backoff:.1f}s (attempt {attempt + 1}/{retries + 1})"
                self.logger.warning(retry_msg)
                await asyncio.sleep(backoff + random.random()*0.3)
                backoff *= 2
        error = ApiError("retries exhausted")
        log_error_with_context(error, f"URL: {url}")
        raise error

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return await self._request("GET", url, params=params)

    async def get_binary(self, url: str) -> bytes:
        r = await self._request("GET", url)
        return r.content

    async def post(self, url: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return await self._request("POST", url, json=json, params=params)

    async def patch(self, url: str, json: Dict[str, Any]) -> httpx.Response:
        return await self._request("PATCH", url, json=json)

    async def delete(self, url: str, params: dict | None = None) -> httpx.Response:
        return await self._request("DELETE", url, params=params)

    async def close(self) -> None:
        """Close the async client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._initialized = False

    async def __aenter__(self) -> "AsyncApiClient":
        """Enter async context manager: initialize client."""
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit async context manager: close client."""
        await self.close()


class ApiClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.logger = get_logger('netpicker_cli.api')
        self._client = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize the sync client on first use."""
        if not self._initialized:
            self._client = httpx.Client(
                base_url=self.s.base_url,
                headers=self.s.auth_headers(),
                timeout=self.s.timeout,
                verify=not self.s.insecure,
            )
            self._initialized = True

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Ensure client is initialized before making requests."""
        self._ensure_initialized()
        retries = 3
        backoff = 0.5
        for attempt in range(retries + 1):
            try:
                r = self._client.request(method, url, **kwargs)
                if r.status_code == 401:
                    raise Unauthorized("Unauthorized (check token)")
                if r.status_code == 404:
                    from .errors import NotFound
                    raise NotFound("Resource not found")
                if r.status_code == 429:
                    raise TooManyRequests("Rate limited")
                if 500 <= r.status_code < 600:
                    body = ""
                    try:
                        body = r.text
                    except Exception:
                        body = "<unavailable>"
                    snippet = (body[:500] + "...") if len(body) > 500 else body
                    raise ServerError(f"Server error {r.status_code}: {snippet}")
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
                    snippet = (body[:500] + "...") if len(body) > 500 else body
                    raise ApiError(f"{str(e)}: {snippet}") from e
                return r
            except (TooManyRequests, ServerError):
                if attempt == retries: raise
                time.sleep(backoff + random.random()*0.3); backoff *= 2
        raise ApiError("retries exhausted")

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self._request("GET", url, params=params)

    def get_binary(self, url: str) -> bytes:
        return self._request("GET", url).content

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        return self._request("POST", url, json=json, params=params)

    def patch(self, url: str, json: Dict[str, Any]) -> httpx.Response:
        return self._request("PATCH", url, json=json)

    def delete(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._request("DELETE", url, params=params)

    def close(self) -> None:
        """Close the sync client connection."""
        if self._client is not None:
            self._client.close()
            self._initialized = False

    def __enter__(self) -> "ApiClient":
        """Enter context manager: initialize client."""
        self._ensure_initialized()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        """Exit context manager: close client."""
        self.close()
