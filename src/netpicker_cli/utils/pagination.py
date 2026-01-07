from typing import Callable, Iterable, Iterator, Any

class Paginator:
    """Generic paginator utilities for sequential page fetching.

    The API shape varies across endpoints; this utility focuses on the common
    pattern where responses return either a list or a dict with an 'items' key.
    """

    @staticmethod
    def iterate(
        fetch_page: Callable[[int, int], Any],
        start_page: int = 1,
        size: int = 50,
        items_key: str = "items",
    ) -> Iterator[dict]:
        """Yield items by calling fetch_page(page, size) until exhausted.

        Stops when a page returns fewer items than `size` or when no items are found.
        """
        page = start_page
        while True:
            payload = fetch_page(page, size)
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict):
                items = payload.get(items_key, [])
            else:
                items = []

            if not items:
                break
            for it in items:
                yield it
            if len(items) < size:
                break
            page += 1

    @staticmethod
    def collect_all(
        fetch_page: Callable[[int, int], Any],
        start_page: int = 1,
        size: int = 50,
        items_key: str = "items",
    ) -> list[dict]:
        """Collect and return all items from iterate()."""
        return list(Paginator.iterate(fetch_page, start_page=start_page, size=size, items_key=items_key))
