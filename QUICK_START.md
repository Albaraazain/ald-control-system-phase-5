# 🧪 ALD Control System - Quick Start Guide

## **🎯 Simple & Organized Startup**

Everything is now organized with simple scripts. No more confusion!

### **📋 Start the System**

```bash
./start_ald_system.sh
```

**Choose your option:**
1. **Main Service** – Headless backend
2. **Test PLC Connection** – Quick connectivity test
3. **Run Diagnostics** – System health check

### **🛑 Stop the System**

```bash
./stop_ald_system.sh
```

## **🏗️ Simple Architecture**

```
ALD Control System
├── Main Service (python main.py)
│   ├── PLC Connection (169.254.123.6)
│   ├── Supabase Integration
│   └── Command Processing
│
└── Diagnostics
    ├── Doctor script
    └── CLI tests
```

## **🎛️ Usage Patterns**

### **For Development:**
```bash
./start_ald_system.sh
# Choose option 1 (Main Service)
```

### **For Production:**
```bash
./start_ald_system.sh
# Choose option 1 (Main Service)
```

### **For Testing:**
```bash
./start_ald_system.sh
# Choose option 2 (Test PLC Connection)
# Quick connection test
```

## **📊 What Each Component Does**

| Component | Purpose |
|-----------|---------|
| **Main Service** | PLC control, command processing |
| **Diagnostics** | Connectivity and health checks |

## **🔧 Configuration**

Edit `.env` file:
```bash
PLC_TYPE=real               # or 'simulation'
PLC_IP=169.254.123.6       # Your PLC IP
MACHINE_ID=your-machine-id
```

## **🚨 Troubleshooting**

### **Can't connect to PLC?**
```bash
./start_ald_system.sh
# Choose option 4 (Test PLC Connection)
```

### **System not responding?**
```bash
./stop_ald_system.sh
./start_ald_system.sh
```

### **Check logs:**
```bash
tail -f main_service.log     # Main service logs
tail -f machine_control.log  # PLC operation logs
```

## **🎯 Quick Commands**

```bash
# Start everything
./start_ald_system.sh

# Stop everything
./stop_ald_system.sh

# Test PLC connection
python tools/plc_cli/plc_cli.py connect-test

# Run diagnostics
bash scripts/doctor.sh
```

**That's it! Simple and organized.** 🚀
