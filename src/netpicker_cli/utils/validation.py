# src/netpicker_cli/utils/validation.py
import re
import json
import ipaddress
from typing import Any, Dict, List, Optional, Union
from ..utils.logging import output_message, log_error_with_context


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_ip_address(ip: str) -> str:
    """
    Validate and normalize an IP address.

    Args:
        ip: IP address string

    Returns:
        Normalized IP address string

    Raises:
        ValidationError: If IP address is invalid
    """
    if not ip or not ip.strip():
        raise ValidationError("IP address cannot be empty")

    ip = ip.strip()

    try:
        # Try to parse as IPv4 or IPv6
        parsed = ipaddress.ip_address(ip)
        return str(parsed)
    except ValueError as e:
        raise ValidationError(f"Invalid IP address '{ip}': {str(e)}")


def validate_hostname(hostname: str) -> str:
    """
    Validate a hostname/FQDN.

    Args:
        hostname: Hostname string

    Returns:
        Normalized hostname string

    Raises:
        ValidationError: If hostname is invalid
    """
    if not hostname or not hostname.strip():
        raise ValidationError("Hostname cannot be empty")

    hostname = hostname.strip().lower()

    # RFC 1123 hostname validation
    if len(hostname) > 253:
        raise ValidationError(f"Hostname too long (max 253 characters): '{hostname}'")

    # Check each label
    labels = hostname.split('.')
    for label in labels:
        if not label:
            raise ValidationError(f"Empty label in hostname: '{hostname}'")
        if len(label) > 63:
            raise ValidationError(f"Label too long (max 63 characters): '{label}' in '{hostname}'")
        if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', label):
            raise ValidationError(f"Invalid label format: '{label}' in '{hostname}'")

    return hostname


def validate_device_name(name: str) -> str:
    """
    Validate a device name.

    Args:
        name: Device name string

    Returns:
        Normalized device name

    Raises:
        ValidationError: If device name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Device name cannot be empty")

    name = name.strip()

    if len(name) > 100:
        raise ValidationError(f"Device name too long (max 100 characters): '{name}'")

    # Allow alphanumeric, hyphens, underscores, and dots
    if not re.match(r'^[a-zA-Z0-9._-]+$', name):
        raise ValidationError(f"Invalid device name format: '{name}' (only alphanumeric, dots, hyphens, and underscores allowed)")

    return name


def validate_tag(tag: str) -> str:
    """
    Validate a single tag.

    Args:
        tag: Tag string

    Returns:
        Normalized tag

    Raises:
        ValidationError: If tag is invalid
    """
    if not tag or not tag.strip():
        raise ValidationError("Tag cannot be empty")

    tag = tag.strip()

    if len(tag) > 50:
        raise ValidationError(f"Tag too long (max 50 characters): '{tag}'")

    # Allow alphanumeric, hyphens, underscores, and dots
    if not re.match(r'^[a-zA-Z0-9._-]+$', tag):
        raise ValidationError(f"Invalid tag format: '{tag}' (only alphanumeric, dots, hyphens, and underscores allowed)")

    return tag


def validate_tags(tags: Union[str, List[str], None]) -> List[str]:
    """
    Validate a list of tags.

    Args:
        tags: Comma-separated string or list of tags

    Returns:
        List of validated tags

    Raises:
        ValidationError: If any tag is invalid
    """
    if tags is None:
        return []

    if isinstance(tags, str):
        # Split by comma and strip whitespace
        tag_list = [t.strip() for t in tags.split(',') if t.strip()]
    elif isinstance(tags, list):
        tag_list = tags
    else:
        raise ValidationError(f"Tags must be a string or list, got {type(tags)}")

    validated_tags = []
    for tag in tag_list:
        validated_tags.append(validate_tag(tag))

    # Check for duplicates
    if len(validated_tags) != len(set(validated_tags)):
        raise ValidationError("Duplicate tags found")

    return validated_tags


def validate_policy_name(name: str) -> str:
    """
    Validate a policy name.

    Args:
        name: Policy name string

    Returns:
        Normalized policy name

    Raises:
        ValidationError: If policy name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Policy name cannot be empty")

    name = name.strip()

    if len(name) > 100:
        raise ValidationError(f"Policy name too long (max 100 characters): '{name}'")

    # Allow alphanumeric, hyphens, underscores, and dots
    if not re.match(r'^[a-zA-Z0-9._-]+$', name):
        raise ValidationError(f"Invalid policy name format: '{name}' (only alphanumeric, dots, hyphens, and underscores allowed)")

    return name


