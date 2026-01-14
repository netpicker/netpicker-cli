# Netpicker MCP Server Configuration

This directory contains the Model Context Protocol (MCP) server for Netpicker CLI.

## Installation

Install Netpicker CLI with MCP support:

```bash
pip install netpicker-cli
```

## Usage

The MCP server can be used with AI assistants that support MCP, such as Claude Desktop.

### Configuration for Claude Desktop

Add the following to your Claude Desktop configuration file:

```json
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

## Available Tools

The MCP server exposes the following tools:

### Device Management
- `devices_list` - List network devices
- `devices_show` - Show device details
- `devices_create` - Create a new device
- `devices_delete` - Delete a device

### Backup Management
- `backups_upload` - Upload device configuration
- `backups_history` - Show backup history
- `backups_diff` - Compare configurations

### Compliance Management
- `policy_list` - List compliance policies
- `policy_create` - Create compliance policy
- `policy_add_rule` - Add compliance rule
- `policy_test_rule` - Test compliance rule

### Automation
- `automation_list_jobs` - List automation jobs
- `automation_execute_job` - Execute automation job

### Health Monitoring
- `health_check` - Check system health

## Environment Variables

The MCP server requires the following environment variables to be set:

- `NETPICKER_BASE_URL` - Netpicker API base URL
- `NETPICKER_TENANT` - Tenant identifier
- `NETPICKER_TOKEN` - API authentication token

## Example Usage with Claude

Once configured, you can ask Claude to:

- "Show me all network devices"
- "Create a new Cisco router device"
- "Check the backup history for device 192.168.1.1"
- "Create a compliance policy for security rules"
- "Test if this config complies with our security policy"
- "Execute the network backup automation job"

## Development

To run the MCP server directly for testing:

```bash
python -m netpicker_cli.mcp.server
```

The server communicates over stdio using the MCP protocol.