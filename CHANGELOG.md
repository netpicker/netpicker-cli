# Changelog

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
