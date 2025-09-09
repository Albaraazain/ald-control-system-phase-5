# ALD Control System - Easy Launcher Guide

This document explains how to easily run the different components of the ALD Control System.

## Quick Start

### 1. First Time Setup
```bash
./launcher.sh
```
The launcher will automatically set up your environment if needed.

### 2. Manual Setup (if needed)
```bash
./scripts/setup_environment.sh
```

### 3. Create .env file
Create a `.env` file in the root directory with your Supabase credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

## Available Components

### 🖥️ Main ALD Control Service (Backend)
- **Script**: `./scripts/start_main_service.sh`
- **Purpose**: Main system service that handles commands, recipes, and parameter control
- **Includes**: Command flow listener, recipe executor, parameter control listener

### 🎛️ Parameter Control UI
- **Script**: `./scripts/start_parameter_control_ui.sh`
- **Port**: 8501
- **URL**: http://localhost:8501
- **Purpose**: Web interface for testing parameter control (pump, nitrogen generator, MFC values)

### 🔧 PLC Tester UI  
- **Script**: `./scripts/start_plc_tester.sh`
- **Port**: 8502
- **URL**: http://localhost:8502
- **Purpose**: Comprehensive PLC testing interface

### 🐛 Simple PLC Debug UI
- **Script**: `./scripts/start_plc_debug.sh` 
- **Port**: 8503
- **URL**: http://localhost:8503
- **Purpose**: Simple debugging interface for PLC operations

## Usage Patterns

### For Development
1. Start the main service: `./scripts/start_main_service.sh`
2. In another terminal, start the UI you need:
   - Parameter testing: `./scripts/start_parameter_control_ui.sh`
   - PLC testing: `./scripts/start_plc_tester.sh`

### For Testing All UIs
Use the launcher to start all UIs at once:
```bash
./launcher.sh
# Select option 5 to start all UIs
```

### For Production
1. Ensure `.env` file is properly configured
2. Start main service: `./scripts/start_main_service.sh`
3. Access UIs as needed on their respective ports

## File Structure
```
.
├── launcher.sh                 # Interactive launcher
├── requirements.txt            # Unified dependencies
├── scripts/
│   ├── setup_environment.sh    # Environment setup
│   ├── start_main_service.sh   # Main ALD service
│   ├── start_parameter_control_ui.sh
│   ├── start_plc_tester.sh
│   └── start_plc_debug.sh
├── src/                        # Main source code
├── parameter_control_ui.py     # Parameter control Streamlit app
├── streamlit_plc_tester.py     # PLC tester Streamlit app
└── simple_plc_debug.py         # Simple debug Streamlit app
```

## Troubleshooting

### Port Already in Use
If you get "port already in use" errors:
1. Use the launcher option 6 to check running services
2. Use option 7 to stop all services
3. Or manually kill processes: `pkill streamlit`

### Missing Dependencies
Run the setup script:
```bash
./scripts/setup_environment.sh
```

### Database Connection Issues
1. Check your `.env` file has correct Supabase credentials
2. Ensure your Supabase project is running
3. Check network connectivity

## Real Machine Addresses
The parameter control UI is configured with these real machine modbus addresses:
- Pressure Gauge: 2072 (coil)
- Exhaust: 11 (coil) 
- N2 Generator: 37 (coil)
- Pump: 10 (coil)
- MFC Setpoint: 2066 (holding register)
- MFC Current Value: 2082 (input register)