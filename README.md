# Netpicker CLI

A comprehensive command-line interface for Netpicker API — empowering network engineers with powerful automation, compliance management, and device operations through both traditional CLI and AI-assisted workflows.

## ✨ Key Features

- **Device Management**: List, create, show, and delete network devices
- **Backup Operations**: Upload, fetch, search, and compare device configurations
- **Compliance Management**: Create policies, add rules, run compliance checks, and generate reports
- **Automation**: Execute jobs, manage queues, store and test automation scripts
- **MCP Server**: Integrate with AI assistants like Claude for natural language network management
- **Health Monitoring**: System status checks and user authentication verification

---

## 🚀 Installation & Setup

### Production Install

```bash
pip install netpicker-cli[mcp]
```

### Development Install

```bash
git clone <repository-url>
cd netpicker-cli
python -m venv venv && source venv/bin/activate
pip install -e ".[dev,mcp]"
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
export NETPICKER_VERBOSE=1           # Enable verbose debug logging
export NETPICKER_QUIET=1             # Suppress informational output
```

> Environment variables override config file values when set.

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
netpicker backups fetch <IP/FQDN> --id <CONFIG_ID> [--output DIR]    # Download specific config
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
netpicker policy show --name <NAME> [--format FORMAT]                      # Show policy details
netpicker policy create --name <NAME> [--description DESC]       # Create new policy
netpicker policy update --name <NAME> [--description DESC]       # Update policy
netpicker policy replace --name <NAME> --file <FILE>              # Replace policy from file
netpicker policy add-rule <POLICY> --name <NAME> [options...]     # Add rule to policy
netpicker policy remove-rule --name <POLICY> --rule-name <NAME>   # Remove rule from policy
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
netpicker policy show --name security-policy

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
netpicker policy remove-rule --name security-policy --rule-name rule_no_telnet

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
netpicker policy update --name security-policy --description "Updated security policy v2"
```

---

## ✅ Compliance Testing

Run compliance checks against device configurations and generate detailed reports.

### Commands

```bash
netpicker compliance overview [--format FORMAT]                           # Compliance overview
netpicker compliance report-tenant [--policy POLICY] [--format FORMAT]                      # Tenant-wide compliance report
netpicker compliance devices [--ip IP] [--policy POLICY] [--format FORMAT] # Device compliance status
netpicker compliance export [--format FORMAT] [-o FILE]          # Export compliance data
netpicker compliance status [--policy POLICY] [--format FORMAT]           # Compliance status summary
netpicker compliance failures [--limit N] [--format FORMAT]               # List compliance failures
netpicker compliance log [--policy POLICY] [--limit N] [--format FORMAT]  # Compliance check logs
netpicker compliance report-config --config-id <ID> [--format FORMAT]      # Config compliance report
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

# View compliance failures (most recent)
netpicker compliance failures --limit 20

# View compliance check logs
netpicker compliance log --limit 10

# View logs for a specific policy
netpicker compliance log --policy security-policy

# Export compliance data to file
netpicker compliance export --format json -o compliance_export.json

# Generate config-specific compliance report
netpicker compliance report-config --config-id config-123

# Export compliance status as JSON
netpicker compliance status 192.168.1.1 --format json
```

---

## ⚙️ Automation

Execute automation jobs, manage job queues, and monitor automation execution.

### Commands

```bash
netpicker automation list-fixtures [--format FORMAT]                       # List available fixtures
netpicker automation list-jobs [--pattern PATTERN] [--format FORMAT]                           # List automation jobs
netpicker automation store-job --name <NAME> --job-config <JSON>  # Store automation job
netpicker automation store-job-file --name <NAME> --file <FILE>    # Store job from file
netpicker automation show-job --name <NAME> [--format FORMAT]               # Show job details
netpicker automation delete-job --name <NAME> [--force]            # Delete automation job
netpicker automation test-job --name <NAME> [--fixtures JSON]      # Test automation job
netpicker automation execute-job --name <NAME> [options...]   # Execute automation job
netpicker automation logs [--job JOB] [--limit N] [--format FORMAT]         # View automation logs
netpicker automation show-log --id <LOG_ID> [--format FORMAT]               # Show specific log entry
netpicker automation list-queue [--format FORMAT]                           # List job queues
netpicker automation store-queue --name <NAME> --queue-config <JSON> # Store job queue
netpicker automation show-queue --name <NAME> [--format FORMAT]             # Show queue details
netpicker automation delete-queue --name <NAME> [--force]          # Delete job queue
netpicker automation review-queue --name <NAME> [--format FORMAT]           # Review queue status
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
netpicker automation show-job --name network-health-check

# Execute a health check job on all devices
netpicker automation execute-job --name network-health-check

# Execute a job on specific devices
netpicker automation execute-job --name backup-config --targets 192.168.1.1,192.168.1.2

# Execute a job on devices with specific tags
netpicker automation execute-job --name security-audit --tags production

# Execute a job with custom variables
netpicker automation execute-job --name custom-script --variables "timeout:30;retry:3"

# Test a job before execution
netpicker automation test-job --name network-health-check

# View automation logs (most recent)
netpicker automation logs --limit 10

# View logs for a specific job
netpicker automation logs --job network-health-check --limit 5

# Show details of a specific log entry
netpicker automation show-log --id log-123

# Store a new automation job from a file
netpicker automation store-job-file --name my-job --file job_config.py

# Delete an automation job
netpicker automation delete-job --name old-job

# List queued jobs
netpicker automation list-queue

# Review and approve a queued job
netpicker automation review-queue --name pending-job

# Export job list as JSON
netpicker automation list-jobs --format json > jobs.json
```

---

## 🤖 Model Context Protocol (MCP) Server

NetPicker CLI includes a built-in MCP server that enables AI assistants like Claude to interact with your network infrastructure through natural language conversations.

#### Quick MCP Setup

```bash
# Install with MCP support
pip install -e ".[mcp]"

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
- `automation_execute_job` - Execute automation jobs

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
pip install -e ".[dev,mcp]"
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
