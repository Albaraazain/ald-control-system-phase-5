# File: src/domain/services.py
"""
Domain services for the ALD control system.
Contains business logic that doesn't naturally fit within entities or value objects.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from .entities import ALDProcess, Recipe, Parameter, ProcessStatus, ParameterType
from .value_objects import ProcessId, RecipeId, ParameterId, Duration, Temperature, Pressure, FlowRate
from .aggregates import ProcessAggregate, RecipeAggregate, ParameterAggregate, SystemAggregate
from src.log_setup import logger

class DomainService(ABC):
    """Base class for domain services"""
    pass

class ValidationService(DomainService):
    """Service for validating business rules and constraints"""

    @staticmethod
    def validate_recipe_for_execution(recipe: Recipe, available_parameters: List[Parameter]) -> List[str]:
        """Validate that a recipe can be executed with available parameters"""
        errors = []

        # Basic recipe validation
        recipe_errors = recipe.validate()
        errors.extend(recipe_errors)

        # Check parameter availability
        available_param_ids = {param.parameter_id for param in available_parameters}
        required_param_ids = set()

        for step in recipe.steps:
            if step.step_type.value == "parameter":
                param_id_str = step.parameters.get('parameter_id')
                if param_id_str:
                    required_param_ids.add(ParameterId(param_id_str))

        missing_params = required_param_ids - available_param_ids
        if missing_params:
            errors.append(f"Missing required parameters: {[str(p) for p in missing_params]}")

        # Validate parameter ranges for parameter steps
        for step in recipe.steps:
            if step.step_type.value == "parameter":
                param_id_str = step.parameters.get('parameter_id')
                target_value = step.parameters.get('value')

                if param_id_str and target_value is not None:
                    param_id = ParameterId(param_id_str)
                    param = next((p for p in available_parameters if p.parameter_id == param_id), None)

                    if param and not param.validate_value(target_value):
                        errors.append(
                            f"Step {step.step_number}: Value {target_value} out of range for parameter {param_id}"
                        )

        return errors

    @staticmethod
    def validate_process_transition(current_status: ProcessStatus, target_status: ProcessStatus) -> bool:
        """Validate if a process status transition is allowed"""
        allowed_transitions = {
            ProcessStatus.IDLE: [ProcessStatus.STARTING],
            ProcessStatus.STARTING: [ProcessStatus.RUNNING, ProcessStatus.FAILED, ProcessStatus.CANCELLED],
            ProcessStatus.RUNNING: [ProcessStatus.PAUSED, ProcessStatus.STOPPING, ProcessStatus.FAILED, ProcessStatus.CANCELLED],
            ProcessStatus.PAUSED: [ProcessStatus.RUNNING, ProcessStatus.STOPPING, ProcessStatus.CANCELLED],
            ProcessStatus.STOPPING: [ProcessStatus.COMPLETED, ProcessStatus.FAILED, ProcessStatus.CANCELLED],
            ProcessStatus.COMPLETED: [],
            ProcessStatus.FAILED: [],
            ProcessStatus.CANCELLED: []
        }

        return target_status in allowed_transitions.get(current_status, [])

    @staticmethod
    def validate_parameter_safety(parameter: Parameter, new_value: float) -> Tuple[bool, str]:
        """Validate parameter safety including critical parameter checks"""
        # Basic range validation
        if not parameter.validate_value(new_value):
            return False, f"Value {new_value} is outside acceptable range"

        # Critical parameter additional validation
        if parameter.is_critical:
            # For critical parameters, implement stricter validation
            if parameter.parameter_type == ParameterType.TEMPERATURE:
                temp = Temperature(new_value, "°C")
                if temp.value > 500:  # Example safety limit
                    return False, "Temperature exceeds safety limit of 500°C"

            elif parameter.parameter_type == ParameterType.PRESSURE:
                pressure = Pressure(new_value, "Pa")
                if pressure.value > 1000000:  # 1 MPa safety limit
                    return False, "Pressure exceeds safety limit of 1 MPa"

        return True, "Parameter value is safe"

class ProcessDomainService(DomainService):
    """Domain service for process-related business logic"""

    def __init__(self, validation_service: ValidationService):
        self.validation_service = validation_service

    def calculate_process_efficiency(self, process: ALDProcess) -> float:
        """Calculate process efficiency based on execution metrics"""
        if not process.completed_at or not process.started_at:
            return 0.0

        actual_duration = (process.completed_at - process.started_at).total_seconds()

        # Get estimated duration from execution log or use default
        estimated_duration = process.performance_metrics.get('estimated_duration', actual_duration)

        if estimated_duration <= 0:
            return 0.0

        # Efficiency = min(estimated/actual, 1.0) * 100
        efficiency = min(estimated_duration / actual_duration, 1.0) * 100
        return round(efficiency, 2)

    def analyze_process_performance(self, process: ALDProcess) -> Dict[str, Any]:
        """Analyze process performance and identify bottlenecks"""
        analysis = {
            'process_id': str(process.process_id),
            'efficiency': self.calculate_process_efficiency(process),
            'step_analysis': [],
            'bottlenecks': [],
            'recommendations': []
        }

        # Analyze individual steps
        for step_info in process.execution_log:
            step_duration = step_info.get('duration', 0)
            step_number = step_info.get('step_number', 0)

            step_analysis = {
                'step_number': step_number,
                'duration': step_duration,
                'efficiency': 100.0  # Would need estimated vs actual comparison
            }

            # Identify long-running steps as potential bottlenecks
            if step_duration > 30:  # Example threshold
                analysis['bottlenecks'].append({
                    'step_number': step_number,
                    'duration': step_duration,
                    'issue': 'Long execution time'
                })

            analysis['step_analysis'].append(step_analysis)

        # Generate recommendations
        if analysis['efficiency'] < 80:
            analysis['recommendations'].append("Process efficiency below 80%, review step timings")

        if len(analysis['bottlenecks']) > 0:
            analysis['recommendations'].append("Multiple bottlenecks identified, optimize step execution")

        return analysis

    def estimate_completion_time(self, process_aggregate: ProcessAggregate) -> Optional[datetime]:
        """Estimate when a running process will complete"""
        process = process_aggregate.process
        recipe = process_aggregate.recipe

        if not process.is_running() or not process.started_at:
            return None

        # Calculate average step duration from execution log
        if process.execution_log:
            total_duration = sum(step.get('duration', 0) for step in process.execution_log)
            avg_step_duration = total_duration / len(process.execution_log)
        else:
            # Use default estimate
            avg_step_duration = 10.0  # seconds

        # Estimate remaining time
        remaining_steps = process.total_steps - process.current_step
        estimated_remaining_seconds = remaining_steps * avg_step_duration

        return datetime.utcnow() + timedelta(seconds=estimated_remaining_seconds)

    def can_process_run_concurrently(self, process1: ALDProcess, process2: ALDProcess) -> bool:
        """Check if two processes can run concurrently without conflicts"""
        # In this simplified implementation, assume processes can run concurrently
        # In a real system, this would check for resource conflicts, parameter conflicts, etc.

        # Example checks:
        # - Do they use conflicting valves?
        # - Do they require exclusive use of certain parameters?
        # - Are there safety constraints?

        return True  # Simplified for now

class RecipeDomainService(DomainService):
    """Domain service for recipe-related business logic"""

    def __init__(self, validation_service: ValidationService):
        self.validation_service = validation_service

    def optimize_recipe_timing(self, recipe: Recipe) -> Recipe:
        """Optimize recipe step timing for better performance"""
        # This is a simplified optimization - in reality would be much more complex
        optimized_steps = []

        for step in recipe.steps:
            optimized_step = step

            # Example optimizations based on step type
            if step.step_type.value == "purge":
                # Optimize purge duration based on volume
                current_duration = step.parameters.get('duration_ms', 5000)
                optimized_duration = max(1000, int(current_duration * 0.8))  # 20% reduction

                optimized_step.parameters['duration_ms'] = optimized_duration

            elif step.step_type.value == "wait":
                # Optimize wait times
                current_duration = step.parameters.get('duration_ms', 1000)
                optimized_duration = max(500, int(current_duration * 0.9))  # 10% reduction

                optimized_step.parameters['duration_ms'] = optimized_duration

            optimized_steps.append(optimized_step)

        # Create new recipe with optimized steps
        optimized_recipe = Recipe(
            recipe_id=recipe.recipe_id,
            name=f"{recipe.name}_optimized",
            description=f"Optimized version of {recipe.description}",
            steps=optimized_steps,
            parameters=recipe.parameters.copy(),
            version_number=f"{recipe.version_number}_opt"
        )

        return optimized_recipe

    def compare_recipes(self, recipe1: Recipe, recipe2: Recipe) -> Dict[str, Any]:
        """Compare two recipes and highlight differences"""
        comparison = {
            'recipe1_id': str(recipe1.recipe_id),
            'recipe2_id': str(recipe2.recipe_id),
            'step_count_diff': len(recipe2.steps) - len(recipe1.steps),
            'estimated_duration_diff': 0,
            'differences': []
        }

        # Compare estimated durations
        duration1 = recipe1.calculate_estimated_duration()
        duration2 = recipe2.calculate_estimated_duration()
        comparison['estimated_duration_diff'] = duration2.milliseconds - duration1.milliseconds

        # Compare steps
        max_steps = max(len(recipe1.steps), len(recipe2.steps))

        for i in range(max_steps):
            step1 = recipe1.steps[i] if i < len(recipe1.steps) else None
            step2 = recipe2.steps[i] if i < len(recipe2.steps) else None

            if step1 is None:
                comparison['differences'].append({
                    'step_number': i + 1,
                    'type': 'added',
                    'description': f"Step added in recipe2: {step2.name}"
                })
            elif step2 is None:
                comparison['differences'].append({
                    'step_number': i + 1,
                    'type': 'removed',
                    'description': f"Step removed from recipe1: {step1.name}"
                })
            elif step1.step_type != step2.step_type:
                comparison['differences'].append({
                    'step_number': i + 1,
                    'type': 'modified',
                    'description': f"Step type changed: {step1.step_type.value} -> {step2.step_type.value}"
                })
            elif step1.parameters != step2.parameters:
                comparison['differences'].append({
                    'step_number': i + 1,
                    'type': 'parameters_changed',
                    'description': f"Parameters modified for step: {step1.name}"
                })

        return comparison

    def generate_recipe_variants(self, base_recipe: Recipe, variant_configs: List[Dict[str, Any]]) -> List[Recipe]:
        """Generate recipe variants based on configuration"""
        variants = []

        for config in variant_configs:
            variant_name = config.get('name', f"{base_recipe.name}_variant")
            parameter_overrides = config.get('parameter_overrides', {})
            step_modifications = config.get('step_modifications', {})

            # Create variant recipe
            variant_steps = []
            for step in base_recipe.steps:
                modified_step = step

                # Apply step modifications
                if step.step_number in step_modifications:
                    modifications = step_modifications[step.step_number]
                    new_parameters = step.parameters.copy()
                    new_parameters.update(modifications)
                    modified_step.parameters = new_parameters

                variant_steps.append(modified_step)

            variant_recipe = Recipe(
                recipe_id=RecipeId(""),  # Will generate new ID
                name=variant_name,
                description=f"Variant of {base_recipe.description}",
                steps=variant_steps,
                parameters={**base_recipe.parameters, **parameter_overrides}
            )

            variants.append(variant_recipe)

        return variants

class ParameterDomainService(DomainService):
    """Domain service for parameter-related business logic"""

    def __init__(self, validation_service: ValidationService):
        self.validation_service = validation_service

    def calculate_parameter_stability(self, parameter_history: List[Tuple[datetime, float]],
                                    window_minutes: int = 5) -> float:
        """Calculate parameter stability over a time window"""
        if len(parameter_history) < 2:
            return 0.0

        # Filter to time window
        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_values = [value for timestamp, value in parameter_history if timestamp >= cutoff_time]

        if len(recent_values) < 2:
            return 0.0

        # Calculate coefficient of variation (std dev / mean)
        mean_value = sum(recent_values) / len(recent_values)
        if mean_value == 0:
            return 0.0

        variance = sum((value - mean_value) ** 2 for value in recent_values) / len(recent_values)
        std_dev = variance ** 0.5
        cv = std_dev / abs(mean_value)

        # Convert to stability percentage (lower CV = higher stability)
        stability = max(0, 100 - (cv * 100))
        return round(stability, 2)

    def detect_parameter_trends(self, parameter_history: List[Tuple[datetime, float]]) -> Dict[str, Any]:
        """Detect trends in parameter values"""
        if len(parameter_history) < 3:
            return {'trend': 'insufficient_data', 'confidence': 0.0}

        # Simple linear regression to detect trend
        timestamps = [(ts - parameter_history[0][0]).total_seconds() for ts, _ in parameter_history]
        values = [value for _, value in parameter_history]

        n = len(timestamps)
        sum_x = sum(timestamps)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(timestamps, values))
        sum_x2 = sum(x * x for x in timestamps)

        # Calculate slope
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return {'trend': 'stable', 'confidence': 0.0}

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        # Determine trend direction and confidence
        if abs(slope) < 0.001:  # Very small slope
            trend = 'stable'
        elif slope > 0:
            trend = 'increasing'
        else:
            trend = 'decreasing'

        # Calculate R-squared for confidence
        mean_y = sum_y / n
        ss_tot = sum((y - mean_y) ** 2 for y in values)

        if ss_tot == 0:
            confidence = 1.0
        else:
            intercept = (sum_y - slope * sum_x) / n
            ss_res = sum((values[i] - (slope * timestamps[i] + intercept)) ** 2 for i in range(n))
            confidence = max(0, 1 - (ss_res / ss_tot))

        return {
            'trend': trend,
            'slope': slope,
            'confidence': round(confidence, 3),
            'rate_per_hour': slope * 3600  # Convert to per hour
        }

    def recommend_parameter_adjustments(self, current_parameters: Dict[ParameterId, float],
                                      target_parameters: Dict[ParameterId, float]) -> List[Dict[str, Any]]:
        """Recommend parameter adjustments to reach targets"""
        recommendations = []

        for param_id, target_value in target_parameters.items():
            current_value = current_parameters.get(param_id)

            if current_value is None:
                recommendations.append({
                    'parameter_id': str(param_id),
                    'action': 'set_initial_value',
                    'target_value': target_value,
                    'reason': 'Parameter not currently set'
                })
                continue

            difference = target_value - current_value

            if abs(difference) < 0.01:  # Within tolerance
                continue

            # Calculate recommended adjustment
            if abs(difference) > 10:  # Large change
                # Recommend gradual adjustment
                adjustment_step = difference * 0.1  # 10% of difference
                recommendations.append({
                    'parameter_id': str(param_id),
                    'action': 'gradual_adjustment',
                    'current_value': current_value,
                    'target_value': target_value,
                    'recommended_step': adjustment_step,
                    'reason': 'Large change, recommend gradual adjustment'
                })
            else:
                # Direct adjustment
                recommendations.append({
                    'parameter_id': str(param_id),
                    'action': 'direct_adjustment',
                    'current_value': current_value,
                    'target_value': target_value,
                    'reason': 'Small change, safe for direct adjustment'
                })

        return recommendations

    def calculate_parameter_correlation(self, param1_history: List[Tuple[datetime, float]],
                                      param2_history: List[Tuple[datetime, float]]) -> float:
        """Calculate correlation between two parameters"""
        # Align timestamps and get overlapping data points
        aligned_data = []

        for ts1, val1 in param1_history:
            # Find closest timestamp in param2_history
            closest_entry = min(param2_history,
                               key=lambda x: abs((x[0] - ts1).total_seconds()))

            # Only include if timestamps are close (within 1 minute)
            if abs((closest_entry[0] - ts1).total_seconds()) <= 60:
                aligned_data.append((val1, closest_entry[1]))

        if len(aligned_data) < 3:
            return 0.0

        # Calculate Pearson correlation coefficient
        x_values = [x for x, y in aligned_data]
        y_values = [y for x, y in aligned_data]

        n = len(aligned_data)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        sum_y2 = sum(y * y for y in y_values)

        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

        if denominator == 0:
            return 0.0

        correlation = (n * sum_xy - sum_x * sum_y) / denominator
        return round(correlation, 3)