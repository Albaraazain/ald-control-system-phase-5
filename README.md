# ALD Control System

## Overview
This Atomic Layer Deposition (ALD) control system manages and executes recipes for ALD machines. It provides real-time monitoring, control, and execution of complex deposition processes through a distributed architecture spanning from PLCs to mobile applications.

## Infrastructure Architecture

### System Components

1. **ALD Machine**
   - Physical deposition chamber
   - Process control components (valves, sensors, heaters)
   - Safety interlocks and emergency systems
   - Component-specific controllers

2. **PLC (Programmable Logic Controller)**
   - Direct machine control interface
   - Real-time component state management
   - Safety system monitoring
   - Low-level process execution
   - Component parameter control
   - Hardware I/O management

3. **Raspberry Pi Gateway**
   - Runs the machine control service
   - Bridges PLC and cloud infrastructure
   - Local command processing
   - Real-time data collection
   - State synchronization
   - Offline operation capability
   - Local error handling

4. **Supabase Backend**
   - Real-time database
   - State synchronization
   - Command queue management
   - User authentication
   - Process history storage
   - Analytics data collection
   - API endpoints for mobile/web

5. **Mobile Application**
   - Operator interface
   - Real-time process monitoring
   - Recipe management
   - Machine control
   - Alert notifications
   - Process visualization
   - Historical data access

### Communication Flow

1. **PLC ↔ Raspberry Pi**
   - Modbus TCP/IP communication
   - Real-time component state updates
   - Command execution requests
   - Parameter adjustments
   - Safety state monitoring

2. **Raspberry Pi ↔ Supabase**
   - WebSocket connections for real-time updates
   - REST API for data persistence
   - State synchronization
   - Command queue monitoring
   - Process data recording

3. **Supabase ↔ Mobile App**
   - Real-time subscriptions
   - REST API interactions
   - User authentication
   - Data visualization feeds
   - Command submissions

### Data Flow Architecture

1. **Command Path**
   ```
   Mobile App → Supabase → Raspberry Pi → PLC → Machine
   ```
   - Operator initiates command in mobile app
   - Command queued in Supabase
   - Raspberry Pi processes command
   - PLC executes physical operations
   - State changes reflected back through chain

2. **Monitoring Path**
   ```
   Machine → PLC → Raspberry Pi → Supabase → Mobile App
   ```
   - Machine components report to PLC
   - PLC provides state to Raspberry Pi
   - Raspberry Pi updates Supabase
   - Mobile app receives real-time updates

3. **Process Data Path**
   ```
   Machine → PLC → Raspberry Pi → Supabase → Analytics
   ```
   - Real-time parameter collection
   - Periodic data aggregation
   - Historical data storage
   - Analytics processing

## System Architecture

### Core Components

1. **Machine Control Service**
   - Runs as standalone Python service on Raspberry Pi
   - Maintains real-time connection with Supabase
   - Handles recipe execution and machine state management
   - Records process data points for monitoring and analysis
   - Manages PLC communication

2. **Database Schema**
   - `machines`: Machine registry and status tracking
   - `machine_state`: Real-time machine operational state
   - `recipe_commands`: Command queue for machine operations
   - `process_executions`: Active and historical process runs
   - `operator_sessions`: Operator activity tracking
   - `process_data_points`: Real-time process measurements

### Command Handling System

The system implements a command-based architecture where all operations are executed through a command queue:

1. **Command Types**
   - `start_recipe`: Initiates a new recipe execution
   - `stop_recipe`: Halts an ongoing recipe
   - `set_parameter`: Adjusts machine parameters

2. **Command States**
   - `pending`: New command waiting to be processed
   - `processing`: Command currently being executed
   - `completed`: Command successfully executed
   - `error`: Command failed with error

### Recipe Execution Flow

1. **Recipe Start Process**
   - Validate recipe and operator credentials
   - Create operator session if needed
   - Initialize process execution record
   - Update machine status and state
   - Begin step-by-step execution

2. **Step Types**
   - `purge`: Chamber purging operations
   - `valve`: Valve control operations
   - `set parameter`: Component parameter adjustments
   - `loop`: Repetitive sequence execution

3. **Data Recording**
   - Continuous monitoring of component parameters
   - Recording of process data points
   - State tracking for analysis and troubleshooting

### Machine States

1. **Operational States**
   - `idle`: Ready for new recipe
   - `processing`: Executing recipe
   - `error`: Error condition
   - `offline`: Machine unavailable

2. **State Management**
   - Real-time state tracking
   - Failure mode detection
   - Automatic state recovery
   - Process history maintenance

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