# ALD Control System - Universal Setup Guide

This is a comprehensive guide for setting up the **entire ALD Control System project** including the PLC communication system, Streamlit testing UI, and all development tools.

## 🎯 One Universal Environment

Instead of managing multiple virtual environments, this project uses **one comprehensive virtual environment** (`venv/`) that contains everything you need:

- ✅ PLC communication libraries (pymodbus, supabase)
- ✅ Streamlit UI framework and components  
- ✅ Testing and debugging tools
- ✅ Development utilities (pytest, linting, etc.)
- ✅ All project dependencies

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)
```bash
# Make the launcher executable
chmod +x run_streamlit.sh

# Run the universal launcher
./run_streamlit.sh
```

This will:
1. Create universal `venv/` environment
2. Install all project dependencies
3. Give you options to run different parts of the system

### Option 2: Manual Setup
```bash
# Create universal virtual environment
python -m venv venv

# Activate it
source venv/bin/activate

# Install all dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Optional: Install development tools
pip install pytest pytest-asyncio black flake8 mypy
```

## 🛠️ Available Applications

Once your environment is set up, you can run any part of the system:

### 1. Streamlit PLC Testing UI
```bash
# With universal environment active:
streamlit run streamlit_plc_tester.py
```
- **Manual Modbus debugging** with address/type specification
- Parameter browser and read/write operations  
- Valve control interface
- Purge operations with safety controls
- Live logging and status monitoring

### 2. Main PLC Application  
```bash
# With universal environment active:
python main.py
```
- Production ALD process control
- Recipe execution and monitoring
- Continuous data recording

### 3. Debug Scripts
```bash
# With universal environment active:
python debug/test_plc_connection.py
python debug/test_valve_control.py
# ... and other debug scripts
```

### 4. Testing Suite
```bash
# With universal environment active:
pytest tests/
```

## 📁 Project Structure

```
ald-control-system-phase-5/
├── venv/                          # Universal virtual environment
├── run_streamlit.sh              # Universal launcher script
├── requirements.txt              # All project dependencies
├── streamlit_plc_tester.py       # Streamlit UI application
├── main.py                       # Main PLC application
├── src/                          # Core PLC communication code
│   ├── plc/                     # PLC interface classes
│   ├── config.py                # Configuration
│   └── ...
├── debug/                        # Debug scripts
├── tests/                        # Test suite
└── docs/                         # Documentation
```

## 🔧 Key Features of Streamlit UI

### Manual Modbus Debugging
- **Raw Read**: Specify exact address + type (holding_register, coil, etc.)
- **Raw Write**: Manual address/type specification with verification
- **Address Scanner**: Discover responsive devices in address ranges

### Parameter Operations
- Search/filter parameters from database
- Individual and batch read/write operations
- Real-time value monitoring with automatic updates
- CSV export functionality

### Valve Control
- Individual valve control (open/close/timed)
- Batch operations (open all, close all)
- State monitoring and verification

### Safety Features
- Input validation and range checking
- Safety confirmations for dangerous operations
- Error handling with detailed logging
- Connection status monitoring

## 🌐 Access the UI

Once Streamlit is running:
- **Local**: http://localhost:8501
- **Network**: http://0.0.0.0:8501 (accessible from other devices)

## 💡 Tips

1. **Keep it Simple**: Use one environment for everything - no need to switch between multiple venvs
2. **Debug Mode**: Use the Debug Console in Streamlit for manual Modbus operations
3. **Safety First**: Always use the safety confirmations for purge operations
4. **Live Monitoring**: The Parameters page updates values in real-time
5. **CSV Export**: Export parameter data for analysis

## 🔍 Troubleshooting

### Connection Issues
- Check PLC IP address and port settings
- Use auto-discovery feature for DHCP environments  
- Verify network connectivity with address scanner

### Missing Dependencies
```bash
# Re-run full installation
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Import Errors
- Make sure `venv` is activated: `source venv/bin/activate`
- Check that `src/` directory is in Python path

## 📞 Support

For issues or questions:
1. Check the debug console logs in Streamlit
2. Run debug scripts to isolate problems
3. Use the address scanner to verify PLC connectivity

---

**Universal Environment = One Setup, All Features! 🎯**