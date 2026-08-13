# Changelog

## 0.2.2 — Unreleased

### Fixed
- Corrected `automation execute-job` examples and help text to show the required target selection via `--devices` or `--tags`, and clarified that execution returns a confirmation message rather than a job ID
- Updated automation documentation to direct users to `netpicker automation logs --job-name <job-name>` for retrieving execution records, and to `netpicker automation logs --batch-id <batch-id>` for the individual execution IDs within a run
- Fixed the MCP `automation_execute_job` wrapper to forward job variables with `--variables` instead of the invalid `--fixtures` flag
- Fixed `backups recent` `--limit` parameter not working: API uses `size` parameter, not `limit`. Now respects `--limit` correctly (was always returning 50 items regardless of limit)
- Improved error message when attempting to create a duplicate device: now shows user-friendly message "Device with IP 'x.x.x.x' already exists in tenant 'TenantName'" instead of raw 409 Conflict API error with IntegrityError detail
- Fixed `automation logs` showing blank fields: the API now returns execution *batches* (`batch_id`, `job_name`, `initiator`, `status_counts`, `created`) rather than individual executions. The listing renders batch summaries, and the new `--batch-id` option drills into the individual executions within a batch
- Fixed `automation show-log` printing an empty entry: it called `/automation/{tenant}/logs/{id}` (a paginated batch listing) and parsed it as a single object. It now calls `/automation/{tenant}/log/{id}` and correctly reports a non-existent ID as an error
- Fixed `automation show-job` crashing with `AttributeError` when a job parameter has no type annotation (the API now returns `annotated: null`)
- Fixed log messages being written to stdout, which corrupted machine-readable output — `netpicker audit report --format json | jq` failed because informational lines preceded the JSON. All log output now goes to stderr, leaving stdout for command output only. This also fixes the MCP `audit_report` tool, which returned unparseable JSON to AI assistants
- Fixed the raw API error appearing alongside the friendly message on a duplicate device create; the underlying error is now logged at debug level (visible with `--verbose`)
- Uncaught API errors are now reported as a message on stderr with a non-zero exit status instead of an unhandled traceback
- Removed a duplicated `Simple:` line in `automation list-jobs` output

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
