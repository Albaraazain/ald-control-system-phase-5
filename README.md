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

3. **Run the system (with new CLI):**
```bash
# Simulation (demo) mode
python main.py --demo

# Real PLC with explicit IP/port
python main.py --plc real --ip 192.168.1.50 --port 502

# Increase verbosity for debugging
LOG_LEVEL=DEBUG python main.py --demo

# One-shot connectivity check (doctor) and exit
python main.py --doctor
```

### Quick Test
```bash
python tests/integration/test_basic_integration.py
```

## 📁 Project Structure

```
ald-control-system-phase-5/
├── src/                          # Core application
│   ├── main.py                   # Application entry point
│   ├── config.py                 # Configuration management
│   ├── db.py                     # Database client
│   ├── log_setup.py             # Logging setup
│   ├── command_flow/            # Command processing
│   ├── recipe_flow/             # Recipe execution
│   ├── step_flow/               # Step execution
│   └── plc/                     # PLC communication
├── tests/                        # Test suite
│   ├── integration/             # Integration tests
│   ├── unit/                    # Unit tests (future)
│   └── fixtures/                # Test data
├── tools/                        # Development tools
│   ├── debug/                   # Debug utilities
│   └── utilities/               # Helper scripts
├── docs/                         # Documentation
├── requirements.txt
├── pyproject.toml               # Modern Python config
└── .env                         # Environment configuration
```

## 🏗️ Architecture

### Core Components

- **Command Flow** (`src/command_flow/`) - Listens for and processes commands from database
- **Recipe Flow** (`src/recipe_flow/`) - Executes ALD recipes with multiple steps  
- **Step Flow** (`src/step_flow/`) - Handles individual recipe steps (valve, purge, parameter, loop)
- **PLC Communication** (`src/plc/`) - Hardware abstraction layer for PLC operations

### Data Flow

1. **Command Processing**: Supabase → Command Listener → Command Processor → Recipe Execution
2. **Hardware Control**: Recipe Steps → PLC Manager → PLC Interface → Hardware
3. **Data Recording**: PLC Values → Continuous Recorder → Supabase Process Data

## 🧪 Testing

### Run Integration Tests
```bash
# Basic connectivity and database tests
python tests/integration/test_basic_integration.py

# Recipe loading and execution tests  
python tests/integration/test_recipe_execution.py

# Command flow integration tests
python tests/integration/test_command_flow.py

# Comprehensive integration suite
python tests/integration/test_comprehensive.py
```

### Test Coverage
- ✅ Database schema integration
- ✅ Recipe loading and execution
- ✅ Command processing
- ✅ Step configuration loading
- ✅ PLC communication (simulation)
- ✅ Error handling and recovery

## 🔧 Development

### Debug Tools
```bash
# PLC connection testing
python tools/debug/test_plc_connection.py

# Database connectivity
python tools/debug/test_supabase_connection.py

# Valve control testing  
python tools/debug/test_valve_control.py
```

### Code Style
```bash
# Format code
black src/ tests/

# Type checking  
mypy src/

# Linting
flake8 src/ tests/
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

## 📖 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
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

### System Commands
```bash
# Start system
python main.py

# Run specific test
python tests/integration/test_basic_integration.py

# Debug PLC connection
python tools/debug/test_plc_connection.py
```

### Database Commands
```bash
# Test database connectivity
python tools/debug/test_supabase_connection.py

# Check recipe data
python tools/debug/test_db_update.py
```

## 🤝 Contributing

1. Follow the existing code structure under `src/`
2. Add tests for new features in `tests/`
3. Update documentation as needed
4. Use the debug tools for testing hardware integration

## 📝 License

This project is proprietary software for ALD system control.

---

**🔬 Built for precision ALD process control with Python reliability and modern architecture**

## Agents (Headless Runtime)

The service runs as multiple cooperating agents managed by a lightweight supervisor:
- Connection Monitor Agent – maintains PLC connectivity and writes machine health
- Command Listener Agent – subscribes to `recipe_commands` and polls as fallback
- Parameter Control Agent – consumes `parameter_control_commands` (optional for ops/testing)

All agents are asyncio tasks with backoff/restart and clean shutdown.

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
