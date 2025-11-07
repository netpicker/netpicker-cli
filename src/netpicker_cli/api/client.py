from __future__ import annotations
from typing import Any, Dict, Optional
import time, random
import httpx
from .errors import ApiError, Unauthorized, TooManyRequests, ServerError
from ..utils.config import Settings

class ApiClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._client = httpx.Client(
            base_url=settings.base_url,
            headers=settings.auth_headers(),
            timeout=settings.timeout,
            verify=not settings.insecure,
        )

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        retries = 3
        backoff = 0.5
        for attempt in range(retries + 1):
            try:
                r = self._client.request(method, url, **kwargs)
                if r.status_code == 401: raise Unauthorized("Unauthorized (check token)")
                if r.status_code == 429: raise TooManyRequests("Rate limited")
                if 500 <= r.status_code < 600: raise ServerError(f"Server error {r.status_code}")
                r.raise_for_status()
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

    def delete(self, url: str) -> httpx.Response:
        return self._request("DELETE", url)
