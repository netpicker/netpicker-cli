"""
Session-scoped caching layer for API responses.

This module provides a context-managed cache that lives for the duration of a CLI
command execution. The cache is automatically cleared when the context exits,
preventing stale data between commands.

Usage:
    # Get or create session cache
    with get_session_cache() as cache:
        # Make cached API calls
        result = cache.get("policies", lambda: cli.get(...).json())
    # Cache is cleared here
    
    # Or use the decorator
    @cached_response(key="device_types")
    def fetch_device_types():
        return cli.get("/api/v1/devices/types").json()
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Callable, Optional
from functools import wraps
import threading

# Thread-local storage for session caches
_thread_local = threading.local()


class SessionCache:
    """Context-managed cache that lives for CLI command execution."""
    
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._enabled: bool = True
    
    def get(self, key: str, factory: Callable[[], Any]) -> Any:
        """
        Get a cached value or compute it.
        
        Args:
            key: Cache key
            factory: Callable that returns the value if not cached
            
        Returns:
            Cached or freshly computed value
            
        Examples:
            >>> cache.get("policies", lambda: cli.get("/api/v1/policy/{tenant}").json())
        """
        if not self._enabled:
            return factory()
        
        if key not in self._data:
            self._data[key] = factory()
        return self._data[key]
    
    def set(self, key: str, value: Any) -> None:
        """Explicitly set a cache value."""
        if self._enabled:
            self._data[key] = value
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._data.clear()
    
    def disable(self) -> None:
        """Disable caching (pass-through mode)."""
        self._enabled = False
    
    def enable(self) -> None:
        """Enable caching."""
        self._enabled = True
    
    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled


@contextmanager
def get_session_cache(use_cache: bool = True) -> SessionCache:
    """
    Get or create a session cache for API responses.
    
    This context manager ensures the cache is cleared when the command completes,
    preventing stale data between CLI invocations.
    
    Args:
        use_cache: Whether to enable caching (can be set to False via --no-cache)
        
    Yields:
        SessionCache instance for storing/retrieving responses
        
    Examples:
        >>> with get_session_cache(use_cache=not args.no_cache) as cache:
        ...     policies = cache.get("policies", lambda: cli.get(...).json())
    """
    if not hasattr(_thread_local, 'cache'):
        _thread_local.cache = SessionCache()
    
    cache = _thread_local.cache
    
    # Enable/disable based on parameter
    if use_cache:
        cache.enable()
    else:
        cache.disable()
    
    try:
        yield cache
    finally:
        # Clear cache when exiting context
        cache.clear()
        cache.enable()  # Reset to enabled for next command


def cached_response(key: str, use_cache: bool = True) -> Callable:
    """
    Decorator to cache API response with automatic session lifecycle.
    
    This decorator wraps a function to cache its result for the CLI session.
    The cache is cleared when the session ends.
    
    Args:
        key: Cache key for storing the response
        use_cache: Whether caching is enabled (set from --no-cache flag)
        
    Returns:
        Decorated function that caches results
        
    Examples:
        >>> @cached_response(key="device_types", use_cache=not args.no_cache)
        ... def fetch_device_types():
        ...     return cli.get("/api/v1/devices/types").json()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get or create thread-local cache
            if not hasattr(_thread_local, 'cache'):
                _thread_local.cache = SessionCache()
            
            cache = _thread_local.cache
            
            # If caching disabled, bypass cache
            if not cache.is_enabled():
                return func(*args, **kwargs)
            
            # Return cached or computed value
            return cache.get(key, lambda: func(*args, **kwargs))
        
        return wrapper
    
    return decorator


def clear_session_cache() -> None:
    """Manually clear the session cache."""
    if hasattr(_thread_local, 'cache'):
        _thread_local.cache.clear()


def disable_cache() -> None:
    """Disable caching for current session."""
    if hasattr(_thread_local, 'cache'):
        _thread_local.cache.disable()


def enable_cache() -> None:
    """Enable caching for current session."""
    if hasattr(_thread_local, 'cache'):
        _thread_local.cache.enable()
