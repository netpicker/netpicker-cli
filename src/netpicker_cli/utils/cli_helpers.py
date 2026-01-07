import functools
from contextlib import contextmanager
from typing import Callable, Any, Iterator, Tuple
import typer

from .config import load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError


def handle_api_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to standardize API error handling across commands.

    - Preserves original function signature via functools.wraps
    - Re-raises typer.Exit unchanged so command exit codes are respected
    - Catches ApiError and prints a clean message
    - Catches all other Exceptions and prints an unexpected error message
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            raise
        except ApiError as e:
            typer.echo(f"API error: {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            typer.echo(f"Unexpected error: {e}")
            raise typer.Exit(code=1)
    return wrapper


@contextmanager
def with_client() -> Iterator[Tuple[Any, ApiClient]]:
    """Context manager to load settings and provide an ApiClient.

    Usage:
        with with_client() as (s, cli):
            data = cli.get(f"/api/v1/foo/{s.tenant}").json()
    """
    s = load_settings()
    cli = ApiClient(s)
    try:
        yield s, cli
    finally:
        # ApiClient currently does not require explicit close
        pass
