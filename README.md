# Netpicker CLI

A comprehensive command-line interface for Netpicker API — empowering network engineers with powerful automation, compliance management, and device operations through both traditional CLI and AI-assisted workflows.

## ✨ Key Features

- **Device Management**: List, create, show, and delete network devices
- **Backup Operations**: Upload, download, search, and compare device configurations
- **Compliance Management**: Create policies, add rules, run compliance checks, and generate reports
- **Automation**: Execute jobs, manage queues, store and test automation scripts
- **Audit Report**: One-command network health report — inventory, compliance, backup freshness, and policy status
- **MCP Server**: Integrate with AI assistants like Claude for natural language network management
- **Health Monitoring**: System status checks and user authentication verification

---

## 🚀 Installation & Setup

### Production Install

```bash
pip install netpicker-cli
```

### Development Install

```bash
git clone <repository-url>
cd netpicker-cli
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

> **Linux Keyring Note**: If you encounter keyring issues on Linux, install the alternative backend:
> ```bash
> pip install keyrings.alt
> export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
> ```

### Configuration & Authentication

#### Recommended: Interactive Login

```bash
netpicker auth login \
  --base-url https://YOUR-NETPICKER-URL \
  --tenant YOUR_TENANT \
  --token YOUR_API_TOKEN
```

This securely stores your token in the OS keyring and saves URL/tenant to `~/.config/netpicker/config.json`.

> **Note**: The config file is only created when using `netpicker auth login`. If you prefer environment variables, the config file won't be created.

#### Alternative: Environment Variables

**Unix/macOS:**
```bash
export NETPICKER_BASE_URL="https://YOUR-NETPICKER-URL"
export NETPICKER_TENANT="YOUR_TENANT"
export NETPICKER_TOKEN="YOUR_API_TOKEN"
```

**Windows PowerShell:**
```powershell
$env:NETPICKER_BASE_URL = "https://YOUR-NETPICKER-URL"
$env:NETPICKER_TENANT   = "YOUR_TENANT"
$env:NETPICKER_TOKEN    = "YOUR_API_TOKEN"
```

#### Optional Settings

```bash
export NETPICKER_TIMEOUT=30          # Request timeout in seconds
export NETPICKER_INSECURE=1          # Skip TLS verification (use with caution)
export NETPICKER_CA_BUNDLE=/path/to/ca.pem  # Custom CA certificate bundle
export NETPICKER_USE_PROXY=1         # Enable proxy (disabled by default)
export NETPICKER_VERBOSE=1           # Enable verbose debug logging
export NETPICKER_QUIET=1             # Suppress informational output
```

> Environment variables override config file values when set.

#### Proxy & TLS Configuration

Since Netpicker is typically an internal service, **proxy is disabled by default**.
All requests go directly to the Netpicker host without consulting `HTTP_PROXY` / `HTTPS_PROXY`.

If you need to route traffic through a proxy, opt in explicitly:

```bash
export NETPICKER_USE_PROXY=1
```

When proxy is enabled, netpicker-cli provides enhanced `no_proxy` support
that correctly handles **CIDR notation** (e.g. `10.0.0.0/8`), which standard httpx ignores:

```bash
export NETPICKER_USE_PROXY=1
export no_proxy="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
```

For internal servers with self-signed or private CA certificates, use `NETPICKER_CA_BUNDLE`
instead of disabling TLS verification:

```bash
# Preferred: point to your internal CA certificate
export NETPICKER_CA_BUNDLE=/etc/ssl/certs/internal-ca.pem

# Not recommended: disables all TLS verification
export NETPICKER_INSECURE=1
```

**TLS verification priority**: `NETPICKER_INSECURE=1` → skip verification, `NETPICKER_CA_BUNDLE` → custom CA, otherwise → system CA store.

### Logging & Output Control

Netpicker CLI provides flexible logging and output control:

```bash
# Normal output (default)
netpicker devices list

# Verbose mode - shows debug information and API calls
netpicker --verbose devices list

# Quiet mode - suppresses informational messages, shows only errors
netpicker --quiet devices list

