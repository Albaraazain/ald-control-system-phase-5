# Streamlit PLC UI Integration Architecture

## System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                    STREAMLIT WEB UI                            │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────┐  │
│  │ Connection  │ Parameter   │ Valve       │ Modbus          │  │
│  │ Panel       │ Browser     │ Control     │ Debugger        │  │
│  └─────────────┴─────────────┴─────────────┴─────────────────┘  │
└─────────────────┬───────────────────────────────────────────────┘
                  │ Streamlit Session State
                  │ + Async Wrapper Functions
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                 INTEGRATION LAYER                               │
│  ┌─────────────────┬─────────────────┬─────────────────────────┐ │
│  │ Async Wrappers  │ Session Mgmt    │ Error Handler           │ │
│  │ - asyncio.run() │ - State Cache   │ - Exception Mapping     │ │
│  │ - Thread Safety │ - Connection    │ - User Messages         │ │
│  │ - Progress Mgmt │   Persistence   │ - Recovery Logic        │ │
│  └─────────────────┴─────────────────┴─────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                 EXISTING PLC SYSTEM                            │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  PLC Manager (Singleton)                   │ │
│  │  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │ │
│  │  │ Connection  │ Parameter   │ Valve       │ Purge       │  │ │
│  │  │ Management  │ Operations  │ Control     │ Operations  │  │ │
│  │  └─────────────┴─────────────┴─────────────┴─────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    PLC Interface                            │ │
│  │  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │ │
│  │  │ Real PLC    │ Simulation  │ Discovery   │ Communicator│  │ │
│  │  │ Interface   │ Interface   │ Service     │ (Modbus)    │  │ │
│  │  └─────────────┴─────────────┴─────────────┴─────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    HARDWARE LAYER                              │
│  ┌─────────────────────┬─────────────────────────────────────┐  │
│  │       Real PLC      │           Simulation               │  │
│  │   (Modbus TCP/IP)   │        (In-Memory Mock)            │  │
│  │  - Holding Regs     │    - Simulated Registers           │  │
│  │  - Input Regs       │    - Valve State Simulation       │  │
│  │  - Coils            │    - Parameter Simulation          │  │
│  │  - Discrete Inputs  │    - Configurable Responses        │  │
│  └─────────────────────┴─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

### 1. Request Flow (UI → PLC)
```
User Action (Streamlit UI)
    ↓
UI Component Event Handler
    ↓
Input Validation & Sanitization
    ↓
Session State Update (Loading State)
    ↓
Async Wrapper Function
    ↓ [asyncio.run()]
PLC Manager Method Call
    ↓
PLC Interface Implementation
    ↓
Modbus Communication
    ↓
Hardware Response
```

### 2. Response Flow (PLC → UI)
```
Hardware Response
    ↓
Modbus Protocol Processing
    ↓
PLC Interface Response
    ↓
PLC Manager Response Processing
    ↓
Async Wrapper Result
    ↓ [Exception handling, logging]
Session State Update (Result/Error)
    ↓
UI Component Refresh
    ↓
User Feedback Display
```

## Component Integration Details

### Session State Management
```python
# Session State Structure
st.session_state = {
    # Connection Management
    'plc_connected': False,
    'connection_params': {
        'ip': '192.168.1.100',
        'port': 502,
        'type': 'simulation'
    },
    'connection_status': 'disconnected',
    'last_connection_test': None,
    
    # Parameter Cache
    'parameter_cache': {},
    'parameter_definitions': {},
    'last_parameter_refresh': None,
    'selected_parameters': [],
    
    # Valve States
    'valve_states': {},
    'active_valve_operations': {},
    
    # UI State
    'current_page': 'connection',
    'loading_operations': set(),
    'error_messages': [],
    'success_messages': [],
    
    # Logging
    'log_buffer': deque(maxlen=1000),
    'log_level': 'INFO',
    'auto_refresh_enabled': True
}
```

### Async Wrapper Pattern
```python
# Example Async Wrapper Implementation
def async_plc_operation(func_name: str, *args, **kwargs):
    """Wrapper to execute async PLC operations in Streamlit context"""
    
    def wrapper():
        try:
            # Set loading state
            st.session_state.loading_operations.add(func_name)
            
            # Execute async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                getattr(plc_manager, func_name)(*args, **kwargs)
            )
            loop.close()
            
            return result
            
        except Exception as e:
            # Error handling and logging
            error_msg = f"PLC operation '{func_name}' failed: {str(e)}"
            st.session_state.error_messages.append(error_msg)
            logger.error(error_msg, exc_info=True)
            raise
            
        finally:
            # Clear loading state
            st.session_state.loading_operations.discard(func_name)
    
    return wrapper()
```

### Error Handling Integration
```python
# Error Mapping System
ERROR_MAPPINGS = {
    'ConnectionError': 'Unable to connect to PLC. Check network and PLC status.',
    'TimeoutError': 'PLC operation timed out. The PLC may be busy or disconnected.',
    'ValueError': 'Invalid parameter value. Please check your input.',
    'RuntimeError': 'PLC system error. Check logs for details.',
}

def handle_plc_error(error: Exception, operation: str) -> str:
    """Map technical errors to user-friendly messages"""
    error_type = type(error).__name__
    user_message = ERROR_MAPPINGS.get(error_type, f"Unexpected error in {operation}")
    
    # Log technical details
    logger.error(f"PLC Error in {operation}: {error}", exc_info=True)
    
    # Return user-friendly message
    return f"{user_message} (Error: {str(error)})"
```

