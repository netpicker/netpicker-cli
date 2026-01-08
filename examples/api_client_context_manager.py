#!/usr/bin/env python3
"""
Example demonstrating the refactored ApiClient context manager pattern.

This script shows both the old and new usage patterns and the benefits
of the context manager approach.
"""

from netpicker_cli.api.client import ApiClient, AsyncApiClient
from netpicker_cli.utils.config import load_settings
import asyncio


def old_pattern_example():
    """Old pattern: Manual resource management (still works!)"""
    print("=== Old Pattern (Backward Compatible) ===")
    settings = load_settings()
    
    # Client initialized on first request
    client = ApiClient(settings)
    
    try:
        response = client.get(f"/api/v1/devices/{settings.tenant}")
        devices = response.json()
        print(f"✓ Fetched {len(devices.get('items', []))} devices")
    finally:
        # Must remember to close manually
        client.close()
        print("✓ Client closed manually")


def new_pattern_example():
    """New pattern: Context manager with automatic cleanup"""
    print("\n=== New Pattern (Recommended) ===")
    settings = load_settings()
    
    # Client initialized on __enter__, closed on __exit__
    with ApiClient(settings) as client:
        response = client.get(f"/api/v1/devices/{settings.tenant}")
        devices = response.json()
        print(f"✓ Fetched {len(devices.get('items', []))} devices")
    # Automatic cleanup - no need to remember .close()
    print("✓ Client closed automatically")


async def async_pattern_example():
    """Async pattern: Context manager for async operations"""
    print("\n=== Async Pattern ===")
    settings = load_settings()
    
    # Async context manager
    async with AsyncApiClient(settings) as client:
        response = await client.get(f"/api/v1/devices/{settings.tenant}")
        devices = response.json()
        print(f"✓ Fetched {len(devices.get('items', []))} devices")
    print("✓ Async client closed automatically")


def lazy_initialization_demo():
    """Demonstrate lazy initialization behavior"""
    print("\n=== Lazy Initialization Demo ===")
    settings = load_settings()
    
    # Step 1: Create client (no connection yet)
    client = ApiClient(settings)
    print(f"Client created: initialized={client._initialized}")
    
    # Step 2: Make first request (triggers initialization)
    response = client.get(f"/api/v1/devices/{settings.tenant}")
    print(f"After request: initialized={client._initialized}")
    
    # Step 3: Cleanup
    client.close()
    print(f"After close: initialized={client._initialized}")


def resource_efficiency_demo():
    """Show resource efficiency with context managers"""
    print("\n=== Resource Efficiency Demo ===")
    settings = load_settings()
    
    # Create multiple clients - connections only when needed
    clients = [ApiClient(settings) for _ in range(5)]
    print(f"Created 5 clients: {sum(c._initialized for c in clients)} initialized")
    
    # Use only one - only one connection created
    with clients[0] as active_client:
        response = active_client.get(f"/api/v1/devices/{settings.tenant}")
        print(f"After using 1: {sum(c._initialized for c in clients)} initialized")
    
    # Cleanup unused clients (no-op since never initialized)
    for c in clients:
        c.close()
    print("✓ All clients cleaned up efficiently")


def main():
    """Run all examples."""
    print("ApiClient Context Manager Examples\n")
    print("=" * 60)
    
    try:
        # Run synchronous examples
        old_pattern_example()
        new_pattern_example()
        lazy_initialization_demo()
        resource_efficiency_demo()
        
        # Run async example
        asyncio.run(async_pattern_example())
        
        print("\n" + "=" * 60)
        print("✓ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("Note: Examples require a valid netpicker configuration")


if __name__ == "__main__":
    main()
