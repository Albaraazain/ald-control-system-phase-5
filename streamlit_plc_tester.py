#!/usr/bin/env python3
"""
ALD Control System PLC Testing Interface
A comprehensive Streamlit application for testing and debugging PLC operations.

Created using Claude Code orchestration with specialized agents.
"""

import streamlit as st
import asyncio
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Add src directory to Python path for imports
sys.path.insert(0, 'src')

try:
    from src.plc.manager import plc_manager
    from src.config import PLC_CONFIG
except ImportError as e:
    st.error(f"Failed to import PLC modules: {e}")
    st.stop()

# Configure Streamlit page
st.set_page_config(
    page_title="ALD PLC Testing Interface",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stButton > button {
        width: 100%;
    }
    .status-connected {
        color: green;
        font-weight: bold;
    }
    .status-disconnected {
        color: red;
        font-weight: bold;
    }
    .status-connecting {
        color: orange;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
def initialize_session_state():
    """Initialize all session state variables."""
    defaults = {
        'plc_connected': False,
        'plc_manager_instance': None,
        'loaded_parameters': {},
        'loaded_valves': {},
        'current_parameter': None,
        'ui_logs': [],
        'last_error': None,
        'connection_status': 'Disconnected',
        'current_page': 'Connection'
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def add_log(message: str, level: str = "INFO"):
    """Add a log entry to the UI logs."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    st.session_state.ui_logs.append(log_entry)
    
    # Keep only last 100 log entries
    if len(st.session_state.ui_logs) > 100:
        st.session_state.ui_logs = st.session_state.ui_logs[-100:]

def run_async(coro):
    """Run async coroutine in a sync context for Streamlit."""
    try:
        return asyncio.run(coro)
    except Exception as e:
        add_log(f"Async operation failed: {str(e)}", "ERROR")
        st.session_state.last_error = str(e)
        return None

async def connect_plc_async(ip: str, port: int, hostname: str = None, auto_discover: bool = False):
    """Async function to connect to PLC."""
    try:
        config = {
            'ip_address': ip,
            'port': port,
            'hostname': hostname if hostname else None,
            'auto_discover': auto_discover
        }
        
        # Initialize PLC manager with real PLC
        success = await plc_manager.initialize('real', config)
        
        if success:
            # Store the manager instance
            st.session_state.plc_manager_instance = plc_manager
            
            # Load parameters from PLC after successful connection
            if hasattr(plc_manager.plc, '_parameter_cache'):
                st.session_state.loaded_parameters = plc_manager.plc._parameter_cache.copy()
                add_log(f"Loaded {len(st.session_state.loaded_parameters)} parameters from PLC")
            
            if hasattr(plc_manager.plc, '_valve_cache'):
                st.session_state.loaded_valves = plc_manager.plc._valve_cache.copy()
                add_log(f"Loaded {len(st.session_state.loaded_valves)} valve mappings")
            
            return True
        return False
        
    except Exception as e:
        st.session_state.last_error = f"Connection failed: {str(e)}"
        return False

async def disconnect_plc_async():
    """Async function to disconnect from PLC."""
    try:
        success = await plc_manager.disconnect()
        if success:
            st.session_state.plc_manager_instance = None
            st.session_state.loaded_parameters = {}
            st.session_state.loaded_valves = {}
        return success
    except Exception as e:
        st.session_state.last_error = f"Disconnect failed: {str(e)}"
        return False

def render_connection_panel():
    """Render the PLC connection panel in the sidebar."""
    with st.sidebar.expander("🔌 PLC Connection", expanded=True):
        # Connection inputs
        ip_address = st.text_input(
            "PLC IP Address", 
            value=PLC_CONFIG.get('ip_address', '192.168.1.100'),
            key='plc_ip'
        )
        
        port = st.number_input(
            "Port", 
            min_value=1, 
            max_value=65535, 
            value=PLC_CONFIG.get('port', 502),
            key='plc_port'
        )
        
        hostname = st.text_input(
            "Hostname (optional)", 
            placeholder="e.g., plc.local",
            help="For DHCP environments",
            key='plc_hostname'
        )
        
        auto_discover = st.checkbox(
            "Enable Auto-Discovery", 
            help="Scan network if hostname fails",
            key='auto_discover'
        )
        
        # Connection buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔗 Connect", type="primary", disabled=st.session_state.plc_connected):
                st.session_state.connection_status = 'Connecting'
                add_log(f"Attempting to connect to {ip_address}:{port}")
                
                success = run_async(connect_plc_async(
                    ip_address, port, hostname if hostname else None, auto_discover
                ))
                
                if success:
                    st.session_state.plc_connected = True
                    st.session_state.connection_status = 'Connected'
                    add_log("Successfully connected to PLC", "SUCCESS")
                    st.success("Connected to PLC!")
                    st.rerun()
                else:
                    st.session_state.connection_status = 'Error'
                    add_log("Failed to connect to PLC", "ERROR")
                    st.error(f"Connection failed: {st.session_state.last_error}")
        
        with col2:
            if st.button("🔌 Disconnect", disabled=not st.session_state.plc_connected):
                st.session_state.connection_status = 'Disconnecting'
                add_log("Disconnecting from PLC")
                
                success = run_async(disconnect_plc_async())
                
                if success:
                    st.session_state.plc_connected = False
                    st.session_state.connection_status = 'Disconnected'
                    add_log("Successfully disconnected from PLC", "SUCCESS")
                    st.success("Disconnected from PLC!")
                    st.rerun()
                else:
                    add_log("Error during disconnect", "ERROR")
                    st.error("Error during disconnect")

def render_status_dashboard():
    """Render the system status dashboard in the sidebar."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 System Status")
    
    # Connection status with emoji
    status_map = {
        'Connected': '🟢 Connected',
        'Disconnected': '🔴 Disconnected', 
        'Connecting': '🟡 Connecting',
        'Disconnecting': '🟡 Disconnecting',
        'Error': '⚠️ Error'
    }
    
    status_display = status_map.get(st.session_state.connection_status, '❓ Unknown')
    st.sidebar.markdown(f"**Status:** {status_display}")
    
    # Parameters and valves count
    param_count = len(st.session_state.loaded_parameters)
    valve_count = len(st.session_state.loaded_valves)
    
    st.sidebar.metric("Parameters Loaded", param_count)
    st.sidebar.metric("Valves Available", valve_count)
    
    # Last error display
    if st.session_state.last_error:
        st.sidebar.error(f"Last Error: {st.session_state.last_error[:50]}...")

def render_navigation_menu():
    """Render the main navigation menu."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🧭 Navigation")
    
    pages = [
        ("🏠", "Connection", "Connection and status overview"),
        ("📊", "Parameters", "Browse and edit PLC parameters"),
        ("🚰", "Valves", "Control valve operations"),
        ("🌪️", "Purge", "Purge system operations"),
        ("🔧", "Debug", "Low-level Modbus debugging"),
        ("📈", "Batch", "Bulk parameter operations"),
        ("📝", "Logs", "Live system logs")
    ]
    
    for icon, page_name, description in pages:
        if st.sidebar.button(f"{icon} {page_name}", help=description):
            st.session_state.current_page = page_name
            st.rerun()

def render_main_content():
    """Render the main content area based on selected page."""
    current_page = st.session_state.current_page
    
    if current_page == "Connection":
        render_connection_overview()
    elif current_page == "Parameters":
        render_parameters_page()
    elif current_page == "Valves":
        render_valves_page()
    elif current_page == "Purge":
        render_purge_page()
    elif current_page == "Debug":
        render_debug_page()
    elif current_page == "Batch":
        render_batch_page()
    elif current_page == "Logs":
        render_logs_page()

def render_connection_overview():
    """Render the connection overview page."""
    st.header("🏠 ALD PLC Testing Interface")
    st.markdown("Welcome to the comprehensive PLC testing and debugging interface.")
    
    if not st.session_state.plc_connected:
        st.warning("⚠️ Not connected to PLC. Use the connection panel in the sidebar to connect.")
        
        st.markdown("""
        ### Getting Started
        1. **Connect to PLC**: Use the connection panel in the sidebar
        2. **Browse Parameters**: Navigate to the Parameters page to view available parameters
        3. **Control Valves**: Use the Valves page for valve operations
        4. **Debug Operations**: Use the Debug page for low-level Modbus testing
        """)
    else:
        st.success("✅ Connected to PLC - Ready for operations!")
        
        # Show some basic system info
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Connection Status", "Active", delta="Connected")
        
        with col2:
            st.metric("Parameters", len(st.session_state.loaded_parameters))
        
        with col3:
            st.metric("Valves", len(st.session_state.loaded_valves))

def render_parameters_page():
    """Render the parameters browser page."""
    st.header("📊 Parameter Browser")
    
    if not st.session_state.plc_connected:
        st.warning("Please connect to PLC first")
        return
    
    # Parameter search and filters
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        search_term = st.text_input(
            "🔍 Search parameters", 
            placeholder="Search by name, component, or description...",
            key="param_search"
        )
    
    with col2:
        data_type_filter = st.selectbox(
            "Data Type",
            options=["All", "float", "int32", "int16", "binary"],
            key="data_type_filter"
        )
    
    with col3:
        writable_filter = st.selectbox(
            "Access",
            options=["All", "Writable", "Read-only"],
            key="writable_filter"
        )
    
    # Filter parameters based on search criteria
    filtered_params = filter_parameters(search_term, data_type_filter, writable_filter)
    
    if not filtered_params:
        st.info("No parameters found matching your criteria. Try connecting to PLC first or adjusting filters.")
        return
    
    st.markdown(f"**Found {len(filtered_params)} parameters**")
    
    # Batch operations
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📖 Read All Visible", help="Read current values for all filtered parameters"):
            asyncio.run(read_all_parameters(list(filtered_params.keys())))
    
    with col2:
        if st.button("🔄 Refresh Parameters", help="Reload parameter metadata from database"):
            refresh_parameter_cache()
    
    with col3:
        csv_data = prepare_csv_export(filtered_params)
        st.download_button(
            "💾 Export CSV",
            data=csv_data,
            file_name=f"plc_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # Parameter list with operations
    for param_id, param_data in filtered_params.items():
        render_parameter_card(param_id, param_data)

def render_valves_page():
    """Render the valve control page."""
    st.header("🚰 Valve Control Center")
    
    if not st.session_state.plc_connected:
        st.warning("Please connect to PLC first")
        return
    
    if not st.session_state.loaded_valves:
        st.info("No valve mappings loaded. Make sure PLC connection loaded valve configurations.")
        if st.button("🔄 Refresh Valve Mappings"):
            refresh_valve_cache()
        return
    
    st.markdown(f"**Available valves: {len(st.session_state.loaded_valves)}**")
    
    # Valve selection and control
    valve_options = [(str(num), f"Valve {num}") for num in sorted(st.session_state.loaded_valves.keys())]
    
    if valve_options:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            selected_valve = st.selectbox(
                "Select Valve",
                options=[opt[0] for opt in valve_options],
                format_func=lambda x: next(opt[1] for opt in valve_options if opt[0] == x),
                key="selected_valve"
            )
        
        with col2:
            valve_num = int(selected_valve)
            render_valve_control_panel(valve_num)
    
    st.markdown("---")
    
    # Batch valve operations
    st.markdown("### 🔧 Batch Valve Operations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🟢 Open All Valves"):
            asyncio.run(batch_valve_operation(True))
    
    with col2:
        if st.button("🔴 Close All Valves"):
            asyncio.run(batch_valve_operation(False))
    
    with col3:
        if st.button("📊 Check All States"):
            asyncio.run(check_all_valve_states())

def render_valve_control_panel(valve_num: int):
    """Render control panel for a specific valve."""
    st.markdown(f"**Valve {valve_num} Control**")
    
    # Current state display (if available)
    valve_info = st.session_state.loaded_valves.get(valve_num, {})
    current_state = valve_info.get('current_state', 'Unknown')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        state_color = "🟢" if current_state else "🔴" if current_state is False else "❓"
        st.metric("Current State", f"{state_color} {'Open' if current_state else 'Closed' if current_state is False else 'Unknown'}")
    
    with col2:
        if st.button(f"🟢 Open Valve {valve_num}", key=f"open_{valve_num}"):
            asyncio.run(control_single_valve(valve_num, True))
    
    with col3:
        if st.button(f"🔴 Close Valve {valve_num}", key=f"close_{valve_num}"):
            asyncio.run(control_single_valve(valve_num, False))
    
    # Timed operations
    st.markdown("**⏱️ Timed Operation**")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        duration_ms = st.number_input(
            "Duration (milliseconds)",
            min_value=100,
            max_value=60000,
            value=1000,
            step=100,
            key=f"duration_{valve_num}"
        )
    
    with col2:
        if st.button(f"⏱️ Timed Open", key=f"timed_{valve_num}"):
            asyncio.run(control_single_valve(valve_num, True, duration_ms))

async def control_single_valve(valve_num: int, state: bool, duration_ms: int = None):
    """Control a single valve."""
    try:
        action = "Opening" if state else "Closing"
        duration_text = f" for {duration_ms}ms" if duration_ms else ""
        add_log(f"{action} valve {valve_num}{duration_text}", "INFO")
        
        if not st.session_state.plc_manager_instance:
            raise RuntimeError("Not connected to PLC")
        
        success = await st.session_state.plc_manager_instance.control_valve(valve_num, state, duration_ms)
        
        if success:
            # Update cached state
            if valve_num in st.session_state.loaded_valves:
                st.session_state.loaded_valves[valve_num]['current_state'] = state
            
            action_past = "Opened" if state else "Closed"
            add_log(f"Successfully {action_past.lower()} valve {valve_num}", "SUCCESS")
            st.success(f"Valve {valve_num} {action_past.lower()} successfully!")
        else:
            raise RuntimeError("Valve operation returned False")
            
    except Exception as e:
        error_msg = f"Failed to control valve {valve_num}: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

async def batch_valve_operation(state: bool):
    """Perform batch valve operation."""
    valve_count = len(st.session_state.loaded_valves)
    success_count = 0
    action = "Opening" if state else "Closing"
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, valve_num in enumerate(sorted(st.session_state.loaded_valves.keys())):
        try:
            status_text.text(f"{action} valve {i+1}/{valve_count}: Valve {valve_num}")
            
            success = await st.session_state.plc_manager_instance.control_valve(valve_num, state)
            if success:
                st.session_state.loaded_valves[valve_num]['current_state'] = state
                success_count += 1
            
        except Exception as e:
            add_log(f"Failed to control valve {valve_num}: {str(e)}", "ERROR")
        
        progress_bar.progress((i + 1) / valve_count)
    
    progress_bar.empty()
    status_text.empty()
    
    action_past = "opened" if state else "closed"
    add_log(f"Batch valve operation completed: {success_count}/{valve_count} valves {action_past}", "INFO")
    st.success(f"{action_past.title()} {success_count} out of {valve_count} valves")

async def check_all_valve_states():
    """Check the current state of all valves."""
    st.info("Valve state checking requires reading valve status parameters - this feature depends on the specific PLC configuration.")
    add_log("Valve state checking requested (requires specific PLC parameter mapping)", "INFO")

def refresh_valve_cache():
    """Refresh valve mappings from the PLC."""
    if st.session_state.plc_manager_instance and hasattr(st.session_state.plc_manager_instance.plc, '_valve_cache'):
        st.session_state.loaded_valves = st.session_state.plc_manager_instance.plc._valve_cache.copy()
        add_log(f"Refreshed {len(st.session_state.loaded_valves)} valve mappings from PLC", "INFO")
        st.success("Valve mappings refreshed!")
    else:
        st.warning("No PLC connection or valve cache available")

def render_purge_page():
    """Render the purge operations page."""
    st.header("🌪️ Purge Operations")
    
    if not st.session_state.plc_connected:
        st.warning("Please connect to PLC first")
        return
    
    st.markdown("**Purge System Control**")
    st.info("⚠️ Ensure all safety protocols are followed before initiating purge operations.")
    
    # Purge duration input
    col1, col2 = st.columns([2, 1])
    
    with col1:
        duration_ms = st.number_input(
            "Purge Duration (milliseconds)",
            min_value=1000,
            max_value=300000,  # 5 minutes max
            value=5000,
            step=1000,
            help="Duration for purge operation in milliseconds"
        )
        
        duration_seconds = duration_ms / 1000
        st.caption(f"Duration: {duration_seconds:.1f} seconds")
    
    with col2:
        st.markdown("**Safety Check**")
        safety_confirmed = st.checkbox(
            "⚠️ Safety protocols confirmed",
            help="Confirm that all safety measures are in place"
        )
    
    # Purge operation buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🌪️ Start Purge", disabled=not safety_confirmed):
            asyncio.run(execute_purge_operation(duration_ms))
    
    with col2:
        if st.button("⏹️ Emergency Stop"):
            asyncio.run(emergency_stop_purge())
    
    with col3:
        if st.button("📊 Check Purge Status"):
            check_purge_status()
    
    # Purge presets
    st.markdown("---")
    st.markdown("**🎛️ Quick Presets**")
    
    preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
    
    with preset_col1:
        if st.button("Short Purge\n(2s)", disabled=not safety_confirmed):
            asyncio.run(execute_purge_operation(2000))
    
    with preset_col2:
        if st.button("Standard Purge\n(10s)", disabled=not safety_confirmed):
            asyncio.run(execute_purge_operation(10000))
    
    with preset_col3:
        if st.button("Long Purge\n(30s)", disabled=not safety_confirmed):
            asyncio.run(execute_purge_operation(30000))
    
    with preset_col4:
        if st.button("Extended Purge\n(60s)", disabled=not safety_confirmed):
            asyncio.run(execute_purge_operation(60000))

async def execute_purge_operation(duration_ms: int):
    """Execute a purge operation."""
    try:
        duration_seconds = duration_ms / 1000
        add_log(f"Starting purge operation for {duration_seconds:.1f} seconds", "INFO")
        
        if not st.session_state.plc_manager_instance:
            raise RuntimeError("Not connected to PLC")
        
        # Show progress during purge
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Start purge operation
        success = await st.session_state.plc_manager_instance.execute_purge(duration_ms)
        
        if success:
            add_log(f"Purge operation completed successfully ({duration_seconds:.1f}s)", "SUCCESS")
            st.success(f"Purge operation completed! Duration: {duration_seconds:.1f} seconds")
        else:
            raise RuntimeError("Purge operation returned False")
            
        progress_bar.empty()
        status_text.empty()
        
    except Exception as e:
        error_msg = f"Failed to execute purge operation: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

async def emergency_stop_purge():
    """Emergency stop for purge operations."""
    try:
        add_log("Emergency stop requested for purge operation", "WARNING")
        
        # Implementation depends on PLC-specific emergency stop procedures
        # This might involve setting specific emergency stop parameters or valves
        st.warning("Emergency stop requested - this requires PLC-specific implementation")
        add_log("Emergency stop procedure requires PLC-specific parameter configuration", "INFO")
        
    except Exception as e:
        error_msg = f"Failed to execute emergency stop: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

def check_purge_status():
    """Check current purge system status."""
    add_log("Purge status check requested", "INFO")
    st.info("Purge status checking requires specific PLC parameter monitoring - implementation depends on system configuration")

def render_debug_page():
    """Render the debug console page."""
    st.header("🔧 Debug Console")
    
    if not st.session_state.plc_connected:
        st.warning("Please connect to PLC first")
        return
    
    st.markdown("**Low-Level Modbus Operations**")
    st.warning("⚠️ Advanced debugging tools - use with caution!")
    
    # Raw Modbus operations
    tab1, tab2, tab3 = st.tabs(["📖 Raw Read", "✏️ Raw Write", "🔍 Address Scanner"])
    
    with tab1:
        render_raw_read_interface()
    
    with tab2:
        render_raw_write_interface()
    
    with tab3:
        render_address_scanner_interface()

def render_raw_read_interface():
    """Render raw Modbus read interface."""
    st.markdown("**Direct Modbus Read Operations**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        modbus_type = st.selectbox(
            "Modbus Function",
            options=["holding_register", "input_register", "coil", "discrete_input"],
            key="debug_read_type"
        )
    
    with col2:
        start_address = st.number_input(
            "Start Address",
            min_value=0,
            max_value=65535,
            value=0,
            key="debug_read_address"
        )
    
    with col3:
        count = st.number_input(
            "Count",
            min_value=1,
            max_value=125,
            value=1,
            key="debug_read_count"
        )
    
    if st.button("📖 Execute Raw Read"):
        asyncio.run(execute_raw_read(modbus_type, start_address, count))

def render_raw_write_interface():
    """Render raw Modbus write interface."""
    st.markdown("**Direct Modbus Write Operations**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        write_type = st.selectbox(
            "Write Type",
            options=["holding_register", "coil"],
            key="debug_write_type"
        )
    
    with col2:
        write_address = st.number_input(
            "Address",
            min_value=0,
            max_value=65535,
            value=0,
            key="debug_write_address"
        )
    
    if write_type == "coil":
        write_value = st.selectbox("Value", options=[True, False], key="debug_write_coil_value")
    else:
        write_value = st.number_input(
            "Value",
            min_value=-32768,
            max_value=65535,
            value=0,
            key="debug_write_register_value"
        )
    
    if st.button("✏️ Execute Raw Write", type="primary"):
        asyncio.run(execute_raw_write(write_type, write_address, write_value))

def render_address_scanner_interface():
    """Render address scanner interface."""
    st.markdown("**Modbus Address Scanner**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        scan_type = st.selectbox(
            "Scan Type",
            options=["holding_register", "input_register", "coil", "discrete_input"],
            key="scan_type"
        )
    
    with col2:
        scan_start = st.number_input(
            "Start Address",
            min_value=0,
            max_value=65535,
            value=0,
            key="scan_start"
        )
    
    with col3:
        scan_end = st.number_input(
            "End Address",
            min_value=0,
            max_value=65535,
            value=99,
            key="scan_end"
        )
    
    if st.button("🔍 Scan Address Range"):
        if scan_end > scan_start:
            asyncio.run(scan_address_range(scan_type, scan_start, scan_end))
        else:
            st.error("End address must be greater than start address")

async def execute_raw_read(modbus_type: str, address: int, count: int):
    """Execute raw Modbus read operation."""
    try:
        add_log(f"Raw read: {modbus_type} address {address}, count {count}", "INFO")
        
        if not st.session_state.plc_manager_instance or not hasattr(st.session_state.plc_manager_instance.plc, 'communicator'):
            raise RuntimeError("PLC communicator not available")
        
        communicator = st.session_state.plc_manager_instance.plc.communicator
        
        if modbus_type == "holding_register":
            result = communicator.client.read_holding_registers(address, count=count)
        elif modbus_type == "input_register":
            result = communicator.client.read_input_registers(address, count=count)
        elif modbus_type == "coil":
            result = communicator.client.read_coils(address, count=count)
        elif modbus_type == "discrete_input":
            result = communicator.client.read_discrete_inputs(address, count=count)
        else:
            raise ValueError(f"Unknown modbus type: {modbus_type}")
        
        if not result.isError():
            if modbus_type in ["coil", "discrete_input"]:
                values = result.bits[:count]
                st.success(f"Read successful: {values}")
                add_log(f"Raw read result: {values}", "SUCCESS")
            else:
                values = result.registers
                st.success(f"Read successful: {values}")
                add_log(f"Raw read result: {values}", "SUCCESS")
                
                # Also show as hex
                hex_values = [f"0x{val:04x}" for val in values]
                st.info(f"Hex values: {hex_values}")
        else:
            raise RuntimeError(f"Modbus error: {result}")
            
    except Exception as e:
        error_msg = f"Raw read failed: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

async def execute_raw_write(write_type: str, address: int, value):
    """Execute raw Modbus write operation."""
    try:
        add_log(f"Raw write: {write_type} address {address} = {value}", "INFO")
        
        if not st.session_state.plc_manager_instance or not hasattr(st.session_state.plc_manager_instance.plc, 'communicator'):
            raise RuntimeError("PLC communicator not available")
        
        communicator = st.session_state.plc_manager_instance.plc.communicator
        
        if write_type == "holding_register":
            result = communicator.client.write_register(address, value)
        elif write_type == "coil":
            result = communicator.client.write_coil(address, value)
        else:
            raise ValueError(f"Write not supported for type: {write_type}")
        
        if not result.isError():
            st.success(f"Write successful: {write_type} address {address} = {value}")
            add_log(f"Raw write successful", "SUCCESS")
            
            # Auto-read back to verify
            await asyncio.sleep(0.1)
            if write_type == "holding_register":
                verify_result = communicator.client.read_holding_registers(address, count=1)
                if not verify_result.isError():
                    read_back = verify_result.registers[0]
                    if read_back == value:
                        st.success(f"✅ Write verified: {read_back}")
                    else:
                        st.warning(f"⚠️ Write verification: wrote {value}, read {read_back}")
            elif write_type == "coil":
                verify_result = communicator.client.read_coils(address, count=1)
                if not verify_result.isError():
                    read_back = verify_result.bits[0]
                    if read_back == value:
                        st.success(f"✅ Write verified: {read_back}")
                    else:
                        st.warning(f"⚠️ Write verification: wrote {value}, read {read_back}")
        else:
            raise RuntimeError(f"Modbus error: {result}")
            
    except Exception as e:
        error_msg = f"Raw write failed: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

async def scan_address_range(scan_type: str, start_addr: int, end_addr: int):
    """Scan a range of Modbus addresses."""
    try:
        add_log(f"Scanning {scan_type} addresses {start_addr}-{end_addr}", "INFO")
        
        if not st.session_state.plc_manager_instance or not hasattr(st.session_state.plc_manager_instance.plc, 'communicator'):
            raise RuntimeError("PLC communicator not available")
        
        communicator = st.session_state.plc_manager_instance.plc.communicator
        total_addresses = end_addr - start_addr + 1
        found_addresses = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for addr in range(start_addr, end_addr + 1):
            status_text.text(f"Scanning address {addr} ({addr - start_addr + 1}/{total_addresses})")
            
            try:
                if scan_type == "holding_register":
                    result = communicator.client.read_holding_registers(addr, count=1)
                elif scan_type == "input_register":
                    result = communicator.client.read_input_registers(addr, count=1)
                elif scan_type == "coil":
                    result = communicator.client.read_coils(addr, count=1)
                elif scan_type == "discrete_input":
                    result = communicator.client.read_discrete_inputs(addr, count=1)
                
                if not result.isError():
                    if scan_type in ["coil", "discrete_input"]:
                        value = result.bits[0]
                    else:
                        value = result.registers[0]
                    
                    found_addresses.append((addr, value))
                    
            except Exception:
                pass  # Continue scanning even if individual addresses fail
            
            progress_bar.progress((addr - start_addr + 1) / total_addresses)
        
        progress_bar.empty()
        status_text.empty()
        
        if found_addresses:
            st.success(f"Found {len(found_addresses)} responsive addresses:")
            
            # Display results in a table
            import pandas as pd
            df = pd.DataFrame(found_addresses, columns=["Address", "Value"])
            if scan_type in ["holding_register", "input_register"]:
                df["Hex"] = df["Value"].apply(lambda x: f"0x{x:04x}")
            st.dataframe(df)
            
            add_log(f"Address scan completed: {len(found_addresses)}/{total_addresses} responsive", "SUCCESS")
        else:
            st.warning(f"No responsive addresses found in range {start_addr}-{end_addr}")
            add_log("Address scan completed: no responsive addresses found", "INFO")
            
    except Exception as e:
        error_msg = f"Address scan failed: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

def render_batch_page():
    """Render the batch operations page."""
    st.header("📈 Batch Operations")
    
    if not st.session_state.plc_connected:
        st.warning("Please connect to PLC first")
        return
    
    st.info("Batch operations functionality will be implemented by specialized agents")

def render_logs_page():
    """Render the live logs page."""
    st.header("📝 Live System Logs")
    
    # Display recent logs
    if st.session_state.ui_logs:
        st.text_area(
            "Recent Logs", 
            value="\n".join(st.session_state.ui_logs[-20:]),  # Show last 20 logs
            height=400,
            disabled=True
        )
    else:
        st.info("No logs available yet. Perform some operations to generate logs.")
    
    # Auto-refresh option
    if st.checkbox("Auto-refresh logs"):
        st.rerun()

def filter_parameters(search_term: str, data_type_filter: str, writable_filter: str):
    """Filter parameters based on search criteria."""
    filtered = {}
    
    for param_id, param_data in st.session_state.loaded_parameters.items():
        # Apply search filter
        if search_term:
            search_lower = search_term.lower()
            if not any([
                search_lower in str(param_data.get('name', '')).lower(),
                search_lower in str(param_data.get('component_name', '')).lower(),
                search_lower in str(param_data.get('description', '')).lower(),
                search_lower in str(param_id).lower()
            ]):
                continue
        
        # Apply data type filter
        if data_type_filter != "All" and param_data.get('data_type') != data_type_filter:
            continue
        
        # Apply writable filter
        if writable_filter == "Writable" and not param_data.get('is_writable', False):
            continue
        elif writable_filter == "Read-only" and param_data.get('is_writable', False):
            continue
        
        filtered[param_id] = param_data
    
    return filtered

def render_parameter_card(param_id: str, param_data: dict):
    """Render an individual parameter card with read/write operations."""
    with st.expander(f"📊 {param_data.get('name', 'Unnamed')} - {param_data.get('short_component_name', '')}", expanded=False):
        # Parameter info
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**ID:** `{param_id}`")
            st.markdown(f"**Component:** {param_data.get('component_name', 'Unknown')}")
            st.markdown(f"**Data Type:** {param_data.get('data_type', 'Unknown')}")
            st.markdown(f"**Modbus Address:** {param_data.get('modbus_address', 'N/A')}")
            
            if param_data.get('description'):
                st.markdown(f"**Description:** {param_data.get('description')}")
            
            # Value constraints
            if param_data.get('min_value') is not None or param_data.get('max_value') is not None:
                min_val = param_data.get('min_value', 'N/A')
                max_val = param_data.get('max_value', 'N/A')
                st.markdown(f"**Range:** {min_val} to {max_val}")
            
            if param_data.get('unit'):
                st.markdown(f"**Unit:** {param_data.get('unit')}")
        
        with col2:
            # Current value display
            current_value = st.session_state.loaded_parameters[param_id].get('current_value')
            if current_value is not None:
                st.metric("Current Value", f"{current_value}")
            else:
                st.metric("Current Value", "Not read")
            
            # Read/Write operations
            col_read, col_write = st.columns(2)
            
            with col_read:
                if st.button(f"📖 Read", key=f"read_{param_id}"):
                    asyncio.run(read_single_parameter(param_id))
            
            with col_write:
                if param_data.get('is_writable', False):
                    if st.button(f"✏️ Write", key=f"write_{param_id}"):
                        st.session_state[f'write_mode_{param_id}'] = True
                        st.rerun()
                else:
                    st.button(f"🔒 Read-only", disabled=True, key=f"readonly_{param_id}")
        
        # Write mode interface
        if st.session_state.get(f'write_mode_{param_id}', False):
            render_write_interface(param_id, param_data)

def render_write_interface(param_id: str, param_data: dict):
    """Render the write interface for a parameter."""
    st.markdown("**✏️ Write New Value**")
    
    data_type = param_data.get('data_type', 'float')
    min_val = param_data.get('min_value')
    max_val = param_data.get('max_value')
    
    # Input field based on data type
    if data_type == 'binary':
        new_value = st.selectbox(
            "Value",
            options=[True, False],
            format_func=lambda x: "ON (True)" if x else "OFF (False)",
            key=f"write_input_{param_id}"
        )
        new_value = float(1.0 if new_value else 0.0)
    elif data_type in ['int32', 'int16']:
        new_value = st.number_input(
            "Value",
            min_value=int(min_val) if min_val is not None else -2147483648,
            max_value=int(max_val) if max_val is not None else 2147483647,
            step=1,
            key=f"write_input_{param_id}"
        )
        new_value = float(new_value)
    else:  # float
        new_value = st.number_input(
            "Value",
            min_value=float(min_val) if min_val is not None else -1e10,
            max_value=float(max_val) if max_val is not None else 1e10,
            format="%.6f",
            key=f"write_input_{param_id}"
        )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Write Value", key=f"confirm_write_{param_id}"):
            asyncio.run(write_single_parameter(param_id, new_value))
            st.session_state[f'write_mode_{param_id}'] = False
            st.rerun()
    
    with col2:
        if st.button("❌ Cancel", key=f"cancel_write_{param_id}"):
            st.session_state[f'write_mode_{param_id}'] = False
            st.rerun()
    
    with col3:
        if st.button("📖 Read First", key=f"read_before_write_{param_id}"):
            asyncio.run(read_single_parameter(param_id))

async def read_single_parameter(param_id: str):
    """Read a single parameter from PLC."""
    try:
        add_log(f"Reading parameter {param_id}", "INFO")
        
        if not st.session_state.plc_manager_instance:
            raise RuntimeError("Not connected to PLC")
        
        value = await st.session_state.plc_manager_instance.read_parameter(param_id)
        
        # Update cached value
        st.session_state.loaded_parameters[param_id]['current_value'] = value
        
        param_name = st.session_state.loaded_parameters[param_id].get('name', param_id)
        add_log(f"Successfully read {param_name}: {value}", "SUCCESS")
        st.success(f"Read {param_name}: **{value}**")
        
    except Exception as e:
        error_msg = f"Failed to read parameter {param_id}: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

async def write_single_parameter(param_id: str, value: float):
    """Write a single parameter to PLC."""
    try:
        add_log(f"Writing parameter {param_id} = {value}", "INFO")
        
        if not st.session_state.plc_manager_instance:
            raise RuntimeError("Not connected to PLC")
        
        success = await st.session_state.plc_manager_instance.write_parameter(param_id, value)
        
        if success:
            # Update cached value
            st.session_state.loaded_parameters[param_id]['current_value'] = value
            
            param_name = st.session_state.loaded_parameters[param_id].get('name', param_id)
            add_log(f"Successfully wrote {param_name} = {value}", "SUCCESS")
            st.success(f"Successfully wrote **{value}** to {param_name}")
            
            # Automatically read back to verify
            await asyncio.sleep(0.1)
            read_back_value = await st.session_state.plc_manager_instance.read_parameter(param_id)
            st.session_state.loaded_parameters[param_id]['current_value'] = read_back_value
            
            if abs(read_back_value - value) < 1e-6:
                add_log(f"Write verification successful: {read_back_value}", "SUCCESS")
            else:
                add_log(f"Write verification warning: wrote {value}, read back {read_back_value}", "WARNING")
        else:
            raise RuntimeError("Write operation returned False")
        
    except Exception as e:
        error_msg = f"Failed to write parameter {param_id}: {str(e)}"
        add_log(error_msg, "ERROR")
        st.error(error_msg)

async def read_all_parameters(param_ids: list):
    """Read multiple parameters from PLC."""
    success_count = 0
    total_count = len(param_ids)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, param_id in enumerate(param_ids):
        try:
            status_text.text(f"Reading parameter {i+1}/{total_count}: {param_id}")
            
            value = await st.session_state.plc_manager_instance.read_parameter(param_id)
            st.session_state.loaded_parameters[param_id]['current_value'] = value
            success_count += 1
            
        except Exception as e:
            add_log(f"Failed to read {param_id}: {str(e)}", "ERROR")
        
        progress_bar.progress((i + 1) / total_count)
    
    progress_bar.empty()
    status_text.empty()
    
    add_log(f"Batch read completed: {success_count}/{total_count} successful", "INFO")
    st.success(f"Read {success_count} out of {total_count} parameters")

def refresh_parameter_cache():
    """Refresh parameter metadata from the PLC."""
    if st.session_state.plc_manager_instance and hasattr(st.session_state.plc_manager_instance.plc, '_parameter_cache'):
        st.session_state.loaded_parameters = st.session_state.plc_manager_instance.plc._parameter_cache.copy()
        add_log(f"Refreshed {len(st.session_state.loaded_parameters)} parameters from PLC", "INFO")
        st.success("Parameter metadata refreshed!")
    else:
        st.warning("No PLC connection or parameter cache available")

def prepare_csv_export(filtered_params: dict) -> str:
    """Prepare CSV data for parameter export."""
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'Parameter ID', 'Name', 'Component', 'Data Type', 'Modbus Address', 
        'Min Value', 'Max Value', 'Is Writable', 'Current Value', 'Unit', 'Description'
    ])
    
    # Data rows
    for param_id, param_data in filtered_params.items():
        writer.writerow([
            param_id,
            param_data.get('name', ''),
            param_data.get('component_name', ''),
            param_data.get('data_type', ''),
            param_data.get('modbus_address', ''),
            param_data.get('min_value', ''),
            param_data.get('max_value', ''),
            param_data.get('is_writable', False),
            param_data.get('current_value', ''),
            param_data.get('unit', ''),
            param_data.get('description', '')
        ])
    
    return output.getvalue()

def main():
    """Main application entry point."""
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar components
    render_connection_panel()
    render_status_dashboard()
    render_navigation_menu()
    
    # Render main content
    render_main_content()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("*ALD PLC Testing Interface v1.0*")
    st.sidebar.markdown("*Built with Claude Code Orchestration*")

if __name__ == "__main__":
    main()