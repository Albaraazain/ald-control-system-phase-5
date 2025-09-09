#!/usr/bin/env python3
"""
Simple PLC Modbus Debugger
A minimal Streamlit app for testing PLC connections with manual address specification.
No database, no complexity - just direct Modbus testing.
"""

import streamlit as st
from pymodbus.client import ModbusTcpClient
import struct

# Configure Streamlit
st.set_page_config(
    page_title="Simple PLC Debugger", 
    page_icon="🔧",
    layout="wide"
)

# Initialize session state
if 'plc_client' not in st.session_state:
    st.session_state.plc_client = None
if 'connected' not in st.session_state:
    st.session_state.connected = False
if 'logs' not in st.session_state:
    st.session_state.logs = []

def add_log(message, level="INFO"):
    """Add log message"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    st.session_state.logs.append(log_entry)
    if len(st.session_state.logs) > 50:
        st.session_state.logs = st.session_state.logs[-50:]

def connect_plc(ip, port):
    """Connect to PLC"""
    try:
        client = ModbusTcpClient(ip, port=port, timeout=5)
        if client.connect():
            st.session_state.plc_client = client
            st.session_state.connected = True
            add_log(f"Connected to PLC at {ip}:{port}", "SUCCESS")
            return True
        else:
            add_log(f"Failed to connect to {ip}:{port}", "ERROR")
            return False
    except Exception as e:
        add_log(f"Connection error: {str(e)}", "ERROR")
        return False

def disconnect_plc():
    """Disconnect from PLC"""
    if st.session_state.plc_client:
        st.session_state.plc_client.close()
        st.session_state.plc_client = None
        st.session_state.connected = False
        add_log("Disconnected from PLC", "INFO")

def read_modbus(address, modbus_type, count=1):
    """Read from PLC"""
    if not st.session_state.connected:
        return None, "Not connected"
    
    try:
        client = st.session_state.plc_client
        
        if modbus_type == "holding_register":
            result = client.read_holding_registers(address, count=count)
        elif modbus_type == "input_register":
            result = client.read_input_registers(address, count=count)
        elif modbus_type == "coil":
            result = client.read_coils(address, count=count)
        elif modbus_type == "discrete_input":
            result = client.read_discrete_inputs(address, count=count)
        else:
            return None, f"Unknown modbus type: {modbus_type}"
        
        if result.isError():
            error_msg = f"Modbus error: {result}"
            add_log(error_msg, "ERROR")
            return None, error_msg
        
        if modbus_type in ["coil", "discrete_input"]:
            values = result.bits[:count]
            add_log(f"Read {modbus_type} {address}: {values}", "SUCCESS")
            return values, None
        else:
            values = result.registers
            add_log(f"Read {modbus_type} {address}: {values}", "SUCCESS")
            return values, None
            
    except Exception as e:
        error_msg = f"Read error: {str(e)}"
        add_log(error_msg, "ERROR")
        return None, error_msg

def write_modbus(address, modbus_type, value):
    """Write to PLC"""
    if not st.session_state.connected:
        return False, "Not connected"
    
    try:
        client = st.session_state.plc_client
        
        if modbus_type == "holding_register":
            result = client.write_register(address, int(value))
        elif modbus_type == "coil":
            result = client.write_coil(address, bool(value))
        else:
            return False, f"Write not supported for {modbus_type}"
        
        if result.isError():
            error_msg = f"Modbus write error: {result}"
            add_log(error_msg, "ERROR")
            return False, error_msg
        
        add_log(f"Write {modbus_type} {address} = {value}", "SUCCESS")
        return True, None
        
    except Exception as e:
        error_msg = f"Write error: {str(e)}"
        add_log(error_msg, "ERROR")
        return False, error_msg

def read_float(address):
    """Read float (32-bit) from holding registers"""
    values, error = read_modbus(address, "holding_register", count=2)
    if error:
        return None, error
    
    try:
        # Convert to float using 'badc' byte order (common for PLCs)
        raw_data = struct.pack('>HH', values[1], values[0])
        float_value = struct.unpack('>f', raw_data)[0]
        return float_value, None
    except Exception as e:
        return None, f"Float conversion error: {str(e)}"

def write_float(address, value):
    """Write float (32-bit) to holding registers"""
    try:
        # Convert float to registers using 'badc' byte order
        raw_float = struct.pack('>f', float(value))
        high_word, low_word = struct.unpack('>HH', raw_float)
        registers = [low_word, high_word]  # badc order
        
        client = st.session_state.plc_client
        result = client.write_registers(address, registers)
        
        if result.isError():
            error_msg = f"Float write error: {result}"
            add_log(error_msg, "ERROR")
            return False, error_msg
        
        add_log(f"Write float {address} = {value}", "SUCCESS")
        return True, None
        
    except Exception as e:
        error_msg = f"Float write error: {str(e)}"
        add_log(error_msg, "ERROR")
        return False, error_msg

# Main UI
st.title("🔧 Simple PLC Modbus Debugger")
st.markdown("Direct PLC testing - specify address and type manually")

# Connection section
with st.container():
    st.subheader("🔌 PLC Connection")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        plc_ip = st.text_input("PLC IP Address", value="192.168.1.100")
    with col2:
        plc_port = st.number_input("Port", min_value=1, max_value=65535, value=502)
    with col3:
        if st.button("🔗 Connect", disabled=st.session_state.connected):
            if connect_plc(plc_ip, plc_port):
                st.success("Connected!")
                st.rerun()
    with col4:
        if st.button("🔌 Disconnect", disabled=not st.session_state.connected):
            disconnect_plc()
            st.info("Disconnected")
            st.rerun()

# Connection status
if st.session_state.connected:
    st.success("✅ Connected to PLC")
else:
    st.error("❌ Not connected")

st.markdown("---")

# Testing sections
if st.session_state.connected:
    
    # Read section
    st.subheader("📖 Read Operations")
    
    col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
    
    with col1:
        read_address = st.number_input("Address", min_value=0, max_value=65535, value=0, key="read_addr")
    with col2:
        read_type = st.selectbox("Modbus Type", 
                                ["holding_register", "input_register", "coil", "discrete_input"],
                                key="read_type")
    with col3:
        read_count = st.number_input("Count", min_value=1, max_value=125, value=1, key="read_count")
    with col4:
        if st.button("📖 Read"):
            values, error = read_modbus(read_address, read_type, read_count)
            if error:
                st.error(f"Read failed: {error}")
            else:
                st.success(f"Read successful: {values}")
                # Show hex format for registers
                if read_type in ["holding_register", "input_register"] and values:
                    hex_values = [f"0x{val:04x}" for val in values]
                    st.info(f"Hex values: {hex_values}")

    # Float read section
    st.markdown("**🔢 Read Float (32-bit)**")
    col1, col2 = st.columns([1, 1])
    with col1:
        float_read_addr = st.number_input("Float Address", min_value=0, max_value=65535, value=0, key="float_read")
    with col2:
        if st.button("📖 Read Float"):
            float_val, error = read_float(float_read_addr)
            if error:
                st.error(f"Float read failed: {error}")
            else:
                st.success(f"Float value: {float_val}")

    st.markdown("---")

    # Write section  
    st.subheader("✏️ Write Operations")
    
    col1, col2, col3, col4 = st.columns([1, 2, 1, 1])
    
    with col1:
        write_address = st.number_input("Address", min_value=0, max_value=65535, value=0, key="write_addr")
    with col2:
        write_type = st.selectbox("Modbus Type", 
                                 ["holding_register", "coil"],
                                 key="write_type")
    with col3:
        if write_type == "coil":
            write_value = st.selectbox("Value", [0, 1], format_func=lambda x: "OFF" if x == 0 else "ON")
        else:
            write_value = st.number_input("Value", min_value=-32768, max_value=65535, value=0, key="write_val")
    with col4:
        if st.button("✏️ Write"):
            success, error = write_modbus(write_address, write_type, write_value)
            if error:
                st.error(f"Write failed: {error}")
            else:
                st.success("Write successful!")

    # Float write section
    st.markdown("**🔢 Write Float (32-bit)**")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        float_write_addr = st.number_input("Float Address", min_value=0, max_value=65535, value=0, key="float_write_addr")
    with col2:
        float_write_val = st.number_input("Float Value", format="%.6f", key="float_write_val")
    with col3:
        if st.button("✏️ Write Float"):
            success, error = write_float(float_write_addr, float_write_val)
            if error:
                st.error(f"Float write failed: {error}")
            else:
                st.success("Float write successful!")

else:
    st.warning("Connect to PLC first to enable testing operations")

# Logs section
st.markdown("---")
st.subheader("📝 Logs")

if st.session_state.logs:
    logs_text = "\n".join(st.session_state.logs[-20:])  # Show last 20 logs
    st.text_area("Recent logs", value=logs_text, height=200, disabled=True)
    
    if st.button("🗑️ Clear Logs"):
        st.session_state.logs = []
        st.rerun()
else:
    st.info("No logs yet. Perform some operations to generate logs.")