# Environment variables for persistent settings
export NETPICKER_VERBOSE=1    # Always enable verbose mode
export NETPICKER_QUIET=1      # Always enable quiet mode
```

**Logging Levels:**
- **Normal**: Clean CLI output without log prefixes
- **Verbose**: Detailed debug information including API calls, response times, and full stack traces
- **Quiet**: Only error and critical messages are displayed

### Quick Health Check

```bash
netpicker health
netpicker whoami --json | jq .
```

---

## 📋 Device Management

NetPicker CLI provides comprehensive device inventory management capabilities.

### Commands

```bash
netpicker devices list [--tag TAG] [--format FORMAT] [--limit N] [--offset M] [--all] [--parallel P]
netpicker devices show <IP/FQDN> [--format FORMAT]
netpicker devices create <IP> [--name HOSTNAME] [--platform PLATFORM] [--port PORT] [--vault VAULT] [--tags TAGS] [--format FORMAT]
netpicker devices delete <IP/FQDN> [--force]
```

### Examples

```bash
# List first 10 devices in table format
netpicker devices list --limit 10

# List devices with JSON output
netpicker devices list --format json

# Show device details in JSON
netpicker devices show 192.168.1.1 --format json

# Create a new device with tags
netpicker devices create 10.0.0.1 --name router01 --platform cisco_ios --vault default --tags "production,core"

# Create a device with custom vault
netpicker devices create 10.0.0.2 --name switch01 --platform cisco_nxos --vault my-vault --port 22

# List devices filtered by tag
netpicker devices list --tag production

# List all devices with parallel fetching (faster for large datasets)
netpicker devices list --all --parallel 5

# Delete a device (with confirmation prompt)
netpicker devices delete 192.168.1.1

# Delete a device without confirmation
netpicker devices delete 192.168.1.1 --force

# Export device list to CSV
netpicker devices list --format csv --output devices.csv

# Export device list to YAML
netpicker devices list --format yaml > devices.yaml
```

---

## 💾 Backup Operations

Manage device configuration backups, compare versions, and search through backup history.

### Commands

```bash
netpicker backups recent [--limit N] [--format FORMAT]                    # Recent backups across all devices
netpicker backups list <IP/FQDN> [--page N] [--size N] [--all] [--parallel P] [--format FORMAT]  # List backups for device
netpicker backups history <IP/FQDN> [--limit N] [--format FORMAT]    # Backup history for device
netpicker backups upload <IP/FQDN> --file <FILE>     # Upload config backup
netpicker backups diff <IP/FQDN> [--id-a ID] [--id-b ID] [--context N] [--format FORMAT]
netpicker backups download <IP/FQDN> --id <CONFIG_ID> [--output DIR]    # Download specific config
netpicker backups search [--q TEXT] [--device IP] [--since TS] [--limit N] [--format FORMAT]
netpicker backups commands [--platform <name>] [--format FORMAT]          # Show backup commands for platform
```

### Examples

```bash
# View recent backups across all devices
netpicker backups recent --limit 20

# List backups for a specific device
netpicker backups list 192.168.1.1

# List all backups for a device with parallel fetching
netpicker backups list 192.168.1.1 --all --parallel 5

# Compare latest two configs for a device
netpicker backups diff 192.168.1.1

# Compare specific config versions
netpicker backups diff 192.168.1.1 --id-a config-id-1 --id-b config-id-2

# Search for configs containing specific text
netpicker backups search --q "interface GigabitEthernet" --device 192.168.1.1

# Upload a configuration backup
netpicker backups upload 192.168.1.1 --file router-config.txt

# View backup history for a device
netpicker backups history 192.168.1.1 --limit 10

# Show backup command templates for a platform
netpicker backups commands --platform cisco_ios

