# ALD Control System v2.0 - Architectural Diagrams

## System Architecture Overview

```mermaid
graph TB
    subgraph "Presentation Layer"
        CLI[CLI Interface]
        API[REST API]
        EVENTS[Event Handlers]
        MONITOR[Monitoring Dashboard]
    end

    subgraph "Application Layer"
        CMD[Command Handlers]
        QUERY[Query Handlers]
        USECASE[Use Cases]
        EVENTAPP[Event Application Handlers]
    end

    subgraph "Domain Layer"
        ENTITIES[Domain Entities]
        VALUEOBJ[Value Objects]
        DOMAINSERV[Domain Services]
        DOMAINEVENTS[Domain Events]
        STATEMACHINE[State Machine]
        AGGREGATES[Aggregates]
    end

    subgraph "Infrastructure Layer"
        REPOS[Repositories]
        PLC[PLC Adapters]
        DB[Database Adapters]
        CACHE[Cache Services]
        EVENTS_INFRA[Event Store]
        EXTERNAL[External Services]
    end

    CLI --> CMD
    API --> CMD
    EVENTS --> EVENTAPP

    CMD --> USECASE
    QUERY --> USECASE
    EVENTAPP --> USECASE

    USECASE --> ENTITIES
    USECASE --> DOMAINSERV
    USECASE --> STATEMACHINE

    ENTITIES --> REPOS
    DOMAINSERV --> REPOS
    STATEMACHINE --> EVENTS_INFRA

    REPOS --> DB
    PLC --> EXTERNAL
    CACHE --> DB
```

## Dependency Injection Container Architecture

```mermaid
graph TB
    subgraph "DI Container Core"
        CONTAINER[DIContainer]
        REGISTRY[ServiceRegistry]
        LOCATOR[ServiceLocator]
        DESCRIPTOR[ServiceDescriptor]
    end

    subgraph "Service Lifecycles"
        SINGLETON[Singleton Services]
        TRANSIENT[Transient Services]
        SCOPED[Scoped Services]
        FACTORY[Factory Services]
    end

    subgraph "Registration Strategies"
        CORE_REG[Core Service Registration]
        COMPAT_REG[Compatibility Registration]
        FLAG_REG[Feature Flag Registration]
        HEALTH_REG[Health Check Registration]
    end

    subgraph "Registered Services"
        IPLC[IPLCInterface]
        IREPO[IRepository Services]
        IDATA[IDataCollectionService]
        ISTATE[IStateManager]
        IEVENT[IEventBus]
        ICACHE[ICacheService]
        ICONFIG[IConfigurationService]
        ISECURITY[ICredentialManager]
    end

    REGISTRY --> CONTAINER
    LOCATOR --> CONTAINER
    CONTAINER --> DESCRIPTOR

    CORE_REG --> REGISTRY
    COMPAT_REG --> REGISTRY
    FLAG_REG --> REGISTRY
    HEALTH_REG --> REGISTRY

    CONTAINER --> SINGLETON
    CONTAINER --> TRANSIENT
    CONTAINER --> SCOPED
    CONTAINER --> FACTORY

    SINGLETON --> IPLC
    SINGLETON --> IDATA
    SINGLETON --> ISTATE
    SINGLETON --> IEVENT
    SINGLETON --> ICACHE
    SINGLETON --> ICONFIG
    SINGLETON --> ISECURITY

    TRANSIENT --> IREPO
```

## Event-Driven State Management Architecture

```mermaid
graph TB
    subgraph "Event Sourcing Layer"
        EVENTSTORE[Event Store]
        EVENTBUS[Event Bus]
        PROJECTIONS[Read Projections]
        SNAPSHOTS[State Snapshots]
    end

    subgraph "State Machine"
        SM[Machine State Machine]
        STATES[States: idle, processing, error]
        TRANSITIONS[State Transitions]
        VALIDATION[Transition Validation]
    end

    subgraph "Domain Events"
        PROCESS_START[ProcessStartedEvent]
        PROCESS_STOP[ProcessStoppedEvent]
        STATE_CHANGE[MachineStateChangedEvent]
        MODE_CHANGE[LoggingModeChangedEvent]
    end

    subgraph "Event Handlers"
        PARAM_LOGGER[Parameter Logger Handler]
        STATE_PROJ[State Projection Handler]
        AUDIT_LOG[Audit Log Handler]
        MONITOR[Monitoring Handler]
    end

    subgraph "Consistency Guarantees"
        ATOMIC[Atomic Transitions]
        CONSISTENCY[Read Consistency]
        SAGA[Saga Pattern]
        COMPENSATION[Compensation Actions]
    end

    SM --> TRANSITIONS
    TRANSITIONS --> VALIDATION
    VALIDATION --> DOMAIN_EVENTS

    PROCESS_START --> EVENTBUS
    PROCESS_STOP --> EVENTBUS
    STATE_CHANGE --> EVENTBUS
    MODE_CHANGE --> EVENTBUS

    EVENTBUS --> EVENTSTORE
    EVENTBUS --> PARAM_LOGGER
    EVENTBUS --> STATE_PROJ
    EVENTBUS --> AUDIT_LOG
    EVENTBUS --> MONITOR

    EVENTSTORE --> PROJECTIONS
    PROJECTIONS --> SNAPSHOTS

    SM --> ATOMIC
    ATOMIC --> CONSISTENCY
    CONSISTENCY --> SAGA
    SAGA --> COMPENSATION
```

