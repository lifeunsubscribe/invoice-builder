"""
Tests for request validation utilities.

Verifies array size validation to prevent DoS attacks:
- Valid array sizes pass validation
- Oversized arrays raise ValueError
- Nested validation works correctly
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.middleware.request_validator import (
    validate_array_size,
    validate_nested_array_sizes,
    MAX_ARRAY_SIZE
)


class TestValidateArraySize:
    """Tests for validate_array_size function."""

    def test_valid_list_passes(self):
        """Test that a list within size limit passes validation."""
        valid_list = list(range(100))
        # Should not raise
        validate_array_size(valid_list, 'test_list')

    def test_valid_dict_passes(self):
        """Test that a dict within size limit passes validation."""
        valid_dict = {f"key_{i}": i for i in range(100)}
        # Should not raise
        validate_array_size(valid_dict, 'test_dict')

    def test_empty_array_passes(self):
        """Test that an empty array passes validation."""
        validate_array_size([], 'empty_list')
        validate_array_size({}, 'empty_dict')

    def test_max_size_array_passes(self):
        """Test that an array at exactly max size passes."""
        max_list = list(range(MAX_ARRAY_SIZE))
        validate_array_size(max_list, 'max_list')

    def test_oversized_list_raises_error(self):
        """Test that a list exceeding max size raises ValueError."""
        oversized_list = list(range(MAX_ARRAY_SIZE + 1))

        with pytest.raises(ValueError) as excinfo:
            validate_array_size(oversized_list, 'oversized_list')

        assert "oversized_list" in str(excinfo.value)
        assert "exceeds maximum allowed size" in str(excinfo.value)
        assert str(MAX_ARRAY_SIZE) in str(excinfo.value)

    def test_oversized_dict_raises_error(self):
        """Test that a dict exceeding max size raises ValueError."""
        oversized_dict = {f"key_{i}": i for i in range(MAX_ARRAY_SIZE + 1)}

        with pytest.raises(ValueError) as excinfo:
            validate_array_size(oversized_dict, 'oversized_dict')

        assert "oversized_dict" in str(excinfo.value)
        assert "exceeds maximum allowed size" in str(excinfo.value)

    def test_custom_max_size(self):
        """Test validation with custom max size."""
        test_list = list(range(50))

        # Should pass with max_size=100
        validate_array_size(test_list, 'test_list', max_size=100)

        # Should fail with max_size=10
        with pytest.raises(ValueError):
            validate_array_size(test_list, 'test_list', max_size=10)

    def test_non_array_raises_error(self):
        """Test that non-array types raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            validate_array_size("not an array", 'test_field')

        assert "must be an array or object" in str(excinfo.value)

    def test_error_message_includes_field_name(self):
        """Test that error messages include the field name."""
        oversized = list(range(MAX_ARRAY_SIZE + 1))

        with pytest.raises(ValueError) as excinfo:
            validate_array_size(oversized, 'my_custom_field')

        assert "my_custom_field" in str(excinfo.value)


class TestValidateNestedArraySizes:
    """Tests for validate_nested_array_sizes function."""

    def test_valid_nested_arrays_pass(self):
        """Test that valid nested arrays pass validation."""
        data = {
            'list_field': [1, 2, 3],
            'dict_field': {'a': 1, 'b': 2}
        }
        field_configs = [('list_field', True), ('dict_field', False)]

        # Should not raise
        validate_nested_array_sizes(data, field_configs)

    def test_missing_required_field_raises_error(self):
        """Test that missing required field raises ValueError."""
        data = {'field1': [1, 2, 3]}
        field_configs = [('field1', True), ('field2', True)]

        with pytest.raises(ValueError) as excinfo:
            validate_nested_array_sizes(data, field_configs)

        assert "Required field 'field2' is missing" in str(excinfo.value)

    def test_missing_optional_field_passes(self):
        """Test that missing optional field does not raise error."""
        data = {'field1': [1, 2, 3]}
        field_configs = [('field1', True), ('field2', False)]

        # Should not raise
        validate_nested_array_sizes(data, field_configs)

    def test_oversized_nested_array_raises_error(self):
        """Test that oversized nested array raises ValueError."""
        data = {
            'valid_field': [1, 2, 3],
            'oversized_field': list(range(MAX_ARRAY_SIZE + 1))
        }
        field_configs = [('valid_field', True), ('oversized_field', True)]

        with pytest.raises(ValueError) as excinfo:
            validate_nested_array_sizes(data, field_configs)

        assert "oversized_field" in str(excinfo.value)
        assert "exceeds maximum allowed size" in str(excinfo.value)

    def test_non_array_fields_ignored(self):
        """Test that non-array fields are ignored (not validated)."""
        data = {
            'string_field': 'not an array',
            'number_field': 42,
            'array_field': [1, 2, 3]
        }
        field_configs = [
            ('string_field', False),
            ('number_field', False),
            ('array_field', True)
        ]

        # Should not raise - only array_field is validated
        validate_nested_array_sizes(data, field_configs)

    def test_custom_max_size_for_nested(self):
        """Test nested validation with custom max size."""
        data = {
            'field1': list(range(50))
        }
        field_configs = [('field1', True)]

        # Should pass with max_size=100
        validate_nested_array_sizes(data, field_configs, max_size=100)

        # Should fail with max_size=10
        with pytest.raises(ValueError):
            validate_nested_array_sizes(data, field_configs, max_size=10)