# Export backup as JSON
netpicker backups recent --format json > recent_backups.json
```

---

## 📜 Compliance Policy Management

Create and manage compliance policies with customizable rules for network security and configuration standards.

### Commands

```bash
netpicker policy list [--format FORMAT]                                    # List compliance policies
netpicker policy show <POLICY_ID> [--format FORMAT]                       # Show policy details
netpicker policy create --name <NAME> [--description DESC]       # Create new policy
netpicker policy update <POLICY_ID> [--name NAME] [--description DESC]    # Update policy
netpicker policy replace <POLICY_ID> --name <NAME> [--description DESC]   # Replace policy
netpicker policy add-rule <POLICY> --name <NAME> [options...]     # Add rule to policy
netpicker policy remove-rule <POLICY_ID> <RULE_NAME>                      # Remove rule from policy
netpicker policy test-rule <POLICY> --name <NAME> --ip <IP> --config <CONFIG> [options...]  # Test rule against config
netpicker policy execute-rules [--devices <DEVICES>] [--policies <POLICIES>] [--rules <RULES>] [--tags <TAGS>]  # Execute all policy rules
```

### Examples

```bash
# List all policies
netpicker policy list

# List policies in JSON format
netpicker policy list --format json

# Show policy details
netpicker policy show security-policy

# Create a security policy
netpicker policy create --name security-policy --description "Network security compliance"

# Add a compliance rule to check for telnet (must NOT be present)
netpicker policy add-rule security-policy --name rule_no_telnet \
  --commands '{"show running-config": ["interface *", "line vty *"]}' \
  --simplified-text "transport input telnet" --simplified-invert

# Add a rule requiring SSH on VTY lines
netpicker policy add-rule security-policy --name rule_ssh_required \
  --commands '{"show running-config": ["line vty *"]}' \
  --simplified-text "transport input ssh"

# Add a regex-based rule for password complexity
netpicker policy add-rule security-policy --name rule_password_complexity \
  --commands '{"show running-config": ["enable secret"]}' \
  --simplified-text "enable secret [0-9]" --simplified-regex

# Remove a rule from a policy
netpicker policy remove-rule security-policy rule_no_telnet

# Test a rule against a configuration
netpicker policy test-rule security-policy --name rule_no_telnet \
  --ip 192.168.1.1 --config "interface GigabitEthernet0/1
line vty 0 4
 transport input ssh"

# Execute compliance rules against all devices
netpicker policy execute-rules

# Execute rules against specific devices
netpicker policy execute-rules --devices 192.168.1.1,192.168.1.2

# Execute rules against devices with specific tags
netpicker policy execute-rules --tags production,core

# Update a policy description
netpicker policy update security-policy --description "Updated security policy v2"
```

---

## ✅ Compliance Testing

Run compliance checks against device configurations and generate detailed reports.

### Commands

```bash
netpicker compliance overview [--format FORMAT]                           # Compliance overview
netpicker compliance report-tenant [--policy POLICY] [--format FORMAT]                      # Tenant-wide compliance report
netpicker compliance devices [--ipaddress IP] [--policy POLICY] [--format FORMAT] # Device compliance status
netpicker compliance export [--format FORMAT] [-o FILE]          # Export compliance data
netpicker compliance status <IP/FQDN> [--format FORMAT]                      # Device compliance status
netpicker compliance failures [--format FORMAT]                               # List compliance failures
netpicker compliance log <CONFIG_ID> [--body BODY] [--format FORMAT]          # Log compliance for config
netpicker compliance report-config <CONFIG_ID> [--body BODY] [--format FORMAT] # Report compliance for config
```

### Examples

```bash
# Check compliance overview
netpicker compliance overview

# Check compliance status for a specific device
netpicker compliance status 192.168.1.1

# Generate tenant-wide compliance report
netpicker compliance report-tenant --format json > compliance_report.json

# Generate report for a specific policy
netpicker compliance report-tenant --policy security-policy

# List devices with compliance information
netpicker compliance devices

# List devices with specific policy compliance
netpicker compliance devices --policy security-policy

# Check compliance for a specific device
netpicker compliance devices --ipaddress 192.168.1.1

# View compliance failures
netpicker compliance failures

# Log compliance for a specific config
netpicker compliance log <config-id> --body '{"outcome": "SUCCESS"}'

# Export compliance data to file
netpicker compliance export --format json -o compliance_export.json

# Report compliance for a specific config
netpicker compliance report-config <config-id> --body @report.json

