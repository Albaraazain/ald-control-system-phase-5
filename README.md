# ALD Control System

A comprehensive **Atomic Layer Deposition (ALD) control system** built with Python, featuring real-time hardware control, recipe execution, and database integration.

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL database (Supabase)
- PLC hardware (or simulation mode)

### Installation

1. **Clone and setup environment:**

```bash
git clone <repository-url>
cd ald-control-system-phase-5
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configuration:**

```bash
cp .env.example .env
# Edit .env with your database credentials and PLC settings
```

## 🏗️ Architecture - Simple 3-Terminal Design

This system uses a **SIMPLE 3-TERMINAL ARCHITECTURE** that eliminates coordination complexity and provides direct PLC access for easy debugging. Each terminal operates independently with its own PLC connection.

### 🔧 TERMINAL 1: PLC Read Service

- **Purpose**: Continuous PLC data collection
- **Function**: Reads PLC parameters every 1 second and updates database
- **Database**: Updates `parameter_value_history` table
- **Launch**: `python main.py --terminal 1 --demo` or `python terminal1_launcher.py --demo`
- **Features**: Direct PLC access, simple database inserts, error handling with retry logic

### 🍳 TERMINAL 2: Recipe Service

- **Purpose**: Recipe command processing and execution
- **Function**: Listens for recipe commands and executes them via direct PLC access
- **Database**: Monitors `recipe_commands` table, updates `process_executions`
- **Launch**: `python main.py --terminal 2 --demo` or `python terminal2_launcher.py --demo`
- **Features**: Direct PLC access, simple polling, reuses existing recipe_flow components
- **Hybrid Architecture**: Recipe execution writes PLC DIRECTLY for performance (160-350ms per step), then logs audit trail to `parameter_control_commands` AFTER write completes. This hybrid approach provides fast execution + full traceability without routing through Terminal 3.

### ⚙️ TERMINAL 3: Parameter Service (with Realtime + Instant Updates)

- **Purpose**: Parameter control and writing for EXTERNAL commands
- **Function**: Listens for parameter commands via Supabase Realtime and writes directly to PLC
- **Database**: Monitors `parameter_control_commands` table (Realtime + polling fallback)
- **Launch**: `python main.py --terminal 3 --demo` or `python terminal3_launcher.py --demo`
- **File**: `terminal3_clean.py`
- **Features**: 
  - 🚀 **Supabase Realtime** for instant command notifications (~0ms delay)
  - 🚀 **Instant database updates** for immediate UI feedback (~100-200ms total)
  - ✅ **Input validation** (NaN, Infinity, type checks)
  - 🔄 **Fallback polling** (10s when Realtime up, 1s when down)
  - ⚡ **Terminal liveness** tracking with heartbeat monitoring
- **Performance**: ~700ms end-to-end latency (17x faster than original 10-12s)
- **Scope**: Handles EXTERNAL manual parameter commands from operators/systems. Does NOT process recipe commands - recipes use direct PLC access (Terminal 2) for speed, then audit to this table for traceability.

### Running the 3-Terminal System

```bash
# Open 3 separate terminal windows and run each service:

# Terminal 1 - PLC Read Service
python main.py --terminal 1 --demo

# Terminal 2 - Recipe Service
python main.py --terminal 2 --demo

# Terminal 3 - Parameter Service
python main.py --terminal 3 --demo

# Or use launcher scripts:
python terminal1_launcher.py --demo
python terminal2_launcher.py --demo
python terminal3_launcher.py --demo
```

### Key Architecture Benefits

✅ **No Coordination Complexity**: Each terminal operates independently
✅ **Direct PLC Access**: No singleton conflicts, each terminal has its own connection
✅ **Easy Debugging**: Simple to understand, no complex agent coordination
✅ **Independent Operation**: Terminals can run separately without dependencies
✅ **Simplified Deployment**: Just run the terminal you need

### Simple Data Flow

1. **Terminal 1 (PLC Read)**: PLC → Direct Read → Database (parameter_value_history)
2. **Terminal 2 (Recipe)**: Database (recipe_commands) → Direct PLC Execution → Process Updates + Audit Trail (parameter_control_commands)
3. **Terminal 3 (Parameter)**: Database (parameter_control_commands) → Direct PLC Write (external commands only)

**Note**: Terminal 2 uses a hybrid architecture - it writes to PLC directly (fast path: 160-350ms), then logs to parameter_control_commands for audit trail (async background task). Terminal 3 handles external commands only, not recipe-driven changes.

### Quick Test

```bash
# Test individual terminals
python terminal1_launcher.py --demo  # Test PLC data collection
python terminal2_launcher.py --demo  # Test recipe execution
python terminal3_launcher.py --demo  # Test parameter control

