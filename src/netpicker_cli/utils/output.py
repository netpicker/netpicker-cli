"""
Output formatting utilities for CLI commands.
Supports multiple output formats: table, json, csv, yaml.
"""

import json
import csv
import io
import sys
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from enum import Enum


class OutputFormat(str, Enum):
    """Supported output formats."""
    TABLE = "table"
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"


class OutputFormatter:
    """
    Unified output formatter supporting multiple formats.
    
    Usage:
        formatter = OutputFormatter(format="csv", output_file="output.csv")
        formatter.output(data, headers=["name", "ip", "platform"])
    """

    def __init__(
        self,
        format: Union[str, OutputFormat] = OutputFormat.TABLE,
        output_file: Optional[str] = None,
    ):
        """
        Initialize the output formatter.
        
        Args:
            format: Output format (table, json, csv, yaml)
            output_file: Optional file path to write output to
        """
        if isinstance(format, str):
            try:
                self.format = OutputFormat(format.lower())
            except ValueError:
                raise ValueError(
                    f"Unsupported format: {format}. "
                    f"Supported formats: {', '.join([f.value for f in OutputFormat])}"
                )
        else:
            self.format = format

        self.output_file = output_file

    def output(
        self,
        data: Union[Dict, List[Dict], List],
        headers: Optional[List[str]] = None,
    ) -> str:
        """
        Format and output data.
        
        Args:
            data: Data to format (dict, list of dicts, or list)
            headers: Column headers (required for table and csv formats)
            
        Returns:
            Formatted output as string
        """
        if self.format == OutputFormat.JSON:
            result = self._format_json(data)
        elif self.format == OutputFormat.CSV:
            result = self._format_csv(data, headers)
        elif self.format == OutputFormat.YAML:
            result = self._format_yaml(data)
        else:  # TABLE
            result = self._format_table(data, headers)

        # Write to file if specified
        if self.output_file:
            self._write_to_file(result)
        else:
            # Write to stdout
            print(result, end="")

        return result

    def output_json(self, data: Any) -> str:
        """Output data as JSON."""
        return self._format_json(data)

    def output_table(self, data: Union[List[Dict], List], headers: Optional[List[str]] = None) -> str:
        """Output data as table."""
        return self._format_table(data, headers)

    def output_csv(self, data: Union[List[Dict], List], headers: Optional[List[str]] = None) -> str:
        """Output data as CSV."""
        return self._format_csv(data, headers)

    def output_yaml(self, data: Any) -> str:
        """Output data as YAML."""
        return self._format_yaml(data)

    @staticmethod
    def _format_json(data: Any) -> str:
        """Format data as JSON."""
        return json.dumps(data, indent=2) + "\n"

    @staticmethod
    def _format_table(data: Union[List[Dict], List], headers: Optional[List[str]] = None) -> str:
        """Format data as table using tabulate."""
        try:
            from tabulate import tabulate
        except ImportError:
            raise ImportError("tabulate is required for table output. Install with: pip install tabulate")

        # Handle single dict
        if isinstance(data, dict):
            data = [data]

        # If data is list of dicts, convert to rows with headers
        if data and isinstance(data[0], dict):
            if not headers:
                headers = list(data[0].keys()) if data else []
            rows = [
                [item.get(h, "") for h in headers]
                for item in data
            ]
            return tabulate(rows, headers=headers) + "\n"
        else:
            # Data is already in list of lists format
            return tabulate(data, headers=headers) + "\n"

    @staticmethod
    def _format_csv(data: Union[List[Dict], List], headers: Optional[List[str]] = None) -> str:
        """Format data as CSV."""
        output = io.StringIO()

        # Handle single dict
        if isinstance(data, dict):
            data = [data]

        # If data is list of dicts
        if data and isinstance(data[0], dict):
            if not headers:
                headers = list(data[0].keys()) if data else []
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for row in data:
                writer.writerow({h: row.get(h, "") for h in headers})
        else:
            # Data is list of lists
            writer = csv.writer(output)
            if headers:
                writer.writerow(headers)
            writer.writerows(data)

        return output.getvalue()

    @staticmethod
    def _format_yaml(data: Any) -> str:
        """Format data as YAML."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required for YAML output. Install with: pip install PyYAML")

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _write_to_file(self, content: str) -> None:
        """Write content to a file."""
        if not self.output_file:
            return

        path = Path(self.output_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except IOError as e:
            raise IOError(f"Failed to write output to {self.output_file}: {e}")


def output_result(
    data: Any,
    format: str | OutputFormat = OutputFormat.TABLE,
    output_file: str | None = None,
    headers: list[str] | None = None,
) -> str:
    """Convenience function to output data using OutputFormatter.

    This avoids needing to instantiate OutputFormatter in simple cases and
    centralizes consistent behavior across commands.
    """
    formatter = OutputFormatter(format=format, output_file=output_file)
    return formatter.output(data, headers=headers)
