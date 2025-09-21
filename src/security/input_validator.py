"""
Input Validation and Sanitization Module

This module provides comprehensive input validation and sanitization
for the ALD control system to prevent injection attacks and ensure
data integrity.
"""

import re
import ipaddress
import json
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal, InvalidOperation
import jsonschema
from jsonschema import validate
from src.log_setup import logger


class ValidationError(Exception):
    """Input validation error."""
    pass


class InputValidator:
    """Comprehensive input validation and sanitization."""

    # Maximum length limits for different input types
    MAX_STRING_LENGTH = 1024
    MAX_PARAMETER_NAME_LENGTH = 100
    MAX_JSON_SIZE = 10 * 1024  # 10KB
    MAX_LIST_SIZE = 1000

    # Regular expressions for validation
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    PARAMETER_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,99}$')
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.@]+$')
    IP_PATTERN = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')

    @classmethod
    def sanitize_string(cls, value: Any, max_length: Optional[int] = None) -> str:
        """
        Sanitize string input to prevent injection attacks.

        Args:
            value: Input value to sanitize
            max_length: Maximum allowed length (default: MAX_STRING_LENGTH)

        Returns:
            Sanitized string

        Raises:
            ValidationError: If input is invalid or unsafe
        """
        if value is None:
            raise ValidationError("String value cannot be None")

        if not isinstance(value, str):
            value = str(value)

        # Remove null bytes and control characters
        sanitized = value.replace('\x00', '').replace('\r', '').replace('\n', ' ')

        # Remove other dangerous characters
        sanitized = re.sub(r'[<>"\';\\]', '', sanitized)

        # Trim whitespace
        sanitized = sanitized.strip()

        # Check length
        max_len = max_length or cls.MAX_STRING_LENGTH
        if len(sanitized) > max_len:
            raise ValidationError(f"String too long: {len(sanitized)} > {max_len}")

        if len(sanitized) == 0:
            raise ValidationError("String cannot be empty after sanitization")

        return sanitized

    @classmethod
    def validate_uuid(cls, value: Any) -> str:
        """
        Validate UUID format.

        Args:
            value: UUID string to validate

        Returns:
            Validated UUID string

        Raises:
            ValidationError: If UUID format is invalid
        """
        if not isinstance(value, str):
            raise ValidationError("UUID must be a string")

        uuid_str = value.strip().lower()

        if not cls.UUID_PATTERN.match(uuid_str):
            raise ValidationError(f"Invalid UUID format: {value}")

        return uuid_str

    @classmethod
    def validate_parameter_name(cls, value: Any) -> str:
        """
        Validate parameter name format.

        Args:
            value: Parameter name to validate

        Returns:
            Validated parameter name

        Raises:
            ValidationError: If parameter name is invalid
        """
        if not isinstance(value, str):
            raise ValidationError("Parameter name must be a string")

        name = value.strip()

        if not cls.PARAMETER_NAME_PATTERN.match(name):
            raise ValidationError(f"Invalid parameter name format: {value}")

        return name

    @classmethod
    def validate_ip_address(cls, value: Any) -> str:
        """
        Validate IP address format.

        Args:
            value: IP address to validate

        Returns:
            Validated IP address

        Raises:
            ValidationError: If IP address is invalid
        """
        if not isinstance(value, str):
            raise ValidationError("IP address must be a string")

        ip = value.strip()

        try:
            # Use ipaddress module for comprehensive validation
            ip_obj = ipaddress.IPv4Address(ip)
            return str(ip_obj)
        except ipaddress.AddressValueError:
            raise ValidationError(f"Invalid IP address: {value}")

    @classmethod
    def validate_port(cls, value: Any) -> int:
        """
        Validate network port number.

        Args:
            value: Port number to validate

        Returns:
            Validated port number

        Raises:
            ValidationError: If port number is invalid
        """
        try:
            port = int(value)
            if not (1 <= port <= 65535):
                raise ValidationError(f"Port must be between 1 and 65535: {port}")
            return port
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid port number: {value}")

    @classmethod
    def validate_numeric_value(cls, value: Any, min_val: Optional[float] = None,
                              max_val: Optional[float] = None) -> Union[int, float]:
        """
        Validate numeric value with optional range constraints.

        Args:
            value: Numeric value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Validated numeric value

        Raises:
            ValidationError: If value is invalid or out of range
        """
        if value is None:
            raise ValidationError("Numeric value cannot be None")

        try:
            # Handle string representations
            if isinstance(value, str):
                value = value.strip()
                if '.' in value:
                    num_val = float(value)
                else:
                    num_val = int(value)
            else:
                num_val = float(value)

            # Check for NaN and infinity
            if not isinstance(num_val, (int, float)) or str(num_val).lower() in ['nan', 'inf', '-inf']:
                raise ValidationError(f"Invalid numeric value: {value}")

            # Range validation
            if min_val is not None and num_val < min_val:
                raise ValidationError(f"Value {num_val} below minimum {min_val}")

            if max_val is not None and num_val > max_val:
                raise ValidationError(f"Value {num_val} above maximum {max_val}")

            return num_val

        except (ValueError, TypeError, OverflowError):
            raise ValidationError(f"Invalid numeric value: {value}")

    @classmethod
    def validate_json_data(cls, data: Any, schema: Optional[Dict] = None) -> Dict:
        """
        Validate JSON data structure and content.

        Args:
            data: JSON data to validate
            schema: Optional JSON schema for validation

        Returns:
            Validated JSON data

        Raises:
            ValidationError: If JSON data is invalid
        """
        if data is None:
            raise ValidationError("JSON data cannot be None")

        # Convert string to dict if needed
        if isinstance(data, str):
            try:
                # Limit JSON size to prevent DoS
                if len(data) > cls.MAX_JSON_SIZE:
                    raise ValidationError(f"JSON too large: {len(data)} > {cls.MAX_JSON_SIZE}")

                data = json.loads(data)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON format: {e}")

        if not isinstance(data, dict):
            raise ValidationError("JSON data must be an object/dictionary")

        # Schema validation if provided
        if schema:
            try:
                validate(instance=data, schema=schema)
            except jsonschema.ValidationError as e:
                raise ValidationError(f"JSON schema validation failed: {e}")

        return data

    @classmethod
    def validate_list(cls, data: Any, item_validator: Optional[callable] = None,
                     max_size: Optional[int] = None) -> List:
        """
        Validate list data.

        Args:
            data: List data to validate
            item_validator: Optional validator function for list items
            max_size: Maximum allowed list size

        Returns:
            Validated list

        Raises:
            ValidationError: If list data is invalid
        """
        if not isinstance(data, list):
            raise ValidationError("Data must be a list")

        max_len = max_size or cls.MAX_LIST_SIZE
        if len(data) > max_len:
            raise ValidationError(f"List too large: {len(data)} > {max_len}")

        # Validate individual items if validator provided
        if item_validator:
            validated_items = []
            for i, item in enumerate(data):
                try:
                    validated_items.append(item_validator(item))
                except ValidationError as e:
                    raise ValidationError(f"List item {i} validation failed: {e}")
            return validated_items

        return data

    @classmethod
    def validate_parameter_value(cls, value: Any, parameter_type: str) -> Any:
        """
        Validate parameter value based on expected type.

        Args:
            value: Parameter value to validate
            parameter_type: Expected parameter type

        Returns:
            Validated parameter value

        Raises:
            ValidationError: If parameter value is invalid
        """
        if parameter_type == "int":
            return cls.validate_numeric_value(value)
        elif parameter_type == "float":
            return cls.validate_numeric_value(value)
        elif parameter_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.lower() in ["true", "1", "yes", "on"]:
                    return True
                elif value.lower() in ["false", "0", "no", "off"]:
                    return False
            raise ValidationError(f"Invalid boolean value: {value}")
        elif parameter_type == "string":
            return cls.sanitize_string(value)
        else:
            raise ValidationError(f"Unknown parameter type: {parameter_type}")

    @classmethod
    def validate_plc_address(cls, address: Any) -> int:
        """
        Validate PLC Modbus address.

        Args:
            address: Modbus address to validate

        Returns:
            Validated address

        Raises:
            ValidationError: If address is invalid
        """
        try:
            addr = int(address)
            if not (0 <= addr <= 65535):
                raise ValidationError(f"Modbus address must be 0-65535: {addr}")
            return addr
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid Modbus address: {address}")

    @classmethod
    def validate_machine_status(cls, status: Any) -> str:
        """
        Validate machine status value.

        Args:
            status: Machine status to validate

        Returns:
            Validated status

        Raises:
            ValidationError: If status is invalid
        """
        if not isinstance(status, str):
            raise ValidationError("Machine status must be a string")

        status = status.strip().lower()
        valid_statuses = ["idle", "processing", "error", "maintenance"]

        if status not in valid_statuses:
            raise ValidationError(f"Invalid machine status: {status}. Must be one of {valid_statuses}")

        return status


