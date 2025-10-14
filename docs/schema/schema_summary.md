# Supabase Schema Summary (from OpenAPI)

Generated via `scripts/fetch_supabase_openapi.sh` on 2025-09-20.

This summarizes key tables and columns relevant to the ALD control system. Source of truth: `docs/schema/supabase_openapi.json` (PostgREST Swagger 2.0) and `docs/schema/table_columns.json`.

## Tables

### machines
- admin_id, current_operator_id, current_process_id
- machine_type, model, serial_number, status, is_active, is_virtual
- lab_name, lab_institution, location, virtual_config
- install_date, last_maintenance_date
- id, created_at, updated_at

### machine_state
- machine_id, current_state, state_since, updated_at
- is_failure_mode, failure_component, failure_description
- process_id

### recipes
- id, name, description, version, is_public, created_by
- machine_type, substrate
- chamber_temperature_set_point, pressure_set_point
- created_at, updated_at

### recipe_steps
- id, recipe_id, name, type, description
- sequence_number, parent_step_id
- created_at

### loop_step_config
- id, step_id, iteration_count
- created_at, updated_at

### valve_step_config
- id, step_id, valve_id, valve_number
- duration_ms
- created_at, updated_at

### purge_step_config
- id, step_id, gas_type, flow_rate
- duration_ms
- created_at, updated_at

### recipe_commands
- id, machine_id, recipe_step_id, type, parameters
- status, executed_at, error_message
- created_at, updated_at

### parameter_control_commands
- id, machine_id, parameter_name, target_value, timeout_ms
- executed_at, completed_at, error_message
- created_at

### process_executions
- id, machine_id, operator_id, session_id
- recipe_id, recipe_version, parameters, description
- status, start_time, end_time, error_message
- created_at, updated_at

### process_execution_state
- id, execution_id, last_updated, progress, process_metrics
- current_step, current_step_index, current_step_name, current_step_type
- current_overall_step, total_overall_steps
- current_loop_count, current_loop_iteration
- current_valve_number, current_valve_duration_ms
- current_purge_duration_ms, current_parameter_id, current_parameter_value
- created_at

### component_parameter_definitions
- id, component_definition_id, name, description, unit
- default_min, default_max, is_writable
- created_at, updated_at

### component_parameters
 - id, component_id, definition_id, data_type
 - current_value, set_value, min_value, max_value
 - is_writable, show_in_ui, show_in_graph
 - read_modbus_address, read_modbus_type
 - write_modbus_address, write_modbus_type
 - created_at, updated_at

### operator_sessions
- id, machine_id, operator_id, session_status
- reservation_id (FK to slot_reservations), process_execution_id (FK to process_executions)
- session_start_time, session_end_time, last_heartbeat
- grace_period_used_minutes, is_extended, extension_granted_until
- created_at, updated_at

## Notable Mismatches vs. Common App Expectations

- parameter_control_commands: No `status`, `priority`, or `parameter_type`. Tracks `executed_at`, `completed_at`, and `error_message` instead.
- process_executions: Does not store `current_step`, `current_step_index`, or `total_steps`. Execution state is modeled in `process_execution_state`.
- component_parameters: Uses dual-address model with explicit read/write addresses and types
  (`read_modbus_address`, `read_modbus_type`, `write_modbus_address`, `write_modbus_type`).
  Legacy `modbus_address`/`modbus_type` are deprecated and not exposed in views.

Refer to the OpenAPI document for full details and types.
