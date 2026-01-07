# NetPicker CLI

A comprehensive command-line interface for NetPicker API — empowering network engineers with powerful automation, compliance management, and device operations through both traditional CLI and AI-assisted workflows.

## ✨ Key Features

- **Device Management**: List, create, show, and delete network devices
- **Backup Operations**: Upload, fetch, search, and compare device configurations
- **Compliance Management**: Create policies, add rules, run compliance checks, and generate reports
- **Automation**: Execute jobs, manage queues, store and test automation scripts
- **AI Assistance**: Natural language querying and AI-powered network management
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

NetPicker CLI provides flexible logging and output control:

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
netpicker devices list [--tag TAG] [--json] [--limit N] [--offset M] [--all] [--parallel P]
netpicker devices show --ip <IP/FQDN> [--json]
netpicker devices create --ip <IP> [--hostname HOSTNAME] [--platform PLATFORM] [--tags TAGS]
netpicker devices delete --ip <IP/FQDN> [--force]
```

### Examples

```bash
# List first 10 devices
netpicker devices list --limit 10

# Show device details in JSON
netpicker devices show --ip 192.168.1.1 --json

# Create a new device
netpicker devices create --ip 10.0.0.1 --hostname router01 --platform cisco_ios --tags "production,core"

# List devices by tag
netpicker devices list --tag production

# List all devices with parallel fetching (faster for large datasets)
netpicker devices list --all --parallel 5
```

---

## 💾 Backup Operations

Manage device configuration backups, compare versions, and search through backup history.

### Commands

```bash
netpicker backups recent [--limit N] [--json]                    # Recent backups across all devices
netpicker backups list --ip <IP/FQDN> [--page N] [--size N] [--all] [--parallel P] [--json]  # List backups for device
netpicker backups history --ip <IP/FQDN> [--limit N] [--json]    # Backup history for device
netpicker backups upload --ip <IP/FQDN> --config-file <FILE>     # Upload config backup
netpicker backups diff [--ip <IP/FQDN>] [--id-a ID] [--id-b ID] [--context N] [--json]
netpicker backups search [--q TEXT] [--device IP] [--since TS] [--limit N] [--json]
netpicker backups commands [--platform <name>] [--json]          # Show backup commands for platform
```

### Examples

```bash
# View recent backups
netpicker backups recent --limit 20

# Compare latest two configs for a device
netpicker backups diff --ip 192.168.1.1

# Search for configs containing specific text
netpicker backups search --q "interface GigabitEthernet" --device 192.168.1.1

# Upload a configuration backup
netpicker backups upload --ip 192.168.1.1 --config-file router-config.txt
```

---

## 📜 Compliance Policy Management

Create and manage compliance policies with customizable rules for network security and configuration standards.

### Commands

```bash
netpicker policy list [--json]                                    # List compliance policies
netpicker policy show --name <NAME> [--json]                      # Show policy details
netpicker policy create --name <NAME> [--description DESC]       # Create new policy
netpicker policy update --name <NAME> [--description DESC]       # Update policy
netpicker policy replace --name <NAME> --file <FILE>              # Replace policy from file
netpicker policy add-rule --name <POLICY> --rule-name <NAME> --rule-config <JSON>
netpicker policy remove-rule --name <POLICY> --rule-name <NAME>   # Remove rule from policy
netpicker policy test-rule --rule-config <JSON> --config-id <ID>  # Test rule against config
netpicker policy execute-rules --policy <NAME> --config-id <ID>   # Execute all policy rules
```

### Examples

```bash
# List all policies
netpicker policy list

# Create a security policy
netpicker policy create --name security-policy --description "Network security compliance"

# Add a compliance rule
netpicker policy add-rule --name security-policy --rule-name rule_no_telnet \
  --rule-config '{"type": "regex", "pattern": "transport input telnet", "negate": true}'

# Test a rule against a configuration
netpicker policy test-rule --rule-config '{"type": "regex", "pattern": "service password-encryption"}' --config-id 12345
```

---

## ✅ Compliance Testing

Run compliance checks against device configurations and generate detailed reports.

### Commands

```bash
netpicker compliance overview [--json]                           # Compliance overview
netpicker compliance report-tenant [--json]                      # Tenant-wide compliance report
netpicker compliance devices [--ip IP] [--policy POLICY] [--json] # Device compliance status
netpicker compliance export [--format FORMAT] [-o FILE]          # Export compliance data
netpicker compliance status [--policy POLICY] [--json]           # Compliance status summary
netpicker compliance failures [--limit N] [--json]               # List compliance failures
netpicker compliance log [--policy POLICY] [--limit N] [--json]  # Compliance check logs
netpicker compliance report-config --config-id <ID> [--json]      # Config compliance report
```

### Examples

```bash
# Check compliance overview
netpicker compliance overview

# Generate tenant compliance report
netpicker compliance report-tenant --json > compliance_report.json

# Check specific device compliance
netpicker compliance devices --ip 192.168.1.1

# View compliance failures
netpicker compliance failures --limit 20
```

---

## ⚙️ Automation

Execute automation jobs, manage job queues, and monitor automation execution.

### Commands

```bash
netpicker automation list-fixtures [--json]                       # List available fixtures
netpicker automation list-jobs [--json]                           # List automation jobs
netpicker automation store-job --name <NAME> --job-config <JSON>  # Store automation job
netpicker automation store-job-file --name <NAME> --file <FILE>    # Store job from file
netpicker automation show-job --name <NAME> [--json]               # Show job details
netpicker automation delete-job --name <NAME> [--force]            # Delete automation job
netpicker automation test-job --name <NAME> [--fixtures JSON]      # Test automation job
netpicker automation execute-job --name <NAME> [--fixtures JSON]   # Execute automation job
netpicker automation logs [--job JOB] [--limit N] [--json]         # View automation logs
netpicker automation show-log --id <LOG_ID> [--json]               # Show specific log entry
netpicker automation list-queue [--json]                           # List job queues
netpicker automation store-queue --name <NAME> --queue-config <JSON> # Store job queue
netpicker automation show-queue --name <NAME> [--json]             # Show queue details
netpicker automation delete-queue --name <NAME> [--force]          # Delete job queue
netpicker automation review-queue --name <NAME> [--json]           # Review queue status
```

### Examples

```bash
# List available jobs
netpicker automation list-jobs

# Execute a health check job
netpicker automation execute-job --name network-health-check

# View automation logs
netpicker automation logs --limit 10

# Store a new automation job
netpicker automation store-job-file --name my-job --file job_config.json
```

---

## 🤖 AI-Powered Features

NetPicker CLI includes AI assistance for natural language network management and intelligent querying.

### AI Command

```bash
netpicker ai query "Show me all devices"                          # Natural language queries
netpicker ai status                                               # AI service status
netpicker ai tools                                                # List available AI tools
netpicker ai chat                                                 # Interactive AI chat mode
```

### Model Context Protocol (MCP) Server

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

- Documentation: [NetPicker Docs](https://docs.netpicker.io)
- Issues: [GitHub Issues](https://github.com/netpicker/netpicker-cli/issues)
- Support: support@netpicker.io