def validate_rule_name(name: str) -> str:
    """
    Validate a rule name.

    Args:
        name: Rule name string

    Returns:
        Normalized rule name

    Raises:
        ValidationError: If rule name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Rule name cannot be empty")

    name = name.strip()

    if len(name) > 200:
        raise ValidationError(f"Rule name too long (max 200 characters): '{name}'")

    # Allow alphanumeric, hyphens, underscores, dots, and slashes
    if not re.match(r'^[a-zA-Z0-9._/-]+$', name):
        raise ValidationError(f"Invalid rule name format: '{name}' (only alphanumeric, dots, hyphens, underscores, and slashes allowed)")

    return name


def validate_json_payload(payload: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
    """
    Validate and parse JSON payload.

    Args:
        payload: JSON string or dict

    Returns:
        Parsed JSON dict

    Raises:
        ValidationError: If JSON is invalid
    """
    if payload is None:
        return {}

    if isinstance(payload, dict):
        return payload

    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return {}

        try:
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                raise ValidationError("JSON payload must be an object (dict)")
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON payload: {str(e)}")
    else:
        raise ValidationError(f"Payload must be a string or dict, got {type(payload)}")


def validate_positive_integer(value: Union[str, int], field_name: str = "value") -> int:
    """
    Validate a positive integer.

    Args:
        value: Integer or string representation
        field_name: Name of the field for error messages

    Returns:
        Validated integer

    Raises:
        ValidationError: If value is not a positive integer
    """
    try:
        if isinstance(value, str):
            int_value = int(value)
        else:
            int_value = int(value)

        if int_value <= 0:
            raise ValidationError(f"{field_name} must be positive, got {int_value}")

        return int_value
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid integer, got '{value}'")


def validate_limit(limit: Union[str, int]) -> int:
    """
    Validate a limit parameter (positive integer, max 1000).

    Args:
        limit: Limit value

    Returns:
        Validated limit

    Raises:
        ValidationError: If limit is invalid
    """
    limit_int = validate_positive_integer(limit, "limit")
    if limit_int > 1000:
        raise ValidationError(f"limit cannot exceed 1000, got {limit_int}")
    return limit_int


def validate_offset(offset: Union[str, int]) -> int:
    """
    Validate an offset parameter (non-negative integer).

    Args:
        offset: Offset value

    Returns:
        Validated offset

    Raises:
        ValidationError: If offset is invalid
    """
    try:
        if isinstance(offset, str):
            offset_int = int(offset)
        else:
            offset_int = int(offset)

        if offset_int < 0:
            raise ValidationError(f"offset must be non-negative, got {offset_int}")

        return offset_int
    except (ValueError, TypeError):
        raise ValidationError(f"offset must be a valid integer, got '{offset}'")


def validate_port(port: Union[str, int]) -> int:
    """
    Validate a network port number.

    Args:
        port: Port number

    Returns:
        Validated port number

    Raises:
        ValidationError: If port is invalid
    """
    port_int = validate_positive_integer(port, "Port")

    if port_int > 65535:
        raise ValidationError(f"Port number too high (max 65535), got {port_int}")

    return port_int


def validate_email(email: str) -> str:
    """
    Validate an email address.

    Args:
        email: Email address string

    Returns:
        Normalized email address

    Raises:
        ValidationError: If email is invalid
    """
    if not email or not email.strip():
        raise ValidationError("Email cannot be empty")

    email = email.strip()

    # Basic email regex (RFC 5322 compliant)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email):
        raise ValidationError(f"Invalid email format: '{email}'")

    if len(email) > 254:
        raise ValidationError(f"Email too long (max 254 characters): '{email}'")

    return email


def validate_url(url: str) -> str:
    """
    Validate a URL.

    Args:
        url: URL string

    Returns:
        Normalized URL

    Raises:
        ValidationError: If URL is invalid
    """
    if not url or not url.strip():
        raise ValidationError("URL cannot be empty")

    url = url.strip()

    # Basic URL validation
    url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'

    if not re.match(url_pattern, url):
        raise ValidationError(f"Invalid URL format: '{url}' (must start with http:// or https://)")

    if len(url) > 2000:
        raise ValidationError(f"URL too long (max 2000 characters): '{url}'")

    return url


def validate_and_report_errors(func_name: str, **kwargs) -> None:
    """
    Validate multiple inputs and report all errors at once.

    Args:
        func_name: Name of the function/command for error context
        **kwargs: Field names and validation functions/values

    Raises:
        ValidationError: With all validation errors combined
    """
    errors = []

    for field_name, (validator_func, value) in kwargs.items():
        try:
            validator_func(value)
        except ValidationError as e:
            errors.append(f"{field_name}: {str(e)}")

    if errors:
        error_msg = f"Validation errors in {func_name}:\n" + "\n".join(f"  - {error}" for error in errors)
        raise ValidationError(error_msg)