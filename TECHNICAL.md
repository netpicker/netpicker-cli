# NetPicker CLI - Technical Documentation

> **Last Updated**: January 8, 2026  
> **Version**: 0.1.1  
> **Python**: 3.11+

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Directory Structure](#directory-structure)
3. [Core Components](#core-components)
4. [Command Flow](#command-flow)
5. [File Reference](#file-reference)
6. [Testing Guide](#testing-guide)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Common Development Tasks](#common-development-tasks)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                         │
│                      (netpicker_cli/cli.py)                     │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Command Modules (Typer Apps)                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ devices │ │ backups │ │ policy  │ │compliance│ │automation│  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                            │
│  │   ai    │ │  auth   │ │ health  │                            │
│  └─────────┘ └─────────┘ └─────────┘                            │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Utilities Layer                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ config  │ │ helpers │ │ output  │ │  cache  │ │validation│   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Client Layer                         │
│  ┌───────────────────────┐  ┌───────────────────────┐           │
│  │  ApiClient (sync)     │  │ AsyncApiClient (async)│           │
│  │  - GET/POST/PATCH/DEL │  │  - Parallel fetching  │           │
│  └───────────────────────┘  └───────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NetPicker REST API                          │
│                   (External Service)                             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Patterns

1. **Typer Framework**: All commands use Typer for CLI argument parsing
2. **Centralized Helpers**: Common logic in `utils/helpers.py` (DRY principle)
3. **Session-Scoped Caching**: API responses cached per-command execution
4. **Async Parallel Fetching**: Pagination uses `asyncio.gather()` for performance
5. **Multi-Format Output**: All commands support table/json/csv/yaml via `OutputFormatter`

---

## Directory Structure

```
netpicker-cli/
├── src/netpicker_cli/           # Main source code
│   ├── __init__.py              # Package marker
│   ├── cli.py                   # CLI entry point, command registration
│   ├── api_server.py            # FastAPI server (optional)
│   │
│   ├── api/                     # API client layer
│   │   ├── client.py            # ApiClient & AsyncApiClient
│   │   └── errors.py            # Custom exceptions
│   │
│   ├── ai/                      # AI routing
│   │   ├── __init__.py
│   │   └── router.py            # Query-to-tool routing logic
│   │
│   ├── commands/                # CLI command implementations
│   │   ├── ai.py                # AI/NLP commands
│   │   ├── auth.py              # Authentication (login/logout)
│   │   ├── automation.py        # Job execution & queue management
│   │   ├── backups.py           # Config backup operations
│   │   ├── compliance.py        # Compliance reports
│   │   ├── compliance_policy.py # Policy CRUD & rules
│   │   ├── devices.py           # Device management
│   │   ├── health.py            # Health check
│   │   └── whoami.py            # Current user info
│   │
│   ├── mcp/                     # Model Context Protocol server
│   │   ├── __init__.py
│   │   ├── server.py            # MCP tool implementations
│   │   └── README.md            # MCP documentation
│   │
│   └── utils/                   # Shared utilities
│       ├── cache.py             # Session-scoped caching
│       ├── cli_helpers.py       # CLI context managers
│       ├── command_base.py      # Base command utilities
│       ├── config.py            # Settings & configuration
│       ├── config_extraction.py # Config parsing utilities
│       ├── files.py             # File I/O helpers
│       ├── helpers.py           # Centralized DRY helpers
│       ├── logging.py           # Logging setup
│       ├── output.py            # OutputFormatter (multi-format)
│       ├── pagination.py        # Pagination utilities
│       └── validation.py        # Input validation
│
├── tests/                       # Test suite
│   ├── conftest.py              # Shared fixtures
│   ├── integration/             # Integration tests (API mocking)
│   ├── unit/                    # Unit tests
│   └── mocks/                   # Mock-based tests
│
├── pyproject.toml               # Project configuration
├── README.md                    # User documentation
├── TECHNICAL.md                 # This file
├── CACHING.md                   # Caching documentation
└── CONTRIBUTING.md              # Contribution guidelines
```

---

## Core Components

### 1. CLI Entry Point (`cli.py`)

**Purpose**: Registers all command modules with Typer

**Key Elements**:
- `app = typer.Typer()` - Main application
- `@app.callback()` - Global options (--verbose, --quiet)
- `app.add_typer()` - Registers subcommand modules

**Flow**:
```
netpicker <command> <subcommand> [options]
    │
    ▼
cli.py (main_callback) → setup_logging → command module
```

### 2. API Client (`api/client.py`)

**Purpose**: HTTP communication with NetPicker API

**Classes**:
| Class | Purpose | Use Case |
|-------|---------|----------|
| `ApiClient` | Synchronous HTTP client | Single requests |
| `AsyncApiClient` | Async HTTP client | Parallel page fetching |

**Features**:
- Automatic retry with exponential backoff (3 retries)
- Rate limiting handling (429 responses)
- Auth header injection from Settings
- Error mapping to custom exceptions

**Error Handling**:
```python
# api/errors.py
ApiError       # Base exception
NotFound       # 404 responses
Unauthorized   # 401 responses  
TooManyRequests # 429 responses
ServerError    # 5xx responses
```

### 3. Configuration (`utils/config.py`)

**Purpose**: Load and manage CLI settings

**Settings Sources** (priority order):
1. Environment variables (`NETPICKER_*`)
2. Config file (`~/.config/netpicker/config.json`)
3. OS keyring (for token storage)

**Key Settings**:
```python
class Settings:
    base_url: str       # API base URL
    tenant: str         # Tenant identifier
    token: str          # API token (from keyring or env)
    timeout: float      # Request timeout (default: 30)
    insecure: bool      # Skip TLS verification
    verbose: bool       # Debug logging
    quiet: bool         # Suppress output
```

### 4. Centralized Helpers (`utils/helpers.py`)

**Purpose**: DRY utilities used across all command modules

**Key Functions**:
| Function | Purpose | Used By |
|----------|---------|---------|
| `extract_items_from_response(data)` | Normalize API response to list | devices, backups, compliance |
| `filter_items_by_tag(items, tag)` | Client-side tag filtering | devices |
| `format_tags_for_display(tags)` | Format tags as comma-separated | devices, automation |
| `safe_dict_get(data, key, default)` | Safe dictionary access | all modules |
| `ensure_list(data)` | Wrap non-list in list | compliance_policy |
| `extract_ip_from_text(text)` | Regex IP extraction | ai |

### 5. Session Cache (`utils/cache.py`)

**Purpose**: Cache API responses during CLI command execution

**Design**:
- Thread-local storage for isolation
- Cleared automatically when command exits
- Bypass with `--no-cache` flag

**Usage Pattern**:
```python
from ..utils.cache import get_session_cache

with get_session_cache(use_cache=not no_cache) as cache:
    data = cache.get(cache_key, lambda: api_call())
```

### 6. Output Formatter (`utils/output.py`)

**Purpose**: Format command output in multiple formats

**Supported Formats**:
- `table` - Human-readable ASCII table (default)
- `json` - JSON output
- `csv` - CSV output
- `yaml` - YAML output

**Usage**:
```python
formatter = OutputFormatter(format=format, output_file=output_file)
formatter.output(data, headers=["col1", "col2"])
```

---

## Command Flow

### Typical Command Execution Flow

```
1. User runs: netpicker devices list --tag production

2. CLI Entry (cli.py)
   └─→ main_callback() sets up logging, ctx.obj

3. Command Module (commands/devices.py)
   └─→ list_devices() function invoked with parsed args

4. Configuration Loading
   └─→ load_settings() → Settings object

5. API Client Creation
   └─→ ApiClient(settings) or AsyncApiClient(settings)

6. Cache Check (if enabled)
   └─→ get_session_cache() → cache.get(key, factory)

7. API Request
   └─→ cli.get("/api/v1/devices/{tenant}") → httpx request

8. Response Processing
   └─→ extract_items_from_response() → filter_items_by_tag()

9. Output Formatting
   └─→ OutputFormatter.output(data, headers)

10. Display to User
    └─→ typer.echo() or file write
```

### Pagination Flow (with parallel fetching)

```
1. First page request to determine total pages

2. If --parallel flag and --all:
   └─→ AsyncApiClient used
   └─→ asyncio.gather() fetches N pages concurrently
   └─→ Results aggregated

3. Else sequential fetching:
   └─→ While loop until empty page returned
```

---

## File Reference

### Command Modules

| File | Lines | Commands | Description |
|------|-------|----------|-------------|
| `commands/automation.py` | 1358 | list-fixtures, list-jobs, store-job, show-job, delete-job, test-job, execute-job, logs, show-log, list-queue, store-queue, show-queue, delete-queue, review-queue | Automation job management |
| `commands/compliance.py` | 810 | overview, report-tenant, devices, export, status, failures, log, report-config | Compliance reporting |
| `commands/compliance_policy.py` | 610 | list, show, create, update, replace, add-rule, remove-rule, test-rule, execute-rules | Policy management |
| `commands/backups.py` | 535 | recent, list, fetch, diff, search, commands, upload, history | Config backup operations |
| `commands/ai.py` | 409 | query, status, tools, chat | AI-powered queries |
| `commands/devices.py` | 387 | list, show, create, delete | Device CRUD |
| `commands/auth.py` | 121 | login, logout, status | Authentication |
| `commands/whoami.py` | 108 | whoami | User info |
| `commands/health.py` | 50 | health | Health check |

### Utility Modules

| File | Lines | Purpose |
|------|-------|---------|
| `utils/validation.py` | 432 | Input validation (IP, hostname, limit, offset, tags, JSON) |
| `utils/helpers.py` | 324 | Centralized helper functions (DRY) |
| `utils/config_extraction.py` | 243 | Config parsing for AI routing |
| `utils/output.py` | 198 | Multi-format output (table/json/csv/yaml) |
| `utils/cache.py` | 173 | Session-scoped caching |
| `utils/logging.py` | 136 | Logging setup and utilities |
| `utils/config.py` | 119 | Settings and configuration |

### API Layer

| File | Lines | Purpose |
|------|-------|---------|
| `api/client.py` | 207 | ApiClient & AsyncApiClient |
| `api/errors.py` | 20 | Custom exception classes |

### MCP Server

| File | Lines | Purpose |
|------|-------|---------|
| `mcp/server.py` | 509 | MCP tool implementations for AI assistants |

---

## Testing Guide

### Test Structure

```
tests/
├── conftest.py                    # Shared fixtures (runner, mock_settings)
├── integration/                   # Tests with mocked API responses
│   ├── test_automation.py         # Automation commands (18 tests)
│   ├── test_backups.py            # Backup commands (16 tests)
│   ├── test_backups_diff.py       # Diff functionality (7 tests)
│   ├── test_backups_diff_cli.py   # Diff CLI (3 tests)
│   ├── test_backups_recent.py     # Recent backups (3 tests)
│   ├── test_devices.py            # Device commands (7 tests)
│   ├── test_devices_list.py       # Device list (2 tests)
│   ├── test_devices_list_show.py  # Device show (2 tests)
│   ├── test_devices_delete.py     # Device delete (2 tests)
│   ├── test_ai_routing.py         # AI query routing (20 tests)
│   ├── test_compliance.py         # Compliance (if exists)
│   ├── test_edge_cases.py         # Edge cases & errors (15 tests)
│   ├── test_health.py             # Health check (1 test)
│   ├── test_client_errors.py      # API error handling (5 tests)
│   ├── test_mcp_server.py         # MCP server (12 tests)
│   ├── test_mcp_tools_enhanced.py # MCP tools (10 tests)
│   ├── test_integration_workflow.py # E2E workflow (3 tests)
│   └── test_cli_smoke.py          # Basic CLI smoke (5 tests)
│
├── unit/                          # Unit tests (no mocking)
│   ├── test_utils_files.py        # File utilities
│   ├── test_config_load.py        # Config loading
│   ├── test_parameter_extraction.py # Parameter parsing
│   ├── test_extraction.py         # Config extraction
│   ├── test_callbacks.py          # Callback functions
│   ├── test_edge_cases.py         # Unit edge cases
│   ├── test_properties_*.py       # Property-based tests
│   └── test_api_client_context.py # API client context
│
└── mocks/                         # Mock-based tests
    └── test_mcp_tools.py          # MCP tool mocks
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=netpicker_cli --cov-report=term-missing

# Run specific test file
pytest tests/integration/test_automation.py

# Run specific test
pytest tests/integration/test_automation.py::TestAutomationCommands::test_list_fixtures_success

# Run tests matching pattern
pytest tests/ -k "devices"

# Run with verbose output
pytest tests/ -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Show slowest tests
pytest tests/ --durations=10
```

### Test Fixtures (conftest.py)

```python
# Key fixtures available in all tests

@pytest.fixture
def runner():
    """CLI test runner (CliRunner from typer.testing)"""
    return CliRunner()

@pytest.fixture
def mock_settings():
    """Pre-configured Settings object for tests"""
    return Settings(
        base_url="https://api.example.com",
        tenant="test-tenant",
        token="test-token"
    )

@pytest.fixture
def sample_devices():
    """Sample device data for tests"""
    return [...]
```

### Test Categories

| Category | Location | What It Tests |
|----------|----------|---------------|
| **Smoke Tests** | `test_cli_smoke.py` | CLI loads, help works |
| **Command Tests** | `test_*.py` | Individual command behavior |
| **Error Tests** | `test_edge_cases.py`, `test_client_errors.py` | Error handling |
| **Integration Tests** | `test_integration_workflow.py` | Multi-command workflows |
| **MCP Tests** | `test_mcp_*.py` | MCP server functionality |
| **Unit Tests** | `tests/unit/` | Individual functions |

---

## Troubleshooting Guide

### Common Issues & Solutions

#### 1. "No token found" Error

**Symptom**: `No token found. Run: netpicker login --base-url ... --token ...`

**Causes & Solutions**:
| Cause | Solution |
|-------|----------|
| Not logged in | Run `netpicker auth login --base-url URL --tenant TENANT --token TOKEN` |
| Keyring issues | Set `export NETPICKER_TOKEN=your-token` |
| Wrong config path | Check `~/.config/netpicker/config.json` |

**Debug Steps**:
```bash
# Check config
cat ~/.config/netpicker/config.json

# Test with env var
export NETPICKER_TOKEN=your-token
netpicker health
```

**Code Location**: `utils/config.py` → `load_settings()`

---

#### 2. 403 Forbidden

**Symptom**: `403 Forbidden` or `Unauthorized`

**Causes & Solutions**:
| Cause | Solution |
|-------|----------|
| Wrong tenant | Verify tenant name matches token |
| Expired token | Get new token from NetPicker UI |
| Missing permissions | Check token has `access:api` scope |

**Debug Steps**:
```bash
netpicker whoami --format json
netpicker --verbose health
```

**Code Location**: `api/client.py` → `_request()` method

---

#### 3. Connection Timeout

**Symptom**: Request times out

**Causes & Solutions**:
| Cause | Solution |
|-------|----------|
| Slow network | Increase timeout: `export NETPICKER_TIMEOUT=60` |
| Wrong URL | Verify `NETPICKER_BASE_URL` |
| Firewall | Check network connectivity |

**Code Location**: `api/client.py` → `httpx.Client(timeout=...)` 

---

#### 4. "limit cannot exceed 1000" Validation Error

**Symptom**: `ValidationError: limit cannot exceed 1000`

**Cause**: User passed `--limit` value > 1000

**Solution**: Use `--limit 1000` or less; use `--all` for full fetch

**Code Location**: `utils/validation.py` → `validate_limit()`

---

#### 5. Empty Results

**Symptom**: Command returns empty table/no results

**Causes & Solutions**:
| Cause | Solution |
|-------|----------|
| No data exists | Verify data exists in NetPicker UI |
| Wrong filter | Check `--tag` or other filters |
| API response format changed | Check API version compatibility |

**Debug Steps**:
```bash
# Check raw response
netpicker devices list --format json

# Enable verbose logging
netpicker --verbose devices list
```

**Code Location**: Check `extract_items_from_response()` in `utils/helpers.py`

---

#### 6. Test Failures

**Common Test Issues**:

| Issue | Cause | Solution |
|-------|-------|----------|
| URL mismatch | Test uses trailing slash, code doesn't | Fix test URL patterns |
| Mock not matched | `respx` pattern doesn't match actual URL | Check URL in test |
| Settings not mocked | `load_settings` not patched | Add `mock.patch` |
| Field name mismatch | Test data has wrong field names | Check API response format |

**Debug Test**:
```bash
# Run single test with output
pytest tests/integration/test_devices.py::test_list_devices -xvs

# Show full traceback
pytest tests/ --tb=long
```

---

#### 7. Keyring Issues on Linux

**Symptom**: `keyring.errors.NoKeyringError` or similar

**Solution**:
```bash
pip install keyrings.alt
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
```

**Code Location**: `commands/auth.py` → `login()` function

---

#### 8. Import Errors

**Symptom**: `ModuleNotFoundError` or `ImportError`

**Causes & Solutions**:
| Cause | Solution |
|-------|----------|
| Package not installed | `pip install -e ".[dev,mcp]"` |
| Wrong Python version | Use Python 3.11+ |
| Circular import | Check import order in affected module |

---

### Debug Checklist

```bash
# 1. Verify installation
pip show netpicker-cli

# 2. Check Python version
python --version  # Should be 3.11+

# 3. Verify configuration
netpicker auth status
cat ~/.config/netpicker/config.json

# 4. Test connectivity
netpicker health

# 5. Check user permissions
netpicker whoami --format json

# 6. Enable debug logging
netpicker --verbose devices list

# 7. Check raw API response
netpicker devices list --format json
```

---

## Common Development Tasks

### Adding a New Command

1. **Create command file** in `src/netpicker_cli/commands/`

```python
# commands/new_feature.py
import typer
from ..utils.config import load_settings
from ..api.client import ApiClient
from ..utils.output import OutputFormatter
from ..utils.cache import get_session_cache

app = typer.Typer(add_completion=False)

@app.command("list")
def list_items(
    format: str = typer.Option("table", "--format", help="Output format"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    """List items."""
    s = load_settings()
    cli = ApiClient(s)
    
    with get_session_cache(use_cache=not no_cache) as cache:
        data = cache.get("items:key", lambda: cli.get("/api/endpoint").json())
    
    formatter = OutputFormatter(format=format)
    formatter.output(data, headers=["col1", "col2"])
```

2. **Register in cli.py**:
```python
from .commands import new_feature
app.add_typer(new_feature.app, name="new-feature", help="New feature commands")
```

3. **Add tests** in `tests/integration/test_new_feature.py`

### Adding a New Helper Function

1. **Add to `utils/helpers.py`**:
```python
def new_helper(data: Any) -> Any:
    """
    Description of helper function.
    
    Args:
        data: Input data
        
    Returns:
        Processed data
    """
    # Implementation
    return processed_data
```

2. **Import in command module**:
```python
from ..utils.helpers import new_helper
```

### Adding Output Format Support

Already supported! Just use `OutputFormatter`:
```python
from ..utils.output import OutputFormatter

formatter = OutputFormatter(format=format, output_file=output_file)
formatter.output(data, headers=["col1", "col2"])
```

### Adding Caching to a Command

```python
from ..utils.cache import get_session_cache

@app.command("list")
def list_items(
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache"),
):
    s = load_settings()
    cli = ApiClient(s)
    
    cache_key = f"items:{s.tenant}"
    with get_session_cache(use_cache=not no_cache) as cache:
        data = cache.get(cache_key, lambda: cli.get("/endpoint").json())
```

### Adding Parallel Fetching

```python
import asyncio
from ..api.client import AsyncApiClient

async def _fetch_all_pages():
    async_client = AsyncApiClient(s)
    try:
        tasks = [async_client.get(url, params={"page": p}) for p in pages]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        # Process responses
    finally:
        await async_client.close()
    return results

collected = asyncio.run(_fetch_all_pages())
```

---

## API Endpoints Reference

| Endpoint Pattern | Method | Used By |
|-----------------|--------|---------|
| `/api/v1/devices/{tenant}` | GET | devices list |
| `/api/v1/devices/{tenant}/{ip}` | GET/DELETE | devices show/delete |
| `/api/v1/devices/{tenant}` | POST | devices create |
| `/api/v1/devices/{tenant}/by_tags` | POST | devices list --tag |
| `/api/v1/devices/{tenant}/recent-configs/` | GET | backups recent |
| `/api/v1/devices/{tenant}/{ip}/configs` | GET/POST | backups list/upload |
| `/api/v1/devices/{tenant}/{ip}/config/history` | GET | backups history |
| `/api/v1/policy/{tenant}` | GET/POST | policy list/create |
| `/api/v1/policy/{tenant}/{id}` | GET/PATCH | policy show/update |
| `/api/v1/policy/{tenant}/{id}/rule` | POST | policy add-rule |
| `/api/v1/compliance/{tenant}/overview` | GET | compliance overview |
| `/api/v1/compliance/{tenant}/report` | GET | compliance report-tenant |
| `/api/v1/automation/{tenant}/job` | GET | automation list-jobs |
| `/api/v1/automation/{tenant}/execute` | POST | automation execute-job |
| `/api/v1/automation/{tenant}/fixtures` | GET | automation list-fixtures |

---

## Quick Reference Card

### Environment Variables
```bash
NETPICKER_BASE_URL    # API base URL
NETPICKER_TENANT      # Tenant name
NETPICKER_TOKEN       # API token
NETPICKER_TIMEOUT     # Request timeout (seconds)
NETPICKER_INSECURE    # Skip TLS verification
NETPICKER_VERBOSE     # Enable debug logging
NETPICKER_QUIET       # Suppress output
```

### Common Commands
```bash
netpicker health                    # Check connectivity
netpicker whoami                    # Show current user
netpicker devices list              # List devices
netpicker backups recent            # Recent backups
netpicker policy list               # List policies
netpicker compliance overview       # Compliance summary
netpicker automation list-jobs      # List jobs
```

### Development Commands
```bash
pip install -e ".[dev,mcp]"         # Install dev dependencies
pytest tests/                       # Run all tests
pytest tests/ -k "devices"          # Run specific tests
ruff check .                        # Lint code
black .                             # Format code
```

---

*End of Technical Documentation*
