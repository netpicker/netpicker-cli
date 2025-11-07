# NetPicker CLI

A lightweight CLI wrapper for the NetPicker API — perfect for pipelines and power users.

## Features (MVP)
- `netpicker health` – ping the API
- `netpicker devices list|show` – inventory
- `netpicker backups recent|list|fetch|commands|search` – backup workflows
  - `search` falls back to client-side search when server endpoint isn’t available

> Auth is token-based and stored securely via `keyring`. Config lives in `~/.config/netpicker/config.json`.

## Install (dev)
```bash
python -m venv venv && source venv/bin/activate
pip install -e .
# if keyring backend complains on Linux:
pip install keyrings.alt
export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring
