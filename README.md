# NetPicker CLI

A lightweight CLI for the NetPicker API — built for pipelines and power users.

## What it does (current MVP)

- **Health & identity**
  - `netpicker health` — quick API status check
  - `netpicker whoami` — show authenticated user + tenant info

- **Devices**
  - `netpicker devices list [--tag TAG] [--json]`
  - `netpicker devices show --ip <IP/FQDN> [--json]`
  - `netpicker devices delete --ip <IP/FQDN> [--force]`

- **Backups**
  - `netpicker backups recent [--limit N] [--json]`
  - `netpicker backups list --ip <IP/FQDN> [--json]`
  - `netpicker backups fetch --ip <IP/FQDN> --id <CONFIG_ID> [-o DIR]`
  - `netpicker backups commands [--platform <name>] [--json]`
  - `netpicker backups search [--q TEXT] [--device IP] [--since TS] [--limit N] [--json]`
    - Falls back to client-side search when the server endpoint isn’t available
  - `netpicker backups diff [--ip <IP/FQDN>] [--id-a ID] [--id-b ID] [--context N] [--json]`
    - With `--ip` only: diffs the device’s **latest two** configs
    - With `--id-a/--id-b`: diffs those specific configs

> Output defaults to a pretty table. Add `--json` anywhere for machine-readable output.

---

## Install (dev)

```bash
python -m venv venv && source venv/bin/activate
pip install -e .

# If keyring backend complains on Linux:
pip install keyrings.alt
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
