# src/netpicker_cli/utils/logging.py
import logging
import sys
from typing import Optional
import typer


class TyperHandler(logging.Handler):
    """Custom logging handler that outputs to typer.echo() for CLI output."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # For CLI output, we just want the message, not the full log format
            # The formatter is still used for verbose mode
            if hasattr(record, '_cli_message'):
                # This is a direct CLI message, output as-is
                typer.echo(record.getMessage(), err=(record.levelno >= logging.WARNING))
            else:
                # This is a structured log message, use full formatting
                msg = self.format(record)
                typer.echo(msg, err=(record.levelno >= logging.WARNING))
        except Exception:
            self.handleError(record)


# Global configuration
_quiet_mode = False
_verbose_mode = False

def setup_logging(verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """
    Configure logging for the NetPicker CLI.

    Args:
        verbose: Enable debug logging
        quiet: Suppress info and warning messages

    Returns:
        Configured logger instance
    """
    global _quiet_mode, _verbose_mode
    _quiet_mode = quiet
    _verbose_mode = verbose

    logger = logging.getLogger('netpicker_cli')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler with typer integration
    handler = TyperHandler()

    if quiet:
        # Only show errors and critical messages
        handler.setLevel(logging.ERROR)
    elif verbose:
        # Show all messages including debug
        handler.setLevel(logging.DEBUG)
    else:
        # Show info and above (default)
        handler.setLevel(logging.INFO)

    # Create formatter - only use detailed format for verbose mode
    if verbose:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
    else:
        # For normal mode, don't show log level prefix
        formatter = logging.Formatter('%(message)s')

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger(name: str = 'netpicker_cli') -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(name)


# Global logger instance
logger = get_logger()


def log_api_call(method: str, url: str, **kwargs: any) -> None:
    """Log API call details at debug level."""
    logger.debug(f"API {method} {url}" + (f" with params: {kwargs}" if kwargs else ""))


def log_api_response(status_code: int, response_time: Optional[float] = None) -> None:
    """Log API response details at debug level."""
    msg = f"API response: {status_code}"
    if response_time:
        msg += f" ({response_time:.2f}s)"
    logger.debug(msg)


def log_error_with_context(error: Exception, context: str = "") -> None:
    """Log an error with additional context."""
    context_msg = f" [{context}]" if context else ""
    logger.error(f"{type(error).__name__}: {error}{context_msg}")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Full traceback:", exc_info=True)


def output_message(message: str, level: str = "info") -> None:
    """
    Output a message using the appropriate logging level.

    This is a convenience function for commands to use instead of typer.echo().
    The message will be displayed based on the current logging configuration.

    Args:
        message: The message to output
        level: The logging level ('debug', 'info', 'warning', 'error', 'critical')
    """
    # Check quiet mode first
    if _quiet_mode and level in ('info', 'warning'):
        return

    # Get current logging configuration from the global logger
    current_level = logger.getEffectiveLevel()
    level_value = getattr(logging, level.upper(), logging.INFO)

    # Only output if the message level is >= current level
    if level_value >= current_level:
        # For error/critical, output to stderr
        use_stderr = level_value >= logging.WARNING
        typer.echo(message, err=use_stderr)

        # Also log the message for debugging if verbose
        if _verbose_mode and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"CLI output [{level}]: {message}")