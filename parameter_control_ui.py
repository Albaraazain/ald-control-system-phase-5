#!/usr/bin/env python3
"""
Parameter Control Streamlit UI
A dedicated interface for testing parameter control commands that communicate with the PLC via modbus.
"""

import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime
import time

# Add src directory to Python path
sys.path.insert(0, 'src')

try:
    from src.db import get_supabase
    from src.config import MACHINE_ID
except ImportError as e:
    st.error(f"Failed to import required modules: {e}")
    st.stop()

# Configure Streamlit page
st.set_page_config(
    page_title="Parameter Control Interface",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
    }
    .stButton > button {
        width: 100%;
    }
    .status-pending {
        color: orange;
        font-weight: bold;
    }
    .status-executing {
        color: blue;
        font-weight: bold;
    }
    .status-completed {
        color: green;
        font-weight: bold;
    }
    .status-failed {
        color: red;
        font-weight: bold;
    }
    .parameter-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

def get_supabase_client():
    """Get Supabase client with error handling"""
    try:
        return get_supabase()
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return None

def get_machine_id():
    """Get machine ID with fallback"""
    if MACHINE_ID:
        return MACHINE_ID
    
    # Fallback: get first machine from database
    supabase = get_supabase_client()
    if supabase:
        try:
            result = supabase.table('machines').select('id').limit(1).execute()
            if result.data:
                return result.data[0]['id']
        except Exception:
            pass
    return None

def create_parameter_command(parameter_name, parameter_type, target_value, modbus_address, modbus_type, priority=0):
    """Create a new parameter control command"""
    supabase = get_supabase_client()
    machine_id = get_machine_id()
    
    if not supabase or not machine_id:
        return False, "Database connection or machine ID not available"
    
    try:
        command_data = {
            "parameter_name": parameter_name,
            "parameter_type": parameter_type,
            "target_value": float(target_value),
            "modbus_address": modbus_address,
            "modbus_type": modbus_type,
            "machine_id": machine_id,
            "priority": priority
        }
        
        result = supabase.table("parameter_control_commands").insert(command_data).execute()
        
        if result.data:
            return True, f"Command created successfully (ID: {result.data[0]['id']})"
        else:
            return False, "Failed to create command"
            
    except Exception as e:
        return False, f"Error creating command: {str(e)}"