## Data Flow Architecture for Dual-Mode Logging

```mermaid
graph TB
    subgraph "Parameter Reading Pipeline"
        PLC_READ[PLC Bulk Read]
        PARAM_CACHE[Parameter Metadata Cache]
        VALIDATION[Input Validation]
        TIMESTAMP[Timestamp Assignment]
    end

    subgraph "State Determination"
        STATE_QUERY[Atomic State Query]
        MODE_DETECT[Logging Mode Detection]
        PROCESS_RESOLVE[Process ID Resolution]
    end

    subgraph "Dual-Mode Decision Logic"
        DECISION{Logging Mode?}
        IDLE_PATH[Idle Mode Path]
        PROCESS_PATH[Process Mode Path]
    end

    subgraph "Transaction Management"
        UOW[Unit of Work]
        TRANSACTION[Database Transaction]
        DUAL_WRITE[Dual Table Write]
        ROLLBACK[Rollback on Failure]
    end

    subgraph "Data Persistence"
        PARAM_HIST[parameter_value_history]
        PROCESS_DATA[process_data_points]
        EVENT_LOG[Event Log]
        AUDIT_TRAIL[Audit Trail]
    end

    PLC_READ --> PARAM_CACHE
    PARAM_CACHE --> VALIDATION
    VALIDATION --> TIMESTAMP

    TIMESTAMP --> STATE_QUERY
    STATE_QUERY --> MODE_DETECT
    MODE_DETECT --> PROCESS_RESOLVE

    PROCESS_RESOLVE --> DECISION
    DECISION -->|Idle| IDLE_PATH
    DECISION -->|Processing| PROCESS_PATH

    IDLE_PATH --> UOW
    PROCESS_PATH --> UOW

    UOW --> TRANSACTION
    TRANSACTION --> DUAL_WRITE

    DUAL_WRITE --> PARAM_HIST
    DUAL_WRITE --> PROCESS_DATA
    DUAL_WRITE --> EVENT_LOG
    DUAL_WRITE --> AUDIT_TRAIL

    TRANSACTION --> ROLLBACK
```

## Clean Architecture Layer Dependencies

```mermaid
graph TB
    subgraph "External Interfaces"
        UI[User Interface]
        DB[Database]
        PLC_HW[PLC Hardware]
        FS[File System]
        NET[Network]
    end

    subgraph "Interface Adapters"
        CONTROLLERS[Controllers]
        PRESENTERS[Presenters]
        GATEWAYS[Gateways]
        ADAPTERS[External Adapters]
    end

    subgraph "Application Business Rules"
        USECASES[Use Cases]
        APP_SERVICES[Application Services]
        COMMAND_HANDLERS[Command Handlers]
        QUERY_HANDLERS[Query Handlers]
    end

    subgraph "Enterprise Business Rules"
        ENTITIES[Entities]
        VALUE_OBJECTS[Value Objects]
        DOMAIN_SERVICES[Domain Services]
        BUSINESS_RULES[Business Rules]
    end

    UI --> CONTROLLERS
    CONTROLLERS --> USECASES
    USECASES --> ENTITIES

    ENTITIES --> DOMAIN_SERVICES
    DOMAIN_SERVICES --> VALUE_OBJECTS

    USECASES --> GATEWAYS
    GATEWAYS --> ADAPTERS
    ADAPTERS --> DB
    ADAPTERS --> PLC_HW
    ADAPTERS --> FS
    ADAPTERS --> NET

    USECASES --> PRESENTERS
    PRESENTERS --> UI

    COMMAND_HANDLERS --> USECASES
    QUERY_HANDLERS --> USECASES
    APP_SERVICES --> USECASES
```

