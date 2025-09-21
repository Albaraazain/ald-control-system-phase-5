-- Add component_parameter_id column to parameter_control_commands table
-- This allows direct parameter lookup by ID instead of risky parameter_name lookups

-- Add the column (nullable initially for backward compatibility)
ALTER TABLE parameter_control_commands
ADD COLUMN component_parameter_id UUID;

-- Add foreign key constraint to component_parameters table
ALTER TABLE parameter_control_commands
ADD CONSTRAINT fk_parameter_control_commands_component_parameter_id
FOREIGN KEY (component_parameter_id) REFERENCES component_parameters(id);

-- Add index for performance
CREATE INDEX idx_parameter_control_commands_component_parameter_id
ON parameter_control_commands(component_parameter_id);

-- Add comment explaining the purpose
COMMENT ON COLUMN parameter_control_commands.component_parameter_id IS
'Direct reference to component_parameters.id for reliable parameter lookup. When provided, this takes precedence over parameter_name to avoid conflicts with parameters that have the same name across different machines.';