# Decorator for automatic input validation
def validate_inputs(**validators):
    """
    Decorator for automatic input validation.

    Args:
        **validators: Keyword arguments mapping parameter names to validator functions

    Example:
        @validate_inputs(user_id=InputValidator.validate_uuid,
                        parameter_name=InputValidator.validate_parameter_name)
        def my_function(user_id, parameter_name):
            # Function body
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get function argument names
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Validate each argument
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    try:
                        bound_args.arguments[param_name] = validator(bound_args.arguments[param_name])
                    except ValidationError as e:
                        logger.error(f"Input validation failed for {param_name}: {e}")
                        raise

            return func(*bound_args.args, **bound_args.kwargs)
        return wrapper
    return decorator


# Pre-defined validation schemas
PLC_PARAMETER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": "^[a-zA-Z][a-zA-Z0-9_]{0,99}$"},
        "address": {"type": "integer", "minimum": 0, "maximum": 65535},
        "data_type": {"type": "string", "enum": ["int16", "int32", "float32", "bool"]},
        "scale_factor": {"type": "number"},
        "unit": {"type": "string", "maxLength": 20}
    },
    "required": ["name", "address", "data_type"],
    "additionalProperties": False
}

PROCESS_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "process_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
        "parameter_values": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z][a-zA-Z0-9_]{0,99}$": {"type": "number"}
            }
        },
        "timestamp": {"type": "string", "format": "date-time"}
    },
    "required": ["process_id", "parameter_values", "timestamp"],
    "additionalProperties": False
}