# Check compliance status for a specific device
netpicker compliance status 192.168.1.1 --format json
```

---

## ⚙️ Automation

Execute automation jobs, manage job queues, and monitor automation execution.

### Commands

```bash
netpicker automation list-fixtures [--format FORMAT]                       # List available fixtures
netpicker automation list-jobs [--pattern PATTERN] [--format FORMAT]                           # List automation jobs
netpicker automation store-job --name <NAME> --sources <SOURCES>            # Store automation job
netpicker automation store-job-file --name <NAME> --file <FILE>    # Store job from file
netpicker automation show-job <NAME> [--format FORMAT]                      # Show job details
netpicker automation delete-job <NAME> [--format FORMAT]                    # Delete automation job
netpicker automation test-job --name <NAME> [--variables VARS]              # Test automation job
netpicker automation execute-job --name <NAME> [--devices DEVICES|--tags TAGS] [--variables VARS]   # Execute automation job
netpicker automation logs [--job-name JOB] [--batch-id ID] [--status STATUS] [--page N] [--size N] [--format FORMAT]  # View log batches, or executions within a batch
netpicker automation show-log <LOG_ID> [--format FORMAT]                    # Show specific log entry
netpicker automation list-queue [--format FORMAT]                           # List job queues
netpicker automation store-queue --name <NAME> --sources <SOURCES>          # Store job queue
netpicker automation show-queue <QUEUE_ID> [--format FORMAT]                # Show queue details
netpicker automation delete-queue <QUEUE_ID> [--format FORMAT]              # Delete job queue
netpicker automation review-queue <QUEUE_ID> --approved <true|false>        # Review queue (approve/reject)
```

### Examples

```bash
# List available fixtures (predefined variables)
netpicker automation list-fixtures

# List available jobs
netpicker automation list-jobs

# List jobs matching a pattern
netpicker automation list-jobs --pattern health

# Show details of a specific job
netpicker automation show-job my-backup-job

# Execute a job on a specific device
netpicker automation execute-job --name network-health-check --devices 192.168.1.10

# Execute a job on specific devices
netpicker automation execute-job --name backup-config --devices 192.168.1.1,192.168.1.2

# Execute a job on devices with specific tags
netpicker automation execute-job --name security-audit --tags production

# Execute a job with custom variables
netpicker automation execute-job --name custom-script --devices 192.168.1.20 --variables "timeout:30;retry:3"

# Test a job before execution
netpicker automation test-job --name network-health-check --variables "threshold:80"

# View automation log batches (first 50, page 1)
# Each entry is one execution run, with a per-status result count
netpicker automation logs

# View logs with custom page size
netpicker automation logs --size 10 --page 1

# View log batches for a specific job
netpicker automation logs --job-name network-health-check --status SUCCESS

# Drill into a batch to see the individual per-device executions
netpicker automation logs --batch-id f1961371-b9c1-4987-a65d-8c9e29dee03f

# Show details of a specific log entry (IDs come from --batch-id above)
netpicker automation show-log 123456789012345678

# Note: execute-job returns a confirmation message, not a job ID
# Use logs to retrieve execution records and IDs for a job
netpicker automation logs --job-name network-health-check

# Store a new automation job from a file
netpicker automation store-job-file --name my-job --file job_config.py

# Delete an automation job
netpicker automation delete-job old-job

# List queued jobs
netpicker automation list-queue

# Review and approve a queued job
netpicker automation review-queue 987654321098765432 --approved true

# Export job list as JSON
netpicker automation list-jobs --format json > jobs.json
```

---

## 📊 Audit Report

Generate a full network health report with a single command — combining device inventory, compliance posture, backup freshness, and policy status. Ideal for morning stand-ups, weekly reviews, and management reports.

### Command

```bash
netpicker audit report [--tag TAG] [--stale-days N] [--parallel/--no-parallel] [--format FORMAT] [--output FILE]
```

### Examples

```bash
# Quick health check (table output)
netpicker audit report

# Filter to production devices only
netpicker audit report --tag production

# Machine-readable JSON for CI/CD pipelines
netpicker audit report --format json

# Save Monday morning report to file
netpicker audit report --format json --output monday-report.json

# Stricter backup freshness (flag anything older than 3 days)
netpicker audit report --stale-days 3

# CSV export for spreadsheet analysis
netpicker audit report --format csv --output audit.csv

