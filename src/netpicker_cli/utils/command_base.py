# src/netpicker_cli/utils/command_base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional
import typer


class BaseCommand(ABC):
    """
    Abstract base class for CLI commands to ensure consistent structure.

    Commands should implement:
    - validate_args(): Validate input arguments and options
    - execute(): Perform the main command logic and return data
    - format_output(): Format and display the results
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize command with any shared dependencies."""
        pass

    @abstractmethod
    def validate_args(self) -> None:
        """Validate command arguments and options."""
        pass

    @abstractmethod
    def execute(self) -> Any:
        """Execute the main command logic and return results."""
        pass

    @abstractmethod
    def format_output(self, result: Any) -> None:
        """Format and output the command results."""
        pass

    def run(self) -> None:
        """Run the complete command lifecycle."""
        self.validate_args()
        result = self.execute()
        self.format_output(result)


class TyperCommand(BaseCommand):
    """
    Base class for commands that use Typer for argument parsing.
    """

    def __init__(self, ctx: Optional[typer.Context] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.ctx = ctx