# Test basic integration
python tests/integration/test_parameter_synchronization.py
python tests/integration/test_parameter_cross_component.py
```

## 📁 Project Structureald-control-system-phase-5/

## 🧪 Testing

### Run Integration Tests

```bash
# Test parameter synchronization (3-terminal integration)
python tests/integration/test_parameter_synchronization.py

# Test cross-component communication
python tests/integration/test_parameter_cross_component.py

# Test PLC connectivity
python tools/debug/test_plc_connection.py

# Test database connectivity
python tools/debug/test_supabase_connection.py
```

### Test Individual Terminals

```bash
# Terminal 1 (PLC Read) tests
python terminal1_launcher.py --demo

# Terminal 2 (Recipe) tests
python terminal2_launcher.py --demo

# Terminal 3 (Parameter) tests
python terminal3_launcher.py --demo
```

### Test Coverage

- ✅ 3-terminal architecture integration
- ✅ Parameter synchronization across terminals
- ✅ PLC communication (simulation and real)
- ✅ Database operations for each terminal
- ✅ Error handling and recovery
- ✅ Service-specific logging

## 🔧 Development

### Debug Tools

```bash
# PLC connection testing
python tools/debug/test_plc_connection.py

# Database connectivity
python tools/debug/test_supabase_connection.py

# Parameter read/write testing
python tools/debug/test_parameter_read.py
python tools/debug/test_parameter_write.py

# Valve control testing
python tools/debug/test_valve_control.py
```

### Service-Specific Logging

The system uses service-specific logging for better debugging:

```bash
# Monitor specific service logs
tail -f logs/plc.log              # Terminal 1 (PLC Read)
tail -f logs/command_flow.log    # Terminal 2 (Recipe)
tail -f logs/data_collection.log # Terminal 1 data collection
tail -f logs/machine_control.log # Legacy/fallback

