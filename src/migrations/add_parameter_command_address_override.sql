-- Migration: Add modbus address override support to parameter_control_commands
-- This allows commands to specify their own modbus address, bypassing parameter table lookup

BEGIN;

-- Add override columns for modbus addressing
ALTER TABLE parameter_control_commands
ADD COLUMN IF NOT EXISTS write_modbus_address INTEGER,
ADD COLUMN IF NOT EXISTS modbus_address INTEGER;

-- Add comments for clarity
COMMENT ON COLUMN parameter_control_commands.write_modbus_address IS 'Override write modbus address for this command (takes precedence over parameter table)';
COMMENT ON COLUMN parameter_control_commands.modbus_address IS 'Legacy override modbus address for backward compatibility';

COMMIT;

-- Rollback migration (if needed):
-- ALTER TABLE parameter_control_commands DROP COLUMN IF EXISTS write_modbus_address;
-- ALTER TABLE parameter_control_commands DROP COLUMN IF EXISTS modbus_address;