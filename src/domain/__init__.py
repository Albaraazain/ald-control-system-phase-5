# File: src/domain/__init__.py
"""
Domain layer for ALD control system.

Contains business entities, value objects, domain services, and aggregates
following Domain-Driven Design principles.
"""

from .entities import (
    ALDProcess, Recipe, ProcessStep, Parameter,
    ProcessStatus, StepType, ParameterType
)

from .value_objects import (
    ProcessId, RecipeId, ParameterId, ValueRange,
    Duration, Temperature, Pressure, FlowRate
)

from .aggregates import (
    ProcessAggregate, RecipeAggregate,
    ParameterAggregate, SystemAggregate
)

from .services import (
    ProcessDomainService, RecipeDomainService,
    ParameterDomainService, ValidationService
)

__all__ = [
    # Entities
    'ALDProcess', 'Recipe', 'ProcessStep', 'Parameter',
    'ProcessStatus', 'StepType', 'ParameterType',

    # Value Objects
    'ProcessId', 'RecipeId', 'ParameterId', 'ValueRange',
    'Duration', 'Temperature', 'Pressure', 'FlowRate',

    # Aggregates
    'ProcessAggregate', 'RecipeAggregate',
    'ParameterAggregate', 'SystemAggregate',

    # Services
    'ProcessDomainService', 'RecipeDomainService',
    'ParameterDomainService', 'ValidationService'
]