## Performance Optimization Architecture

```mermaid
graph TB
    subgraph "Async Pipeline"
        READER[Parameter Reader Task]
        PROCESSOR[Batch Processor Task]
        WRITER[Database Writer Task]
        MONITOR[Performance Monitor Task]
    end

    subgraph "Connection Management"
        POOL[Connection Pool]
        HEALTH[Health Checks]
        CIRCUIT[Circuit Breaker]
        RETRY[Retry Logic]
    end

    subgraph "Caching Layer"
        METADATA_CACHE[Parameter Metadata Cache]
        QUERY_CACHE[Query Result Cache]
        CONFIG_CACHE[Configuration Cache]
        TTL[TTL Management]
    end

    subgraph "Bulk Operations"
        BULK_READ[Bulk PLC Read]
        BATCH_WRITE[Batch Database Write]
        PARALLEL[Parallel Processing]
        STREAMING[Stream Processing]
    end

    subgraph "Performance Monitoring"
        METRICS[Real-time Metrics]
        ALERTS[Performance Alerts]
        PROFILING[Performance Profiling]
        OPTIMIZATION[Continuous Optimization]
    end

    READER --> BULK_READ
    BULK_READ --> METADATA_CACHE
    METADATA_CACHE --> PROCESSOR

    PROCESSOR --> PARALLEL
    PARALLEL --> BATCH_WRITE
    BATCH_WRITE --> POOL

    POOL --> HEALTH
    HEALTH --> CIRCUIT
    CIRCUIT --> RETRY

    WRITER --> STREAMING
    STREAMING --> QUERY_CACHE

    MONITOR --> METRICS
    METRICS --> ALERTS
    ALERTS --> PROFILING
    PROFILING --> OPTIMIZATION

    TTL --> METADATA_CACHE
    TTL --> QUERY_CACHE
    TTL --> CONFIG_CACHE
```

## Security Architecture

```mermaid
graph TB
    subgraph "Authentication & Authorization"
        AUTH[Authentication Service]
        RBAC[Role-Based Access Control]
        JWT[JWT Token Management]
        SESSION[Session Management]
    end

    subgraph "Credential Management"
        VAULT[Credential Vault]
        ROTATION[Automatic Rotation]
        ENCRYPTION[Encryption at Rest]
        SECURE_CONFIG[Secure Configuration]
    end

    subgraph "Input Validation"
        VALIDATOR[Input Validator]
        SANITIZATION[Data Sanitization]
        SCHEMA[Schema Validation]
        RATE_LIMIT[Rate Limiting]
    end

    subgraph "Security Monitoring"
        AUDIT[Audit Logging]
        THREAT[Threat Detection]
        ANOMALY[Anomaly Detection]
        INCIDENT[Incident Response]
    end

    subgraph "Secure Communications"
        TLS[TLS Encryption]
        CERT[Certificate Management]
        MODBUS_SEC[Secure Modbus]
        API_SEC[API Security]
    end

    AUTH --> RBAC
    RBAC --> JWT
    JWT --> SESSION

    VAULT --> ROTATION
    ROTATION --> ENCRYPTION
    ENCRYPTION --> SECURE_CONFIG

    VALIDATOR --> SANITIZATION
    SANITIZATION --> SCHEMA
    SCHEMA --> RATE_LIMIT

    AUDIT --> THREAT
    THREAT --> ANOMALY
    ANOMALY --> INCIDENT

    TLS --> CERT
    CERT --> MODBUS_SEC
    MODBUS_SEC --> API_SEC
```

## Migration Architecture

