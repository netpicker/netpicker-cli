# Caching Feature Documentation

## Overview

NetPicker CLI now includes a session-scoped caching layer for API responses that don't change frequently. This improves performance for repetitive queries during a CLI session.

## How It Works

- **Session Scope**: Cache lives for the duration of a CLI command execution and is automatically cleared when the command completes
- **Thread-Safe**: Uses thread-local storage to ensure each CLI invocation has its own cache
- **Configurable**: Use the `--no-cache` flag to bypass cache when fresh data is needed

## Cached Commands

The following commands use caching for static reference data:

### compliance_policy.list
- **Cache Key**: `policies:{tenant}`
- **When Cached**: Always (unless `--no-cache` is used)
- **Description**: Lists compliance policies

```bash
# Use cache (fast)
netpicker policy list

# Bypass cache (fresh data)
netpicker policy list --no-cache
```

### automation.list-fixtures
- **Cache Key**: `fixtures:{tenant}`
- **When Cached**: Always (unless `--no-cache` is used)
- **Description**: Lists available automation fixtures

```bash
netpicker automation list-fixtures
netpicker automation list-fixtures --no-cache
```

### automation.list-jobs
- **Cache Key**: `jobs:{tenant}`
- **When Cached**: Only when no `--pattern` filter is applied (to avoid caching filtered results)
- **Description**: Lists automation jobs

```bash
# Use cache (no pattern filter)
netpicker automation list-jobs

# Fetch fresh with pattern filter (bypasses cache)
netpicker automation list-jobs --pattern my-pattern

# Bypass cache explicitly
netpicker automation list-jobs --no-cache
```

### devices.list
- **Cache Key**: `devices:{tenant}:default`
- **When Cached**: Only for default queries (no tag filter, default pagination, no --all flag)
- **Description**: Lists devices

```bash
# Use cache (default pagination, no filters)
netpicker devices list

# Bypass cache (custom query)
netpicker devices list --tag production   # Tag filtering bypasses cache
netpicker devices list --limit 100        # Custom pagination bypasses cache
netpicker devices list --all              # Fetching all pages bypasses cache
netpicker devices list --no-cache         # Explicit bypass
```

## Cache Implementation

The caching layer is implemented in [src/netpicker_cli/utils/cache.py](src/netpicker_cli/utils/cache.py) and provides:

### SessionCache Class
- `get(key, factory)`: Returns cached value or computes via factory function
- `set(key, value)`: Explicitly cache a value
- `enable()`: Enable caching
- `disable()`: Disable caching
- `is_enabled()`: Check if caching is active
- `clear()`: Clear all cached entries

### Context Manager: get_session_cache()
```python
from src.netpicker_cli.utils.cache import get_session_cache

with get_session_cache(use_cache=True) as cache:
    # Cache is active and will be cleared when context exits
    data = cache.get("key", lambda: expensive_operation())
```

### Utility Functions
- `clear_session_cache()`: Manually clear the session cache
- `disable_cache()`: Disable caching globally for current thread
- `enable_cache()`: Enable caching globally for current thread

## Benefits

1. **Performance**: Reduces redundant API calls for static reference data
2. **User Control**: `--no-cache` flag allows forcing fresh data when needed
3. **Clean Lifecycle**: Cache automatically cleared between CLI invocations
4. **Thread-Safe**: Each CLI execution gets isolated cache storage

## When Cache Is Used

Cache is automatically enabled by default for all cached commands. It will be used when:
1. The command is one of the cached commands
2. No `--no-cache` flag is provided
3. Query parameters don't require bypassing (e.g., no filters for list_jobs, default pagination for devices)

## Example Scenarios

### Scenario 1: Quick Multiple Queries
```bash
# First call fetches from API
netpicker policy list

# Second call returns from cache (no API call)
netpicker policy list

# Add --no-cache to force fresh fetch
netpicker policy list --no-cache
```

### Scenario 2: Filtered Queries
```bash
# Uses cache (static policies)
netpicker policy list

# Devices with tag filter - bypasses cache
netpicker devices list --tag production

# Uses cache (static jobs, no pattern)
netpicker automation list-jobs

# Pattern filter - bypasses cache
netpicker automation list-jobs --pattern test-job
```

### Scenario 3: Data Changed After Login
```bash
# Login updates configuration
netpicker auth login --base-url https://api.example.com --token abc123

# Cache is preserved but contains old data
netpicker policy list

# Use --no-cache to get fresh data with new credentials
netpicker policy list --no-cache
```

## Technical Details

### Cache Storage
- Uses Python's `threading.local()` for thread-local cache isolation
- Dictionary-based in-memory storage
- No persistence to disk

### Cache Lifecycle
1. Cache created when entering `get_session_cache()` context
2. Entries added on first access via `cache.get(key, factory)`
3. Cache cleared automatically when exiting context
4. Each CLI command invocation gets a fresh cache

### Performance Impact
- Small memory overhead (typically KB per session)
- Cache lookups are O(1) dictionary access
- Reduces network latency for repeated queries
- No impact on commands that bypass caching

## Configuration

Currently, caching is always enabled by default. Future versions may add:
- Global `--cache-enabled` / `--cache-disabled` flags
- Cache TTL (time-to-live) configuration
- Cache size limits
- Per-command cache bypass in config file

## Debugging

To verify cache behavior:

```bash
# Enable verbose output to see API calls
netpicker --verbose policy list
netpicker --verbose policy list  # Will see fewer API logs if cached

# Check if cache is used
netpicker policy list --no-cache --format json
```
