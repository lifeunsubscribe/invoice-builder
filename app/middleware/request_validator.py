"""
Request validation utilities for preventing DoS attacks via oversized payloads.

Provides validation for:
- Maximum array sizes in request payloads
- Request body size limits (configured via Flask's MAX_CONTENT_LENGTH)
"""

# Maximum number of items allowed in array fields (e.g., weekData)
# Prevents memory exhaustion from unbounded arrays
MAX_ARRAY_SIZE = 1000

# Maximum request body size in bytes (10MB)
# Configured in Flask app via MAX_CONTENT_LENGTH
MAX_CONTENT_LENGTH_BYTES = 10 * 1024 * 1024  # 10MB


def validate_array_size(array, field_name, max_size=MAX_ARRAY_SIZE):
    """
    Validate that an array field does not exceed maximum allowed size.

    Args:
        array: The array to validate (list or dict)
        field_name: Name of the field for error messages
        max_size: Maximum allowed number of items (default: MAX_ARRAY_SIZE)

    Raises:
        ValueError: If array exceeds max_size

    Returns:
        None if validation passes
    """
    if not isinstance(array, (list, dict)):
        raise ValueError(f"{field_name} must be an array or object")

    size = len(array)
    if size > max_size:
        raise ValueError(
            f"{field_name} exceeds maximum allowed size of {max_size} items "
            f"(received {size} items)"
        )


def validate_nested_array_sizes(data, field_configs, max_size=MAX_ARRAY_SIZE):
    """
    Validate multiple array fields in a request payload.

    Args:
        data: Request payload dictionary
        field_configs: List of tuples (field_name, is_required)
            Example: [("weekData", True), ("hours", False)]
        max_size: Maximum allowed size for each array

    Raises:
        ValueError: If any array exceeds max_size or required field is missing

    Returns:
        None if all validations pass
    """
    for field_name, is_required in field_configs:
        if field_name not in data:
            if is_required:
                raise ValueError(f"Required field '{field_name}' is missing")
            continue

        field_value = data[field_name]
        if isinstance(field_value, (list, dict)):
            validate_array_size(field_value, field_name, max_size)