# Monitor all errors
tail -f logs/*.log | grep ERROR

# Monitor startup sequence
tail -f logs/machine_control.log logs/command_flow.log logs/plc.log
```

### Code Style

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
python -m pylint --disable=C0103,C0111 --max-line-length=100 *.py
```

## 📊 Database Schema

The system uses a normalized PostgreSQL database with the following key tables:

- `recipes` - Recipe definitions
- `recipe_steps` - Individual recipe steps
- `valve_step_config` - Valve step configurations
- `purge_step_config` - Purge step configurations
- `loop_step_config` - Loop step configurations
- `recipe_parameters` - Recipe-level parameters
- `process_executions` - Process execution records
- `process_execution_state` - Real-time execution state

## 🚦 Operation Modes

### Production Mode

- Real PLC hardware communication
- Full database logging
- Continuous data recording

### Simulation Mode

- Virtual PLC simulation
- Safe testing environment
- Full feature compatibility

### Debug Mode

- Detailed logging
- Step-by-step execution
- Hardware diagnostics

### 3-Terminal Operation

Each terminal can be run independently:

- **Terminal 1 Only**: Just PLC data collection
- **Terminal 2 Only**: Just recipe execution
- **Terminal 3 Only**: Just parameter control
- **All Three**: Complete system operation

## 📖 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [3-Terminal Design](CLAUDE.md) - Complete system documentation
- [Terminal 1 Guide](Terminal_1_PLC_Read_Service_Guide.md)
- [Terminal 2 Guide](Terminal_2_Recipe_Service_Documentation.md)
- [Terminal 3 Guide](Terminal_3_Implementation_Guide.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [API Reference](docs/API.md)
- [Test Reports](docs/reports/)

## 🔒 Configuration

Key configuration options in `.env`:

```bash
# Database
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# PLC Settings
PLC_HOST=192.168.1.100
PLC_PORT=502
PLC_SIMULATION_MODE=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=machine_control.log
```

## Parameter Filtering (Machine-Specific)

For machines that currently include many non-essential parameters in the database, you can enable a
machine-specific allowlist to reduce noise in loading/logging. This is applied only in the real PLC
metadata loader and does not change any database data.

- Enabled by default only for machine `e3e6e280-0794-459f-84d5-5e468f60746e`.
- Other machines remain unaffected unless listed in `ESSENTIALS_FILTER_MACHINE_IDS`.

Kept parameter names:

- `temperature*` (prefix match)
- `flow`, `flow_rate`, `flow_read`, `flow_set`
- `pressure`, `pressure_read`, `pressure_set`
- `power_on`, `power_off`, `power_state`
- `valve_state` only for components named `Valve N` (keeps the 6 process valves)

Ignored examples: `scale_min`, `scale_max`, `scale_min_voltage`, `scale_max_voltage`, `zero_cal`,
`span_cal`, `purity`, and placeholder names (e.g., `ultrathink`).

Environment control (comma-separated list):

```bash
ESSENTIALS_FILTER_MACHINE_IDS=e3e6e280-0794-459f-84d5-5e468f60746e
```

If unset, the filter defaults to the machine above only. To disable everywhere, set it to an empty
value.

## 🏃‍♂️ Commands

### 3-Terminal System Commands

```bash
# Run complete 3-terminal system (3 separate windows)
python main.py --terminal 1 --demo      # Terminal 1: PLC Read
python main.py --terminal 2 --demo      # Terminal 2: Recipe Service
python main.py --terminal 3 --demo      # Terminal 3: Parameter Service

# Or use launcher scripts
python terminal1_launcher.py --demo    # Terminal 1: PLC Read
python terminal2_launcher.py --demo    # Terminal 2: Recipe Service
python terminal3_launcher.py --demo    # Terminal 3: Parameter Service
```

### Testing Commands

```bash
# Test 3-terminal integration
python tests/integration/test_parameter_synchronization.py
python tests/integration/test_parameter_cross_component.py

# Debug PLC connection
python tools/debug/test_plc_connection.py

# Test database connectivity
python tools/debug/test_supabase_connection.py
```

### Database Commands

```bash
# Test database connectivity
python tools/debug/test_supabase_connection.py

# Check recipe data
python tools/debug/test_db_update.py
```

## 🤝 Contributing

1. Follow the 3-terminal architecture pattern
2. Each terminal should operate independently
3. Add tests for new features in `tests/`
4. Use service-specific logging from `src/log_setup.py`
5. Update documentation as needed
6. Use the debug tools for testing hardware integration

## 📝 License

This project is proprietary software for ALD system control.

---

**🔬 Built for precision ALD process control with Python reliability and modern 3-terminal architecture**

## Safety Features

1. **Error Handling**

   - Comprehensive error detection
   - Graceful failure recovery
   - Detailed error logging
   - State preservation during failures
2. **Parameter Validation**

   - Range checking for all parameters
   - Type validation
   - Machine capability verification
   - Recipe step validation

## Real-time Monitoring

1. **Data Collection**

   - Component parameter tracking
   - Process milestone recording
   - Error and warning logging
   - Performance metrics gathering
2. **Process Analytics**

   - Step execution timing
   - Parameter trend analysis
   - Process completion statistics
   - Error pattern detection

## Infrastructure Setup

### PLC Configuration

1. **Network Setup**

   - Static IP configuration
   - Modbus TCP/IP settings
   - Connection security
   - I/O mapping
2. **Program Structure**

   - Component control logic
   - Safety interlocks
   - State management
   - Communication handlers

### Raspberry Pi Setup

1. **System Requirements**

   - Raspberry Pi 4 or later
   - Debian-based Linux OS
   - Python 3.9+
   - Network configuration
2. **Service Installation**

   ```bash
   # Install system dependencies
   sudo apt-get update
   sudo apt-get install -y python3-venv python3-dev

   # Create virtual environment
   python3 -m venv myenv

   # Install Python dependencies
   pip install -r requirements.txt
   ```

### Supabase Configuration

1. **Project Setup**

   - Database initialization
   - Schema creation
   - Authentication setup
   - API key generation
2. **Security Rules**

   - Row-level security
   - API access control
   - User role definitions

### Mobile App Setup

1. **Development Requirements**

   - Flutter SDK
   - Android Studio / Xcode
   - Supabase Flutter SDK
2. **Build Configuration**

   ```bash
   # Install dependencies
   flutter pub get

   # Run app in development
   flutter run
   ```

## Environment Setup

Required environment variables:

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
MACHINE_ID=your_machine_id
PLC_IP=your_plc_ip
PLC_PORT=your_plc_port
```

For testing:

```
TEST_RECIPE_ID=test_recipe_id
TEST_OPERATOR_ID=test_operator_id
```

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv myenv
   ```
3. Activate the virtual environment:
   ```bash
   # On Linux/Mac:
   source myenv/bin/activate
   # On Windows:
   myenv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the System

Start the machine control service:

```bash
python machine_control.py
```

Run tests:

```bash
python test_handle_recipe_start_command.py
python test_recipe_execution_functions.py
```

## Troubleshooting

Common issues and solutions:

1. **Connection Issues**

   - Verify Supabase credentials
   - Check network connectivity
   - Confirm server status
   - Verify PLC connectivity
   - Check Raspberry Pi network
2. **Recipe Execution Errors**

   - Validate recipe parameters
   - Check component availability
   - Verify operator permissions
   - Check PLC status
   - Verify hardware state
3. **State Synchronization**

   - Clear machine state
   - Reset process status
   - Reinitialize connections
   - Verify PLC communication
   - Check Supabase sync
4. **Mobile App Issues**

   - Verify authentication
   - Check internet connectivity
   - Update app version
   - Clear app cache
   - Verify API endpoints
