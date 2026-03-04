# Changelog

## 0.2.1 — 2026-03-04

### Fixed
- Fixed version string mismatch: `__version__` in `__init__.py` now matches package version

## 0.2.0 — Audit Report & Code Hardening

### New Feature: `netpicker audit report`
One command to audit your entire network. Gathers inventory, compliance, backup freshness, and policy status from the NetPicker API and produces a unified health report.

- **Parallel collection** — all four audit sections fetched concurrently via `asyncio.to_thread()`, with automatic fallback to sequential mode
- **Multiple output formats** — table (human), JSON (CI/CD), CSV (spreadsheets), YAML
- **Stale backup detection** — flags devices whose last config backup exceeds a configurable threshold (`--stale-days`, default 7)
- **Tag filtering** — scope the audit to a device subset with `--tag`
- **Plugin system** — `@register_section` decorator lets users add custom audit checks without forking
- **Graceful degradation** — if one section fails (e.g. compliance API is down), remaining sections still complete
- **CI-friendly exit codes** — exit 0 = all green, exit 2 = at least one section errored
- **File output** — `--output report.json` writes directly to file
- **MCP integration** — new `audit_report` tool registered in the MCP server for AI-assistant workflows

### Improvements
- **`SectionStatus` enum** — replaces bare status strings (`"ok"`, `"warning"`, etc.) with a proper `SectionStatus` enum for type safety
- **Input validation & sanitisation** — `--tag` is validated against a strict regex (alphanumeric, hyphens, underscores, dots, colons only) to prevent injection; `--stale-days` is range-checked (1–365); `--format` is validated before use
- **Comprehensive type hints** — every function signature, local variable, and return type in `audit.py` is annotated
- **Structured logging** — every collector logs entry/exit with timing (`time.monotonic()`), errors routed through `log_error_with_context()` for consistent formatting
- **Constants extracted** — magic numbers replaced with named `Final` constants (`_MAX_PAGE_SIZE`, `_MAX_STALE_DAYS`, `_MAX_DISPLAY_ITEMS`)
- **Resource safety** — `ApiClient.close()` now wrapped in `try/finally` blocks in both parallel and sequential paths to prevent connection leaks
- **Parallel error isolation** — exceptions in individual parallel collectors are caught and surfaced as error-status sections instead of crashing the entire audit

### Tests
- **40 unit tests** covering dataclasses, all 4 collectors, plugin registry, CLI integration (all formats), parallel vs sequential parity, and input validation (tag injection, boundary values)

### Documentation
- Added "Audit Report" section to README with commands, examples, sample output, and plugin guide
- Added `audit_report` MCP tool documentation

## 0.1.11
- Various bug fixes and dependency updates

## 0.1.10
- **Proxy disabled by default**: Netpicker is typically internal, so proxy is now off by default. Set `NETPICKER_USE_PROXY=1` to opt in
- **CIDR-aware `no_proxy` support**: When proxy is enabled, CIDR notation like `10.0.0.0/8` in `no_proxy` is correctly honoured (httpx ignores these natively)
- **Custom CA bundle**: New `NETPICKER_CA_BUNDLE` env var (or `ca_bundle` in config) to point to an internal CA PEM file — avoids needing `NETPICKER_INSECURE=1`
- **Python 3.10 compatibility**: Lowered minimum Python version from 3.11 to 3.10
- Fixed conftest.py guarding optional `ai.router` import

## 0.1.0 — Initial public MVP
- `health`, `devices list|show`
- `backups recent|list|fetch|commands|search (fallback)`
- keyring-based auth, XDG config
