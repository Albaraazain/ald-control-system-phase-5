"""
Parameter Safety Validation Module

This module provides comprehensive parameter validation to prevent dangerous values
from being written to the PLC. It enforces min/max bounds, data type validation,
and safety-critical parameter protection.

CRITICAL: This module prevents equipment damage by validating ALL parameter writes
before they reach the PLC.
"""
from typing import Dict, Any, Optional, Tuple
from src.log_setup import get_plc_logger

logger = get_plc_logger()


class ParameterValidationError(Exception):
    """Raised when parameter validation fails"""
    pass


class ParameterValidator:
    """
    Validates parameter values before PLC writes to prevent equipment damage.

    Enforces:
    - Min/max bounds checking
    - Data type validation
    - Safety-critical parameter protection
    - Range sanity checks
    """

    def __init__(self):
        """Initialize the parameter validator"""
        self.validation_failures = {}  # Track validation failures for monitoring

    def validate_parameter_write(
        self,
        parameter_name: str,
        target_value: float,
        param_info: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a parameter value before writing to PLC.

        Args:
            parameter_name: Name of the parameter
            target_value: Proposed value to write
            param_info: Parameter metadata from database (min_value, max_value, data_type, etc.)

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if validation passes
            - (False, "error message") if validation fails
        """
        try:
            logger.debug(f"🔍 [VALIDATION START] Parameter: {parameter_name} | Target: {target_value}")

            if param_info is None:
                error_msg = f"Cannot validate parameter '{parameter_name}': no parameter metadata provided"
                logger.error(f"❌ [VALIDATION FAILED] {error_msg}")
                self._track_failure(parameter_name, "missing_metadata")
                return (False, error_msg)

            # Extract parameter metadata
            data_type = param_info.get('data_type', 'float')
            min_value = param_info.get('min_value')
            max_value = param_info.get('max_value')
            is_writable = param_info.get('is_writable', False)

            logger.debug(f"📋 [VALIDATION METADATA] Data type: {data_type} | Min: {min_value} | Max: {max_value} | Writable: {is_writable}")

            # Step 1: Check write permission
            if not is_writable:
                error_msg = f"Parameter '{parameter_name}' is read-only (is_writable=False)"
                logger.error(f"❌ [VALIDATION FAILED] {error_msg}")
                self._track_failure(parameter_name, "read_only")
                return (False, error_msg)

            # Step 2: Data type validation
            is_type_valid, type_error = self._validate_data_type(
                parameter_name, target_value, data_type
            )
            if not is_type_valid:
                logger.error(f"❌ [VALIDATION FAILED] {type_error}")
                self._track_failure(parameter_name, "type_mismatch")
                return (False, type_error)

            # Step 3: Min/Max bounds checking
            is_bounds_valid, bounds_error = self._validate_bounds(
                parameter_name, target_value, min_value, max_value
            )
            if not is_bounds_valid:
                logger.error(f"❌ [VALIDATION FAILED] {bounds_error}")
                self._track_failure(parameter_name, "bounds_violation")
                return (False, bounds_error)

            # Step 4: Safety sanity checks (catch absurd values even if bounds are missing)
            is_sane, sanity_error = self._validate_sanity(
                parameter_name, target_value, data_type
            )
            if not is_sane:
                logger.warning(f"⚠️ [VALIDATION WARNING] {sanity_error}")
                self._track_failure(parameter_name, "sanity_check_failed")
                return (False, sanity_error)

            # All validation passed
            logger.info(f"✅ [VALIDATION PASSED] Parameter '{parameter_name}' = {target_value} is safe to write")
            return (True, None)

        except Exception as e:
            error_msg = f"Unexpected validation error for '{parameter_name}': {str(e)}"
            logger.error(f"❌ [VALIDATION ERROR] {error_msg}", exc_info=True)
            self._track_failure(parameter_name, "validation_exception")
            return (False, error_msg)

    def _validate_data_type(
        self,
        parameter_name: str,
        target_value: float,
        data_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that the target value matches the parameter's data type.

        Args:
            parameter_name: Name of the parameter
            target_value: Proposed value
            data_type: Expected data type (binary, float, integer)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if data_type == 'binary':
            # Binary parameters should be 0 or 1
            if target_value not in (0, 1, 0.0, 1.0):
                return (False, f"Parameter '{parameter_name}' is binary but value {target_value} is not 0 or 1")

        elif data_type == 'integer':
            # Integer parameters should not have decimal places
            if not isinstance(target_value, int) and not float(target_value).is_integer():
                return (False, f"Parameter '{parameter_name}' is integer but value {target_value} has decimal places")

        elif data_type == 'float':
            # Float parameters - just check it's numeric
            try:
                float(target_value)
            except (ValueError, TypeError):
                return (False, f"Parameter '{parameter_name}' requires numeric value but got {type(target_value)}")

        else:
            # Unknown data type - warn but allow
            logger.warning(f"⚠️ [VALIDATION] Unknown data type '{data_type}' for parameter '{parameter_name}'")

        return (True, None)

    def _validate_bounds(
        self,
        parameter_name: str,
        target_value: float,
        min_value: Optional[float],
        max_value: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that the target value is within min/max bounds.

        Args:
            parameter_name: Name of the parameter
            target_value: Proposed value
            min_value: Minimum allowed value (None if no limit)
            max_value: Maximum allowed value (None if no limit)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check minimum bound
        if min_value is not None:
            if target_value < min_value:
                return (False,
                    f"Parameter '{parameter_name}' value {target_value} is below minimum {min_value}")

        # Check maximum bound
        if max_value is not None:
            if target_value > max_value:
                return (False,
                    f"Parameter '{parameter_name}' value {target_value} exceeds maximum {max_value}")

        # Bounds check passed
        if min_value is not None or max_value is not None:
            logger.debug(f"✅ [BOUNDS CHECK] Value {target_value} is within bounds [{min_value}, {max_value}]")
        else:
            logger.warning(f"⚠️ [NO BOUNDS] Parameter '{parameter_name}' has no min/max limits defined in database")

        return (True, None)

    def _validate_sanity(
        self,
        parameter_name: str,
        target_value: float,
        data_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Sanity checks to catch absurd values even when bounds are missing from database.

        This is a safety net for parameters that don't have proper min/max bounds defined.

        Args:
            parameter_name: Name of the parameter
            target_value: Proposed value
            data_type: Parameter data type

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for NaN and infinity
        if data_type in ('float', 'integer'):
            try:
                if not (-1e10 < float(target_value) < 1e10):  # Absurdly large values
                    return (False, f"Parameter '{parameter_name}' value {target_value} is absurdly large (>1e10)")
            except (ValueError, OverflowError):
                return (False, f"Parameter '{parameter_name}' value {target_value} is not a valid number")

        # Temperature sanity checks (catch common parameter names)
        param_lower = parameter_name.lower()
        if 'temp' in param_lower or 'temperature' in param_lower:
            if target_value < -273.15:  # Below absolute zero
                return (False, f"Temperature '{parameter_name}' value {target_value}°C is below absolute zero")
            if target_value > 2000:  # Unreasonably high for ALD
                return (False, f"Temperature '{parameter_name}' value {target_value}°C is absurdly high (>2000°C)")

        # Pressure sanity checks
        if 'pressure' in param_lower or 'press' in param_lower:
            if target_value < 0:  # Negative pressure (not absolute)
                return (False, f"Pressure '{parameter_name}' value {target_value} is negative")
            if target_value > 10000:  # Absurdly high pressure for ALD
                return (False, f"Pressure '{parameter_name}' value {target_value} is absurdly high (>10000 mbar)")

        # Duration/time sanity checks
        if 'duration' in param_lower or 'time' in param_lower:
            if target_value < 0:
                return (False, f"Duration '{parameter_name}' value {target_value} is negative")
            if target_value > 86400000:  # More than 24 hours in milliseconds
                return (False, f"Duration '{parameter_name}' value {target_value}ms is absurdly long (>24 hours)")

        # Flow rate sanity checks
        if 'flow' in param_lower:
            if target_value < 0:
                return (False, f"Flow rate '{parameter_name}' value {target_value} is negative")
            if target_value > 10000:  # Absurdly high flow rate
                return (False, f"Flow rate '{parameter_name}' value {target_value} is absurdly high (>10000)")

        return (True, None)

    def _track_failure(self, parameter_name: str, failure_type: str):
        """
        Track validation failures for monitoring and alerting.

        Args:
            parameter_name: Name of the parameter that failed validation
            failure_type: Type of validation failure
        """
        if parameter_name not in self.validation_failures:
            self.validation_failures[parameter_name] = {}

        if failure_type not in self.validation_failures[parameter_name]:
            self.validation_failures[parameter_name][failure_type] = 0

        self.validation_failures[parameter_name][failure_type] += 1

        # Log warning if same parameter fails repeatedly
        total_failures = sum(self.validation_failures[parameter_name].values())
        if total_failures >= 5:
            logger.warning(
                f"⚠️ [VALIDATION ALERT] Parameter '{parameter_name}' has failed validation {total_failures} times. "
                f"Failure types: {self.validation_failures[parameter_name]}"
            )

    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Get statistics on validation failures for monitoring.

        Returns:
            Dictionary with validation failure statistics
        """
        return {
            "total_parameters_with_failures": len(self.validation_failures),
            "failure_details": self.validation_failures.copy()
        }


# Global validator instance
_validator = ParameterValidator()


def validate_parameter_write(
    parameter_name: str,
    target_value: float,
    param_info: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Convenience function to validate a parameter write using the global validator.

    Args:
        parameter_name: Name of the parameter
        target_value: Proposed value to write
        param_info: Parameter metadata from database

    Returns:
        Tuple of (is_valid, error_message)
    """
    return _validator.validate_parameter_write(parameter_name, target_value, param_info)


def get_validation_stats() -> Dict[str, Any]:
    """
    Get statistics on validation failures for monitoring.

    Returns:
        Dictionary with validation failure statistics
    """
    return _validator.get_validation_stats()
