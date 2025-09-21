# ALD Control System - Comprehensive Architecture Documentation

## System Overview

The Atomic Layer Deposition (ALD) Control System is a sophisticated industrial control platform built with clean architecture principles, dependency injection, and high-performance async operations. The system manages hardware operations through a multi-layer architecture designed for reliability, testability, and maintainability.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                       │
├─────────────────────────────────────────────────────────────────┤
│                        Application Layer                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Command Flow   │  │  Recipe Flow    │  │   Step Flow     │ │
│  │                 │  │                 │  │                 │ │
│  │ • Listener      │  │ • Starter       │  │ • Valve Step    │ │
│  │ • Processor     │  │ • Executor      │  │ • Purge Step    │ │
│  │ • State         │  │ • Stopper       │  │ • Parameter     │ │
│  │ • Status        │  │ • Cancellation  │  │ • Loop Step     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                        Domain Layer                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Abstractions  │  │   Event Bus     │  │  State Manager  │ │
│  │                 │  │                 │  │                 │ │
│  │ • IPLCInterface │  │ • Events        │  │ • State Trans.  │ │
│  │ • IDatabaseSvc  │  │ • Subscribers   │  │ • Atomic Ops    │ │
│  │ • IParameterLog │  │ • Publishers    │  │ • Persistence   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      Infrastructure Layer                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   PLC Layer     │  │   Data Layer    │  │  Security Layer │ │
│  │                 │  │                 │  │                 │ │
│  │ • Real PLC      │  │ • Transactional │  │ • Credential    │ │
│  │ • Simulation    │  │ • Dual-Mode Log │  │ • Input Valid.  │ │
│  │ • Discovery     │  │ • Connection    │  │ • Rate Limiting │ │
│  │ • Manager       │  │ • Pool          │  │ • Monitoring    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                    Cross-Cutting Concerns                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  DI Container   │  │  Performance    │  │   Monitoring    │ │
│  │                 │  │                 │  │                 │ │
│  │ • Service Reg.  │  │ • Async Pipeline│  │ • Health Checks │ │
│  │ • Lifecycle     │  │ • Connection    │  │ • Logging       │ │
│  │ • Auto-wiring   │  │ • Pool          │  │ • Metrics       │ │
│  │ • Circular Det. │  │ • Bulk Ops      │  │ • Alerting      │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Core Architecture Principles

### 1. Clean Architecture
- **Dependency Rule**: Dependencies point inward toward the domain
- **Abstract Interfaces**: All external dependencies are abstracted
- **Separation of Concerns**: Each layer has a single responsibility
- **Testability**: All components can be tested in isolation

### 2. Dependency Injection
- **ServiceContainer**: Advanced IoC container with async support
- **Multiple Lifetimes**: Singleton, Transient, and Scoped services
- **Auto-wiring**: Automatic dependency resolution via type hints
- **Circular Detection**: Prevents and reports circular dependencies

### 3. Event-Driven Architecture
- **Event Bus**: Decoupled communication between components
- **Async Messaging**: Non-blocking event processing
- **Publish/Subscribe**: Loosely coupled component interaction
- **Event Sourcing**: Audit trail of system state changes

### 4. High-Performance Design
- **Async/Await**: Non-blocking I/O throughout the system
- **Connection Pooling**: Efficient database connection management
- **Bulk Operations**: Optimized batch processing for PLC and database
- **Performance Monitoring**: Real-time performance metrics

## Layer Descriptions

### Application Layer

#### Command Flow (`src/command_flow/`)
Manages external commands from the Supabase database:
- **Listener**: Polls for new commands with configurable intervals
- **Processor**: Executes commands with state management
- **State**: Maintains current command execution state
- **Status**: Provides command status updates

#### Recipe Flow (`src/recipe_flow/`)
Handles ALD recipe execution lifecycle:
- **Starter**: Initializes recipe execution environment
- **Executor**: Orchestrates step execution with error handling
- **Stopper**: Gracefully terminates recipe execution
- **Cancellation**: Handles interruption and cleanup
- **Data Recorder**: Continuous data collection during execution

#### Step Flow (`src/step_flow/`)
Implements individual recipe step types:
- **Valve Step**: Controls valve states with timing
- **Purge Step**: Manages purge operations
- **Parameter Step**: Sets PLC parameters
- **Loop Step**: Implements iterative operations

### Domain Layer

#### Abstractions (`src/abstractions/`)
Defines all service interfaces:
- **IPLCInterface**: PLC communication contract
- **IDatabaseService**: Database operations contract
- **IParameterLogger**: Parameter logging contract
- **IEventBus**: Event-driven communication contract
- **IStateManager**: State management contract
- **IConnectionMonitor**: Connection monitoring contract

### Infrastructure Layer

#### PLC Layer (`src/plc/`)
Hardware communication infrastructure:
- **RealPLC**: Production PLC communication via Modbus TCP/IP
- **Simulation**: Development/testing PLC simulation
- **Discovery**: Dynamic PLC discovery and configuration
- **Manager**: Centralized PLC access with connection pooling
- **Communicator**: Low-level Modbus protocol handling

#### Data Layer (`src/data_collection/`)
Persistent data management:
- **Transactional**: ACID-compliant dual-mode data operations
- **High-Performance**: Optimized bulk insert operations
- **Connection Pool**: Async database connection management
- **Dual-Mode Logging**: Idle and process-specific data logging

