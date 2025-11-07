import time
import typer
from ..utils.config import load_settings
from ..api.client import ApiClient

def do_health():
    s = load_settings()
    client = ApiClient(s)
    t0 = time.perf_counter()
    data = client.get("/api/v1/status").json()
    ms = int((time.perf_counter() - t0) * 1000)

    # Don’t print Authorization header; show a concise summary instead
    api_base = data.get("api_base", s.base_url)
    tz = data.get("tz") or data.get("scheduler_timezone") or "UTC"
    typer.secho(f"OK ({ms} ms) — api_base={api_base} tz={tz}", fg=typer.colors.GREEN)
