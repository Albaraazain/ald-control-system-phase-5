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
        
        # Predefined parameter options
        parameter_presets = {
            "pump_1": {"type": "binary", "address": 100, "modbus_type": "coil"},
            "pump_2": {"type": "binary", "address": 101, "modbus_type": "coil"},
            "pump_3": {"type": "binary", "address": 104, "modbus_type": "coil"},
            "nitrogen_generator": {"type": "binary", "address": 102, "modbus_type": "coil"},
            "vacuum_pump": {"type": "binary", "address": 105, "modbus_type": "coil"},
            "chamber_heater": {"type": "binary", "address": 103, "modbus_type": "coil"},
            "mfc_1_flow_rate": {"type": "flow_rate", "address": 200, "modbus_type": "holding_register"},
            "mfc_2_flow_rate": {"type": "flow_rate", "address": 202, "modbus_type": "holding_register"},
            "pressure_setpoint": {"type": "pressure", "address": 201, "modbus_type": "holding_register"},
            "temperature_setpoint": {"type": "temperature", "address": 203, "modbus_type": "holding_register"}
        }
        
        # Parameter selection
        selected_preset = st.selectbox(
            "Select Parameter",
            options=list(parameter_presets.keys()),
            format_func=lambda x: x.replace("_", " ").title()
        )
        
        preset = parameter_presets[selected_preset]
        
        # Show parameter details
        st.info(f"**Type:** {preset['type']}\n**Address:** {preset['address']}\n**Modbus:** {preset['modbus_type']}")
        
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
                modbus_address=preset['address'],
                modbus_type=preset['modbus_type'],
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
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💨 All Pumps ON"):
                pumps = ["pump_1", "pump_2", "pump_3", "vacuum_pump"]
                for i, pump in enumerate(pumps):
                    create_parameter_command(
                        parameter_name=pump,
                        parameter_type="binary",
                        target_value=1,
                        modbus_address=parameter_presets[pump]['address'],
                        modbus_type="coil",
                        priority=2
                    )
                st.success(f"Sent ON commands to {len(pumps)} pumps")
                time.sleep(0.5)
                st.rerun()
        
        with col2:
            if st.button("🛑 All Pumps OFF"):
                pumps = ["pump_1", "pump_2", "pump_3", "vacuum_pump"]
                for i, pump in enumerate(pumps):
                    create_parameter_command(
                        parameter_name=pump,
                        parameter_type="binary",
                        target_value=0,
                        modbus_address=parameter_presets[pump]['address'],
                        modbus_type="coil",
                        priority=1
                    )
                st.success(f"Sent OFF commands to {len(pumps)} pumps")
                time.sleep(0.5)
                st.rerun()
        
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
            'parameter_name', 'parameter_type', 'target_value', 'status', 
            'priority', 'created_at', 'executed_at', 'completed_at', 'error_message'
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