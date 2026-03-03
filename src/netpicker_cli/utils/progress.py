"""
Progress feedback utilities for long-running CLI operations.

Uses ``tqdm`` when available for rich progress bars, otherwise falls back
to simple ``typer.echo`` messages.  All public helpers are safe to call
regardless of whether tqdm is installed — network engineers who ``pip
install tqdm`` get a nicer experience, everyone else still works.

Usage::

    from netpicker_cli.utils.progress import progress_bar, page_progress

    # Wrap an iterable
    for item in progress_bar(items, desc="Processing"):
        ...

    # Page-fetching callback
    with page_progress("Fetching devices") as tick:
        while has_more:
            items = fetch_page(page)
            tick(len(items))
            page += 1
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, Optional, TypeVar

import typer

T = TypeVar("T")

_HAS_TQDM: bool
try:
    from tqdm import tqdm as _tqdm  # type: ignore[import-untyped]
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False


def progress_bar(
    iterable: Iterable[T],
    *,
    desc: str = "",
    total: Optional[int] = None,
    disable: bool = False,
) -> Iterable[T]:
    """Wrap *iterable* in a progress bar if ``tqdm`` is available.

    When tqdm is missing or *disable* is True, the iterable is returned
    unmodified — zero overhead.
    """
    if disable or not _HAS_TQDM:
        return iterable
    return _tqdm(iterable, desc=desc, total=total, file=sys.stderr, leave=False)  # type: ignore[return-value]


class _PageCounter:
    """Lightweight tick counter for paged fetches."""

    __slots__ = ("_desc", "_count", "_pages", "_quiet")

    def __init__(self, desc: str, quiet: bool = False) -> None:
        self._desc = desc
        self._count: int = 0
        self._pages: int = 0
        self._quiet = quiet

    def __call__(self, n: int = 0) -> None:
        """Tick the counter. *n* is the number of items received in this page."""
        self._pages += 1
        self._count += n
        if not self._quiet:
            # Overwrite the line in-place
            typer.echo(
                f"\r  {self._desc}: {self._count} items ({self._pages} pages)…",
                nl=False,
                err=True,
            )

    @property
    def count(self) -> int:
        return self._count

    @property
    def pages(self) -> int:
        return self._pages


@contextmanager
def page_progress(
    desc: str = "Fetching",
    *,
    quiet: bool = False,
) -> Iterator[_PageCounter]:
    """Context manager that yields a tick callback for paged fetches.

    Example::

        with page_progress("Fetching devices") as tick:
            while has_more:
                items = fetch(page)
                tick(len(items))
                page += 1
    """
    counter = _PageCounter(desc, quiet=quiet)
    try:
        yield counter
    finally:
        if not quiet and counter.pages > 0:
            # Clear the progress line and print final count
            typer.echo(
                f"\r  {desc}: {counter.count} items ({counter.pages} pages) ✓  ",
                err=True,
            )
