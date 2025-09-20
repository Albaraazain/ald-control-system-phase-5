# ALD Control System - Universal Setup Guide

This is a comprehensive guide for setting up the **ALD Control System** headless backend (no web UI).

## 🎯 One Universal Environment

Instead of managing multiple virtual environments, this project uses **one comprehensive virtual environment** (`venv/`) that contains everything you need:

- ✅ PLC communication libraries (pymodbus, supabase)
- ✅ Testing and debugging tools
- ✅ Development utilities (pytest, linting, etc.)
- ✅ All project dependencies

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)
```bash
./scripts/setup_environment.sh
```

This will create a virtual environment and install dependencies.

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

## 🛠️ Run the Service

### Main PLC Application  
```bash
# With universal environment active:
python main.py
```
- Production ALD process control
- Recipe execution and monitoring
- Continuous data recording
 
### Debug Scripts
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
├── venv/                          # Virtual environment
├── requirements.txt              # Project dependencies
├── main.py                       # Main PLC application
├── src/                          # Core PLC communication code
│   ├── plc/                     # PLC interface classes
│   ├── config.py                # Configuration
│   └── ...
├── debug/                        # Debug scripts
├── tests/                        # Test suite
└── docs/                         # Documentation
```

## 🔧 Key Features

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

## 💡 Tips

1. **Keep it Simple**: Use one environment for everything
2. **Debug Mode**: Use debug scripts for manual Modbus operations
3. **Safety First**: Always validate purge/valve operations in recipes

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
1. Check logs in `machine_control.log`
2. Run debug scripts to isolate problems
3. Use the address scanner to verify PLC connectivity

---

**Universal Environment = One Setup, All Features! 🎯**