```mermaid
graph TB
    subgraph "Phase 1: Security Foundation"
        SEC_FIX[Security Fixes]
        GITIGNORE[Secure .gitignore]
        CRED_ROT[Credential Rotation]
        JSON_SEC[JSON Security]
    end

    subgraph "Phase 2: Service Abstraction"
        DI_CONTAINER[DI Container]
        INTERFACES[Service Interfaces]
        ADAPTERS[Compatibility Adapters]
        FEATURE_FLAGS[Feature Flags]
    end

    subgraph "Phase 3: Dependency Injection"
        SERVICE_MIGRATION[Service Migration]
        DUAL_WRITE[Dual Write Pattern]
        ASYNC_PIPELINE[Async Pipeline]
        TRANSACTION_LAYER[Transaction Layer]
    end

    subgraph "Phase 4: Clean Architecture"
        CLEAN_LAYERS[Clean Architecture Layers]
        LEGACY_REMOVAL[Legacy Code Removal]
        OPTIMIZATION[Performance Optimization]
        MONITORING[Full Monitoring]
    end

    subgraph "Migration Support"
        BLUE_GREEN[Blue-Green Deployment]
        CANARY[Canary Releases]
        ROLLBACK[Emergency Rollback]
        VALIDATION[Migration Validation]
    end

    SEC_FIX --> GITIGNORE
    GITIGNORE --> CRED_ROT
    CRED_ROT --> JSON_SEC

    JSON_SEC --> DI_CONTAINER
    DI_CONTAINER --> INTERFACES
    INTERFACES --> ADAPTERS
    ADAPTERS --> FEATURE_FLAGS

    FEATURE_FLAGS --> SERVICE_MIGRATION
    SERVICE_MIGRATION --> DUAL_WRITE
    DUAL_WRITE --> ASYNC_PIPELINE
    ASYNC_PIPELINE --> TRANSACTION_LAYER

    TRANSACTION_LAYER --> CLEAN_LAYERS
    CLEAN_LAYERS --> LEGACY_REMOVAL
    LEGACY_REMOVAL --> OPTIMIZATION
    OPTIMIZATION --> MONITORING

    BLUE_GREEN --> CANARY
    CANARY --> ROLLBACK
    ROLLBACK --> VALIDATION
```

## Circuit Breaker Pattern Implementation

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Open : Failure threshold reached
    Open --> HalfOpen : Recovery timeout elapsed
    HalfOpen --> Closed : Success call
    HalfOpen --> Open : Failure call

    state Closed {
        [*] --> Normal
        Normal --> FailureCount : Call failed
        FailureCount --> Normal : Call succeeded
        FailureCount --> ThresholdCheck : Increment count
        ThresholdCheck --> Normal : Below threshold
        ThresholdCheck --> [*] : Threshold reached
    }

    state Open {
        [*] --> Blocking
        Blocking --> TimeoutCheck : Check recovery timeout
        TimeoutCheck --> Blocking : Timeout not reached
        TimeoutCheck --> [*] : Timeout reached
    }

    state HalfOpen {
        [*] --> TestCall
        TestCall --> [*] : Call result
    }
```

## Interface Dependency Graph

```mermaid
graph TB
    subgraph "Core Interfaces"
        IPLCInterface
        IParameterRepository
        IProcessRepository
        IMachineRepository
        IUnitOfWork
    end

    subgraph "Service Interfaces"
        IParameterLogger
        IDataCollectionService
        IStateManager
        IEventBus
        ICacheService
    end

    subgraph "Infrastructure Interfaces"
        IConnectionPool
        IConfigurationService
        ICredentialManager
        IInputValidator
        ICircuitBreaker
    end

    subgraph "Monitoring Interfaces"
        IHealthCheck
        IMetricsCollector
    end

    IParameterLogger --> IPLCInterface
    IParameterLogger --> IParameterRepository
    IParameterLogger --> IStateManager
    IParameterLogger --> ICacheService

    IDataCollectionService --> IParameterLogger
    IDataCollectionService --> IHealthCheck

    IParameterRepository --> IConnectionPool
    IParameterRepository --> IUnitOfWork

    IStateManager --> IEventBus
    IStateManager --> IMachineRepository

    IUnitOfWork --> IParameterRepository
    IUnitOfWork --> IProcessRepository
    IUnitOfWork --> IMachineRepository

    IConfigurationService --> ICredentialManager
    IInputValidator --> IConfigurationService

    IPLCInterface --> ICircuitBreaker
    IConnectionPool --> ICircuitBreaker

    IHealthCheck --> IMetricsCollector
```

## Conclusion

These architectural diagrams provide a comprehensive visual representation of the ALD Control System v2.0 redesign, showing:

1. **Clean separation of concerns** across architectural layers
2. **Dependency injection** replacing global singletons
3. **Event-driven state management** eliminating race conditions
4. **Performance optimization** through async pipelines and caching
5. **Security architecture** with comprehensive threat mitigation
6. **Migration strategy** with zero-downtime deployment
7. **Interface abstractions** enabling testability and maintainability

The architecture addresses all critical issues identified by the specialist agents while maintaining backward compatibility during the migration process.