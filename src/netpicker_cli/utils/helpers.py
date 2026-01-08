"""
Centralized helper functions for common operations across netpicker-cli.

This module consolidates duplicate logic for:
- API response normalization
- Tag filtering and manipulation  
- String operations
- Common regex patterns
"""

from __future__ import annotations
from typing import Any, List, Dict
import re


# ============================================================================
# API Response Normalization
# ============================================================================

def extract_items_from_response(data: Any) -> List[dict]:
    """
    Extract items list from API response.
    
    Handles both:
    - Direct list responses: [{"id": 1}, {"id": 2}]
    - Paginated dict responses: {"items": [...], "total": 100}
    
    Args:
        data: API response data (list, dict, or other)
        
    Returns:
        List of items. Empty list if data is neither list nor dict.
        
    Examples:
        >>> extract_items_from_response([{"id": 1}, {"id": 2}])
        [{"id": 1}, {"id": 2}]
        
        >>> extract_items_from_response({"items": [{"id": 1}], "total": 1})
        [{"id": 1}]
        
        >>> extract_items_from_response(None)
        []
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items", [])
    return []


# ============================================================================
# Tag Operations
# ============================================================================

def normalize_tags_to_list(tags: Any) -> List[str]:
    """
    Normalize tag data to a list of strings.
    
    Handles multiple tag formats:
    - Already a list: ["prod", "core"]
    - Comma-separated string: "prod,core"
    - Single string: "prod"
    - None/empty
    
    Args:
        tags: Tag data in various formats
        
    Returns:
        List of normalized tag strings (lowercased, stripped)
        
    Examples:
        >>> normalize_tags_to_list(["Prod", "Core"])
        ["prod", "core"]
        
        >>> normalize_tags_to_list("prod, core, edge")
        ["prod", "core", "edge"]
        
        >>> normalize_tags_to_list(None)
        []
    """
    if not tags:
        return []
    
    if isinstance(tags, list):
        return [str(t).strip().lower() for t in tags if t]
    
    if isinstance(tags, str):
        return [t.strip().lower() for t in tags.split(",") if t.strip()]
    
    return []


def filter_items_by_tag(items: List[dict], tag: str, tag_field: str = "tags") -> List[dict]:
    """
    Filter items by tag (case-insensitive).
    
    Supports various tag formats in items:
    - List: {"tags": ["prod", "core"]}
    - Comma-separated: {"tags": "prod,core"}
    - Single string: {"tags": "prod"}
    
    Args:
        items: List of dictionaries to filter
        tag: Tag to filter by (case-insensitive)
        tag_field: Field name containing tags (default: "tags")
        
    Returns:
        Filtered list of items that have the specified tag
        
    Examples:
        >>> items = [
        ...     {"name": "r1", "tags": ["prod", "core"]},
        ...     {"name": "r2", "tags": "edge,backup"},
        ...     {"name": "r3", "tags": "prod"}
        ... ]
        >>> filter_items_by_tag(items, "prod")
        [{"name": "r1", "tags": ["prod", "core"]}, {"name": "r3", "tags": "prod"}]
    """
    target_tag = tag.lower()
    filtered = []
    
    for item in items:
        item_tags = normalize_tags_to_list(item.get(tag_field))
        if target_tag in item_tags:
            filtered.append(item)
    
    return filtered


def format_tags_for_display(tags: Any) -> str:
    """
    Format tags for display output (comma-separated string).
    
    Args:
        tags: Tag data in various formats
        
    Returns:
        Comma-separated string, or empty string if no tags
        
    Examples:
        >>> format_tags_for_display(["prod", "core"])
        "prod,core"
        
        >>> format_tags_for_display("prod,core")
        "prod,core"
        
        >>> format_tags_for_display(None)
        ""
    """
    if isinstance(tags, list):
        return ",".join(str(t) for t in tags if t)
    if isinstance(tags, str):
        return tags
    return ""


# ============================================================================
# Regex Pattern Helpers
# ============================================================================

# Pre-compiled regex patterns for common validations
IP_ADDRESS_PATTERN = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')
ALPHANUMERIC_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
LABEL_PATTERN = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def extract_ip_from_text(text: str) -> str | None:
    """
    Extract the first IP address from a text string.
    
    Args:
        text: Text potentially containing IP address
        
    Returns:
        First IP address found, or None
        
    Examples:
        >>> extract_ip_from_text("show config for 192.168.1.1")
        "192.168.1.1"
        
        >>> extract_ip_from_text("list devices")
        None
    """
    match = IP_ADDRESS_PATTERN.search(text)
    return match.group(1) if match else None


def extract_number_from_text(text: str, patterns: List[str]) -> int | None:
    """
    Extract a number from text using multiple regex patterns.
    
    Args:
        text: Text to search
        patterns: List of regex patterns to try (should have one capture group)
        
    Returns:
        First number found, or None
        
    Examples:
        >>> patterns = [r'\\btop\\s+(\\d+)', r'\\bfirst\\s+(\\d+)', r'\\blimit\\s+(\\d+)']
        >>> extract_number_from_text("show top 5 devices", patterns)
        5
        
        >>> extract_number_from_text("list all devices", patterns)
        None
    """
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def extract_tag_from_text(text: str, patterns: List[str]) -> str | None:
    """
    Extract a tag from text using multiple regex patterns.
    
    Args:
        text: Text to search
        patterns: List of regex patterns to try (should have one capture group)
        
    Returns:
        First tag found (lowercased), or None
        
    Examples:
        >>> patterns = [r'\\btag\\s+([a-z0-9_-]+)', r'\\bwith\\s+tag\\s+([a-z0-9_-]+)']
        >>> extract_tag_from_text("devices with tag prod", patterns)
        "prod"
        
        >>> extract_tag_from_text("list devices", patterns)
        None
    """
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    return None


# ============================================================================
# Type Coercion Helpers
# ============================================================================

def safe_dict_get(data: Any, key: str, default: Any = None) -> Any:
    """
    Safely get value from data, handling non-dict types.
    
    Args:
        data: Data to extract from (ideally dict)
        key: Key to extract
        default: Default value if extraction fails
        
    Returns:
        Value if data is dict and key exists, otherwise default
        
    Examples:
        >>> safe_dict_get({"name": "router1"}, "name")
        "router1"
        
        >>> safe_dict_get(["a", "b"], "name", "N/A")
        "N/A"
        
        >>> safe_dict_get(None, "name", "N/A")
        "N/A"
    """
    if isinstance(data, dict):
        return data.get(key, default)
    return default


def ensure_list(data: Any) -> List:
    """
    Ensure data is a list.
    
    Args:
        data: Data to convert to list
        
    Returns:
        List (unchanged if already list, wrapped if single item, empty if None)
        
    Examples:
        >>> ensure_list([1, 2, 3])
        [1, 2, 3]
        
        >>> ensure_list("single")
        ["single"]
        
        >>> ensure_list(None)
        []
    """
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def ensure_dict(data: Any, fallback_key: str = "value") -> Dict:
    """
    Ensure data is a dictionary.
    
    Args:
        data: Data to convert to dict
        fallback_key: Key to use if wrapping non-dict value
        
    Returns:
        Dict (unchanged if already dict, wrapped if other type)
        
    Examples:
        >>> ensure_dict({"name": "r1"})
        {"name": "r1"}
        
        >>> ensure_dict("router1")
        {"value": "router1"}
        
        >>> ensure_dict(None)
        {}
    """
    if data is None:
        return {}
    if isinstance(data, dict):
        return data
    return {fallback_key: data}