# Disable parallel fetching (useful for debugging)
netpicker audit report --no-parallel
```

### Sample Output

```
  NetPicker Audit Report — tenant: production
  Tag filter: production
  Generated: 2026-02-28T09:00:00+00:00
  Overall status: [WARN]

  [OK] INVENTORY
      total_devices: 47
      platforms:
        cisco_ios: 28
        arista_eos: 12
        fortios: 7

  [WARN] COMPLIANCE
      devices:
        passed: 42
        failed: 5
      policies:
        enabled: 3
        disabled: 1

  [WARN] BACKUPS
      total_recent: 47
      fresh: 44
      stale: 2
      errored: 1
      stale_threshold_days: 7
      Stale devices (>7d):
        10.0.1.5 (edge-rtr-05) — last backup 12d ago
        10.0.2.3 (branch-sw-03) — last backup 9d ago

  [OK] POLICIES
      total: 4
      enabled: 3
      disabled: 1

  Tip: use --format json for machine-readable output
```

### Plugin Support

Custom audit sections can be registered for extensibility:

```python
from netpicker_cli.commands.audit import register_section, AuditSection

@register_section
def check_firmware(cli, settings, options):
    # Your custom logic here
    return AuditSection(name="firmware", summary={"outdated": 2}, status="warning")
```

See [examples/audit_report.py](examples/audit_report.py) for a complete example.

---

## 🤖 Model Context Protocol (MCP) Server

NetPicker CLI includes a built-in MCP server that enables AI assistants like Claude to interact with your network infrastructure through natural language conversations.

#### Quick MCP Setup

```bash
# Install netpicker-cli
pip install netpicker-cli

# Configure for Claude Desktop
# Add to your claude_desktop_config.json:
{
  "mcpServers": {
    "netpicker": {
      "command": "netpicker-mcp",
      "env": {
        "NETPICKER_BASE_URL": "https://your-netpicker-instance.com",
        "NETPICKER_TENANT": "your-tenant",
        "NETPICKER_TOKEN": "your-api-token"
      }
    }
  }
}
```

#### MCP Tools Available

**Device Management:**
- `devices_list` - List network devices with filtering options
- `devices_show` - Display detailed device information
- `devices_create` - Create new network devices
- `devices_delete` - Remove devices from inventory

**Backup Management:**
- `backups_upload` - Upload device configurations
- `backups_history` - View backup history for devices
- `backups_diff` - Compare configuration versions

**Compliance & Policy:**
- `policy_list` - List compliance policies
- `policy_create` - Create new compliance policies
- `policy_add_rule` - Add rules to policies
- `policy_test_rule` - Test rules against configurations

**Automation:**
- `automation_list_jobs` - List available automation jobs
- `automation_execute_job` - Execute automation jobs on target devices or tags; use logs to retrieve execution IDs

#### AI Assistant Examples

Once configured, you can ask Claude things like:
- *"Show me the first 10 devices"*
- *"Create a backup of router 192.168.1.1"*
- *"Check if this config complies with our security policy"*
- *"Execute the network health check automation job"*
- *"List all devices that failed compliance in the last 24 hours"*

---

## 🐛 Troubleshooting

### Common Issues

**"No token found"**
- Run `netpicker auth login` or set `NETPICKER_TOKEN` environment variable

**403 Forbidden**
- Verify tenant name matches your API token's scope
- Ensure token has `access:api` permissions

**Connection timeouts**
- Check `NETPICKER_BASE_URL` is correct
- Adjust `NETPICKER_TIMEOUT` if needed (default: 30s)

**Large result sets**
- API responses are paginated by default
- Use `--all` flag to fetch all results (may take time)
- Or use `--limit` and `--offset` for manual pagination

**Keyring issues on Linux**
- Install alternative keyring: `pip install keyrings.alt`
- Set: `export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring`

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `pytest`
6. Submit a pull request

### Development Setup

```bash
git clone <repository-url>
cd netpicker-cli
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest  # Run tests
ruff check .  # Lint code
black .      # Format code
```

---

## 📄 License

MIT License - see LICENSE file for details.

## 📞 Support

- Documentation: [GitHub Repository](https://github.com/netpicker/netpicker-cli)
- Issues: [GitHub Issues](https://github.com/netpicker/netpicker-cli/issues)
- Support: support@netpicker.io
