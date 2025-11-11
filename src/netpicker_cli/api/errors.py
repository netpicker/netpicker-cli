# src/netpicker_cli/api/errors.py

class ApiError(Exception):
    """Base API error."""


class Unauthorized(ApiError):
    """401 Unauthorized."""


class TooManyRequests(ApiError):
    """429 Rate limited."""


class ServerError(ApiError):
    """5xx server-side error."""


class NotFound(ApiError):
    """404 resource not found."""