def get_recent_commands(limit=20):
    """Get recent parameter control commands"""
    supabase = get_supabase_client()
    if not supabase:
        return []
    
    try:
        result = (
            supabase.table("parameter_control_commands")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching commands: {e}")
        return []

def get_command_stats():
    """Get command statistics"""
    supabase = get_supabase_client()
    if not supabase:
        return {}
    
    try:
        # Get counts by status
        result = supabase.table("parameter_control_commands").select("status").execute()
        if not result.data:
            return {}
        
        stats = {}
        for row in result.data:
            status = row['status']
            stats[status] = stats.get(status, 0) + 1
        
        return stats
    except Exception as e:
        st.error(f"Error fetching stats: {e}")
        return {}

def clear_all_commands():
    """Clear all parameter control commands"""
    supabase = get_supabase_client()
    if not supabase:
        return False, "Database connection not available"
    
    try:
        # Delete all commands (using a filter that matches all records)
        result = supabase.table("parameter_control_commands").delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        return True, "All commands cleared successfully"
    except Exception as e:
        return False, f"Error clearing commands: {str(e)}"

# Main App
def main():
    st.title("⚡ Parameter Control Interface")
    st.markdown("**Control machine parameters through modbus commands**")
    
    # Sidebar for creating new commands
    with st.sidebar:
        st.header("🔧 Create Parameter Command")
        
        # Real machine parameter addresses
        parameter_presets = {
            "pressure_gauge": {"type": "binary", "address": 2072, "modbus_type": "coil", "description": "Pressure gauge on/off"},
            "exhaust": {"type": "binary", "address": 11, "modbus_type": "coil", "description": "Exhaust valve on/off"},
            "n2_generator": {"type": "binary", "address": 37, "modbus_type": "coil", "description": "Nitrogen generator on/off"},
            "pump": {"type": "binary", "address": 10, "modbus_type": "coil", "description": "Main pump on/off"},
            "mfc_setpoint": {"type": "flow_rate", "address": 2066, "modbus_type": "holding_register", "description": "MFC flow rate setpoint"},
            "mfc_current_value": {"type": "flow_rate", "address": 2082, "modbus_type": "input_register", "description": "MFC current flow rate (read-only)"},
            # Keep some old ones for backward compatibility
            "pump_1": {"type": "binary", "address": 100, "modbus_type": "coil", "description": "Test pump 1 (legacy)"},
            "pump_2": {"type": "binary", "address": 101, "modbus_type": "coil", "description": "Test pump 2 (legacy)"},
            "chamber_heater": {"type": "binary", "address": 103, "modbus_type": "coil", "description": "Chamber heater on/off (legacy)"},
            "temperature_setpoint": {"type": "temperature", "address": 203, "modbus_type": "holding_register", "description": "Temperature setpoint (legacy)"}
        }
        
        # Parameter selection
        selected_preset = st.selectbox(
            "Select Parameter",
            options=list(parameter_presets.keys()),
            format_func=lambda x: f"{x.replace('_', ' ').title()} ({parameter_presets[x]['description']})"
        )
        
        preset = parameter_presets[selected_preset]
        
        # Show parameter details and allow editing modbus address
        st.info(f"**Description:** {preset['description']}\n**Type:** {preset['type']}\n**Address:** {preset['address']}\n**Modbus:** {preset['modbus_type']}")
        
        # Allow custom modbus address
        with st.expander("🔧 Advanced Settings", expanded=False):
            custom_address = st.number_input(
                "Custom Modbus Address", 
                min_value=1, 
                max_value=65535, 
                value=preset['address'], 
                step=1,
                help="Override the default modbus address for this parameter"
            )
            
            custom_modbus_type = st.selectbox(
                "Modbus Type",
                options=["coil", "holding_register", "input_register", "discrete_input"],
                index=["coil", "holding_register", "input_register", "discrete_input"].index(preset['modbus_type']),
                help="Type of modbus register"
            )
            
            if custom_address != preset['address'] or custom_modbus_type != preset['modbus_type']:
                st.warning(f"⚠️ Using custom settings: Address={custom_address}, Type={custom_modbus_type}")
        
        # Value input based on parameter type
        if preset['type'] == 'binary':
            target_value = st.selectbox("Value", options=[0, 1], format_func=lambda x: "OFF" if x == 0 else "ON")
        else:
            if preset['type'] == 'flow_rate':
                target_value = st.number_input("Flow Rate (sccm)", min_value=0.0, max_value=1000.0, value=100.0, step=1.0)
            elif preset['type'] == 'pressure':
                target_value = st.number_input("Pressure (torr)", min_value=0.0, max_value=10.0, value=1.0, step=0.1)
            elif preset['type'] == 'temperature':
                target_value = st.number_input("Temperature (°C)", min_value=0.0, max_value=500.0, value=25.0, step=1.0)
            else:
                target_value = st.number_input("Value", value=1.0)
        
        # Priority
        priority = st.selectbox("Priority", options=[0, 1, 2, 3], index=1, help="Higher numbers = higher priority")
        
        # Create command button
        if st.button("🚀 Send Command", type="primary"):
            success, message = create_parameter_command(
                parameter_name=selected_preset,
                parameter_type=preset['type'],
                target_value=target_value,
                modbus_address=custom_address,
                modbus_type=custom_modbus_type,
                priority=priority
            )
            
            if success:
                st.success(message)
                time.sleep(0.5)  # Brief pause to see the success message
                st.rerun()
            else:
                st.error(message)
        
        # Quick action buttons
        st.divider()
        st.subheader("🎯 Quick Actions")
        
        # Real machine quick actions
        if st.button("🚀 System Startup", type="primary"):
            startup_sequence = [
                ("pump", 1, 3),  # Pump ON, priority 3
                ("n2_generator", 1, 2),  # N2 Generator ON, priority 2
                ("pressure_gauge", 1, 1)  # Pressure gauge ON, priority 1
            ]
            for param, value, priority in startup_sequence:
                if param in parameter_presets:
                    create_parameter_command(
                        parameter_name=param,
                        parameter_type=parameter_presets[param]['type'],
                        target_value=value,
                        modbus_address=parameter_presets[param]['address'],
                        modbus_type=parameter_presets[param]['modbus_type'],
                        priority=priority
                    )
            st.success("🚀 System startup sequence initiated!")
            time.sleep(0.5)
            st.rerun()
            
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔛 All Equipment ON"):
                equipment = ["pump", "n2_generator", "pressure_gauge", "exhaust"]
                for i, equip in enumerate(equipment):
                    if equip in parameter_presets:
                        create_parameter_command(
                            parameter_name=equip,
                            parameter_type=parameter_presets[equip]['type'],
                            target_value=1,
                            modbus_address=parameter_presets[equip]['address'],
                            modbus_type=parameter_presets[equip]['modbus_type'],
                            priority=2
                        )
                st.success(f"Sent ON commands to {len(equipment)} equipment")
                time.sleep(0.5)
                st.rerun()
        
        with col2:
            if st.button("⚠️ Emergency STOP"):
                equipment = ["pump", "n2_generator", "exhaust"]  # Don't turn off pressure gauge
                for i, equip in enumerate(equipment):
                    if equip in parameter_presets:
                        create_parameter_command(
                            parameter_name=equip,
                            parameter_type=parameter_presets[equip]['type'],
                            target_value=0,
                            modbus_address=parameter_presets[equip]['address'],
                            modbus_type=parameter_presets[equip]['modbus_type'],
                            priority=3  # High priority for emergency stop
                        )
                st.error(f"🚨 Emergency STOP sent to {len(equipment)} equipment")
                time.sleep(0.5)
                st.rerun()
        
        # Custom parameter creation
        st.divider()
        st.subheader("🛠️ Custom Parameter")
        
        with st.expander("Create Custom Parameter", expanded=False):
            custom_name = st.text_input("Parameter Name", placeholder="e.g., custom_pump_4", help="Unique name for your parameter")
            custom_param_type = st.selectbox("Parameter Type", options=["binary", "flow_rate", "pressure", "temperature", "numeric"], key="custom_type")
            custom_param_address = st.number_input("Modbus Address", min_value=1, max_value=65535, value=300, key="custom_addr")
            custom_param_modbus_type = st.selectbox("Modbus Type", options=["coil", "holding_register", "input_register", "discrete_input"], key="custom_modbus")
            
            # Value input for custom parameter
            if custom_param_type == 'binary':
                custom_target_value = st.selectbox("Value", options=[0, 1], format_func=lambda x: "OFF" if x == 0 else "ON", key="custom_val")
            else:
                custom_target_value = st.number_input("Value", value=1.0, key="custom_num_val")
            
            custom_priority = st.selectbox("Priority", options=[0, 1, 2, 3], index=1, key="custom_prio")
            
            if st.button("🎯 Send Custom Command", key="custom_cmd"):
                if custom_name.strip():
                    success, message = create_parameter_command(
                        parameter_name=custom_name.strip(),
                        parameter_type=custom_param_type,
                        target_value=custom_target_value,
                        modbus_address=custom_param_address,
                        modbus_type=custom_param_modbus_type,
                        priority=custom_priority
                    )
                    
                    if success:
                        st.success(message)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please enter a parameter name")
        
        # Clear all commands
        st.divider()
        if st.button("🗑️ Clear All Commands", type="secondary"):
            if st.session_state.get('confirm_clear', False):
                success, message = clear_all_commands()
                if success:
                    st.success(message)
                    st.session_state['confirm_clear'] = False
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.session_state['confirm_clear'] = True
                st.warning("Click again to confirm clearing all commands")
    
    # Main content area
    col1, col2, col3 = st.columns([1, 1, 2])
    
    # Command Statistics
    stats = get_command_stats()
    
    with col1:
        st.subheader("📊 Command Stats")
        
        if stats:
            # Pending commands
            pending_count = stats.get('pending', 0)
            st.metric("⏳ Pending", pending_count, delta=None)
            
            # Executing commands  
            executing_count = stats.get('executing', 0)
            st.metric("⚡ Executing", executing_count, delta=None)
        else:
            st.info("No commands found")
    
    with col2:
        st.subheader("📈 Results")
        
        if stats:
            # Completed commands
            completed_count = stats.get('completed', 0)
            st.metric("✅ Completed", completed_count, delta=None)
            
            # Failed commands
            failed_count = stats.get('failed', 0)
            st.metric("❌ Failed", failed_count, delta=None)
    
    with col3:
        st.subheader("🎯 System Status")
        
        # Show machine ID
        machine_id = get_machine_id()
        if machine_id:
            st.success(f"**Machine ID:** `{machine_id}`")
        else:
            st.error("**Machine ID:** Not configured")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("🔄 Auto-refresh (5s)", value=True)
        
        if auto_refresh:
            # Auto-refresh every 5 seconds
            time.sleep(5)
            st.rerun()
    
    # Recent Commands Table
    st.divider()
    st.subheader("📝 Recent Commands")
    
    commands = get_recent_commands(50)
    
    if commands:
        # Convert to DataFrame for better display
        df = pd.DataFrame(commands)
        
        # Format the data for display
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%H:%M:%S')
        df['executed_at'] = pd.to_datetime(df['executed_at'], errors='coerce').dt.strftime('%H:%M:%S')
        df['completed_at'] = pd.to_datetime(df['completed_at'], errors='coerce').dt.strftime('%H:%M:%S')
        
        # Select and reorder columns
        display_columns = [
            'parameter_name', 'parameter_type', 'target_value', 'modbus_address', 'modbus_type',
            'status', 'priority', 'created_at', 'executed_at', 'completed_at', 'error_message'
        ]
        
        available_columns = [col for col in display_columns if col in df.columns]
        df_display = df[available_columns]
        
        # Color code status
        def color_status(status):
            colors = {
                'pending': '🟡',
                'executing': '🔵', 
                'completed': '🟢',
                'failed': '🔴'
            }
            return f"{colors.get(status, '⚪')} {status}"
        
        df_display['status'] = df_display['status'].apply(color_status)
        
        # Display table
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "parameter_name": "Parameter",
                "parameter_type": "Type", 
                "target_value": "Value",
                "modbus_address": "Address",
                "modbus_type": "Modbus",
                "status": "Status",
                "priority": "Priority", 
                "created_at": "Created",
                "executed_at": "Executed", 
                "completed_at": "Completed",
                "error_message": "Error"
            }
        )
        
        # Summary info
        total_commands = len(commands)
        recent_pending = len([cmd for cmd in commands if cmd['status'] == 'pending'])
        recent_executing = len([cmd for cmd in commands if cmd['status'] == 'executing'])
        
        if recent_pending > 0 or recent_executing > 0:
            st.info(f"🔥 **Active:** {recent_pending} pending, {recent_executing} executing commands")
    
    else:
        st.info("No parameter commands found. Create your first command using the sidebar!")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.8em;'>
        <p>Parameter Control Interface | Real-time modbus communication | Status updates every 3 seconds</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()