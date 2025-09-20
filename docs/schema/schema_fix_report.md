# Schema Alignment Report

This repository was updated to match the live Supabase schema (see docs/schema/schema_summary.md).

Changes made:
- src/parameter_control_listener.py
  - Claim commands via executed_at (no status/priority).
  - Finalize via completed_at and optional error_message.
  - Removed reliance on parameter_type and priority.
  
- test_parameter_control.py
  - Insert minimal fields consistent with table.
  - Pending detection via executed_at IS NULL.
- src/recipe_flow/starter.py and src/recipe_flow/executor.py
  - Removed writes to process_executions.current_step/current_step_index.
  - State remains in process_execution_state only.
- src/step_flow/loop_step.py
  - Removed writes to process_executions.current_step.
- src/plc/real_plc.py
  - Now prefers read_modbus_* for reads and write_modbus_* for writes, with legacy fallback.

Run to refresh schema artifacts:
- scripts/fetch_supabase_openapi.sh

Verification (2025-09-19):
- src/parameter_control_listener.py: compliant. Claims via executed_at, finalizes via
  completed_at/error_message. No usage of status/priority/parameter_type.
  
- test_parameter_control.py: inserts minimal fields; pending detected by executed_at IS NULL.
- src/recipe_flow/starter.py: does not write current_step/current_step_index in
  process_executions. Initializes process_execution_state instead.
- src/recipe_flow/executor.py: updates progress in process_execution_state only.
- src/step_flow/loop_step.py: does not write process_executions.current_step; only touches
  process_executions.updated_at.
- src/plc/real_plc.py: reads prefer read_modbus_address/type; writes prefer
  write_modbus_address/type with legacy fallback.