## Real-Time Update Architecture

### Parameter Monitoring System
```
Background Thread (daemon)
    ↓
Periodic PLC Parameter Read (configurable interval)
    ↓
Compare with cached values
    ↓
Update session state with changes
    ↓
Trigger UI refresh (streamlit-autorefresh)
    ↓
Display updated values to user
```

### Event-Driven Updates
```python
# Auto-refresh configuration
st_autorefresh(
    interval=2000,  # 2 second intervals
    limit=None,     # No limit on refreshes
    key="plc_monitor"
)

# Conditional refresh logic
if st.session_state.auto_refresh_enabled and st.session_state.plc_connected:
    # Only refresh if connected and monitoring enabled
    refresh_parameter_cache()
    update_valve_states()
    check_active_operations()
```

## Security Integration Points

### Input Validation Layer
```python
# Parameter value validation
def validate_parameter_value(param_id: str, value: Any) -> Tuple[bool, str]:
    """Validate parameter values before PLC write operations"""
    
    # Get parameter definition from database
    param_def = get_parameter_definition(param_id)
    
    # Type validation
    if not isinstance(value, param_def.expected_type):
        return False, f"Expected {param_def.expected_type}, got {type(value)}"
    
    # Range validation
    if hasattr(param_def, 'min_value') and value < param_def.min_value:
        return False, f"Value below minimum: {param_def.min_value}"
    
    if hasattr(param_def, 'max_value') and value > param_def.max_value:
        return False, f"Value above maximum: {param_def.max_value}"
    
    return True, "Valid"
```

### Operation Confirmation System
```python
# Dangerous operation confirmation
@require_confirmation
def execute_dangerous_operation(operation_name: str, **params):
    """Execute operations requiring user confirmation"""
    
    # Display confirmation dialog
    confirmed = st.modal_confirmation(
        title=f"Confirm {operation_name}",
        message=f"Are you sure you want to execute {operation_name}?",
        details=f"Parameters: {params}"
    )
    
    if confirmed:
        return async_plc_operation(operation_name, **params)
    else:
        st.info("Operation cancelled by user")
        return False
```

## Database Integration Points

### Parameter Definition Sync
```python
# Sync parameter definitions from Supabase
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_parameter_definitions():
    """Load and cache parameter definitions from database"""
    
    supabase = get_supabase()
    result = supabase.table('component_parameters').select('*').execute()
    
    # Transform to dictionary for efficient lookup
    return {param['id']: param for param in result.data}
```

### Operation Logging
```python
def log_plc_operation(operation: str, parameters: dict, result: Any, error: str = None):
    """Log PLC operations to database for audit trail"""
    
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'operation': operation,
        'parameters': json.dumps(parameters),
        'result': str(result) if result else None,
        'error': error,
        'user_session': st.session_state.get('session_id'),
        'source': 'streamlit_ui'
    }
    
    # Async database insert
    supabase = get_supabase()
    supabase.table('plc_operation_logs').insert(log_entry).execute()
```

## Performance Optimization Strategies

### Caching Architecture
```python
# Multi-level caching system
@st.cache_data(ttl=60)  # UI level cache
def get_cached_parameters():
    """Cached parameter data for UI display"""
    return st.session_state.parameter_cache

@st.cache_resource  # Resource-level cache
def get_plc_manager():
    """Cached PLC manager instance"""
    return plc_manager

# Manual cache invalidation
def invalidate_parameter_cache():
    """Force refresh of parameter cache"""
    get_cached_parameters.clear()
    st.session_state.parameter_cache.clear()
```

### Connection Pooling
```python
# Connection lifecycle management
class StreamlitPLCManager:
    """Streamlit-aware PLC manager wrapper"""
    
    def __init__(self):
        self._connection_pool = {}
        self._last_activity = {}
    
    def get_connection(self, session_id: str):
        """Get or create connection for session"""
        
        if session_id not in self._connection_pool:
            self._connection_pool[session_id] = plc_manager
        
        self._last_activity[session_id] = time.time()
        return self._connection_pool[session_id]
    
    def cleanup_stale_connections(self, timeout: int = 1800):
        """Clean up connections inactive for timeout seconds"""
        
        current_time = time.time()
        stale_sessions = [
            sid for sid, last_activity in self._last_activity.items()
            if current_time - last_activity > timeout
        ]
        
        for session_id in stale_sessions:
            if session_id in self._connection_pool:
                asyncio.run(self._connection_pool[session_id].disconnect())
                del self._connection_pool[session_id]
                del self._last_activity[session_id]
```

## Deployment Architecture

### Container Structure
```dockerfile
# Multi-stage Dockerfile structure
FROM python:3.11-slim as base
# Install system dependencies

FROM base as dependencies
# Install Python packages

FROM dependencies as application
# Copy application code
# Set up Streamlit configuration

FROM application as production
# Configure production settings
# Set up health checks
# Configure logging
```

### Service Configuration
```yaml
# docker-compose.yml structure
version: '3.8'
services:
  streamlit-ui:
    build: .
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
    volumes:
      - ./logs:/app/logs
      - ./config:/app/config
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

This architecture provides a comprehensive integration between Streamlit and the existing PLC system while maintaining separation of concerns and ensuring robust error handling and performance.