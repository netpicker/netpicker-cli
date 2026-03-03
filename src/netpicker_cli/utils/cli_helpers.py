import functools
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Tuple, TypeVar

import typer

from .config import Settings, load_settings
from ..api.client import ApiClient
from ..api.errors import ApiError

F = TypeVar("F", bound=Callable[..., Any])


def handle_api_errors(func: F) -> F:
    """Decorator to standardize API error handling across commands.

    - Preserves original function signature via functools.wraps
    - Re-raises typer.Exit unchanged so command exit codes are respected
    - Catches ApiError and prints a clean message
    - Catches all other Exceptions and prints an unexpected error message
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
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
    return wrapper  # type: ignore[return-value]


@contextmanager
def with_client() -> Iterator[Tuple[Settings, ApiClient]]:
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
        cli.close()