#### Security Layer (`src/security/`)
Comprehensive security framework:
- **Credential Manager**: Secure credential storage and rotation
- **Input Validator**: Input sanitization and validation
- **Rate Limiter**: DoS protection and resource throttling
- **Security Config**: Centralized security configuration

### Cross-Cutting Concerns

#### Dependency Injection (`src/di/`)
IoC container implementation:
- **ServiceContainer**: Core DI container with async support
- **Service Locator**: Global service resolution
- **Factories**: Service factory patterns
- **Configuration**: JSON/environment-based configuration
- **Migration**: Legacy compatibility and gradual migration

#### Performance Layer (`src/performance/`)
High-performance optimizations:
- **Async Pipeline**: Non-blocking operation pipeline
- **Connection Pool**: Database connection optimization
- **Bulk Operations**: Batch processing optimization
- **Performance Monitor**: Real-time performance tracking

## Data Flow Architecture

### 1. Command Processing Flow
```
Supabase DB → Command Listener → Command Processor → Recipe Executor → Step Executor → PLC Interface → Hardware
```

### 2. Data Collection Flow
```
PLC Hardware → PLC Interface → Parameter Logger → Transactional Repository → Database
```

### 3. Dual-Mode Data Logging
```
Idle Mode:    PLC → Parameter Logger → parameter_value_history table
Process Mode: PLC → Parameter Logger → parameter_value_history + process_data_points tables
```

### 4. Event Flow
```
Component → Event Bus → Event Handlers → State Manager → Database
```

## Key Design Patterns

### 1. Dependency Injection Pattern
- **Registration**: Services registered with lifetime management
- **Resolution**: Automatic dependency graph resolution
- **Disposal**: Proper resource cleanup and lifecycle management

### 2. Repository Pattern
- **Abstract Repositories**: Data access abstraction
- **Transactional Operations**: ACID compliance
- **Dual-Mode**: Idle and process-specific data handling

### 3. Factory Pattern
- **Service Factories**: Configurable service creation
- **PLC Factory**: Dynamic PLC implementation selection
- **Database Factory**: Connection pool management

### 4. Observer Pattern
- **Event Bus**: Publish/subscribe messaging
- **State Watchers**: State change notifications
- **Health Monitors**: Component health tracking

### 5. Strategy Pattern
- **PLC Strategies**: Real vs simulation implementations
- **Logging Strategies**: Idle vs process logging modes
- **Security Strategies**: Configurable security levels

## Performance Characteristics

### Target Performance Metrics
- **Parameter Logging Interval**: 1 second ±10ms jitter
- **End-to-End Cycle Time**: <500ms (current: 650-1600ms)
- **Database Batch Insert**: <100ms for 50 records
- **PLC Bulk Read**: <200ms for 50+ parameters
- **Service Resolution**: <1ms for DI container
- **Memory Usage**: <200MB sustained

### Performance Optimizations
- **Async Pipeline**: All I/O operations non-blocking
- **Connection Pooling**: Reuse database connections
- **Bulk Operations**: Batch PLC reads and database writes
- **Metadata Caching**: Cache parameter metadata
- **Performance Monitoring**: Real-time performance tracking

## Security Architecture

### Security Layers
1. **Input Validation**: All external inputs validated and sanitized
2. **Rate Limiting**: DoS protection with configurable thresholds
3. **Credential Management**: Secure storage with automatic rotation
4. **Network Security**: Restricted PLC network access
5. **File Security**: Secure file permissions and validation
6. **Monitoring**: Real-time security event monitoring

### Security Features
- **JWT Validation**: Token-based authentication
- **UUID Validation**: Secure identifier validation
- **Input Sanitization**: SQL injection and XSS prevention
- **Rate Limiting**: Request throttling and circuit breaking
- **Secure Configurations**: Environment-based security settings

## Deployment Architecture

### Environment Configuration
- **Development**: Full simulation mode with comprehensive logging
- **Testing**: Mixed real/simulation with enhanced monitoring
- **Production**: Real PLC with optimized performance settings

### High Availability
- **Connection Recovery**: Automatic PLC and database reconnection
- **Graceful Degradation**: Fallback to simulation mode
- **Health Monitoring**: Continuous component health checks
- **Alerting**: Real-time alert system for critical issues

### Monitoring and Observability
- **Performance Metrics**: Real-time performance dashboards
- **Health Checks**: Component and system health monitoring
- **Logging**: Structured logging with correlation IDs
- **Alerting**: Configurable alert thresholds and notifications

## Migration Strategy

### Legacy Compatibility
- **Adapter Patterns**: Bridge old and new implementations
- **Feature Flags**: Gradual rollout of new features
- **Migration Helpers**: Automated migration utilities
- **Backward Compatibility**: Support for existing integrations

### Gradual Migration
- **Phase 1**: Infrastructure layer (DI, security, performance)
- **Phase 2**: Domain layer (abstractions, event bus)
- **Phase 3**: Application layer (flows with new architecture)
- **Phase 4**: Presentation layer (new APIs and interfaces)

This architecture provides a robust, scalable, and maintainable foundation for the ALD control system while ensuring high performance and security standards.