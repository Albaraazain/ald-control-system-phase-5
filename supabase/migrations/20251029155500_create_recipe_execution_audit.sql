-- Migration: Create recipe_execution_audit table for comprehensive recipe traceability
-- Purpose: Track ALL recipe execution operations with full context for debugging, compliance, and performance analysis
-- Separates recipe-driven operations from manual parameter commands (parameter_control_commands)

-- Create enum for operation types
CREATE TYPE recipe_operation_type AS ENUM (
    'valve',        -- Valve control operations
    'parameter',    -- Parameter adjustments
    'purge',        -- Purge operations
    'loop',         -- Loop iterations
    'wait'          -- Wait/delay steps
);

-- Create enum for operation status
CREATE TYPE recipe_operation_status AS ENUM (
    'initiated',    -- Operation started
    'writing',      -- Writing to PLC
    'verifying',    -- Verifying write (if enabled)
    'success',      -- Completed successfully
    'failed',       -- Failed to complete
    'skipped',      -- Skipped (due to cancel/error)
    'cancelled'     -- Cancelled by user
);

-- Create the main audit table
CREATE TABLE recipe_execution_audit (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Recipe execution context (foreign keys for full traceability)
    process_id UUID NOT NULL REFERENCES process_executions(id) ON DELETE CASCADE,
    recipe_id UUID NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    step_id UUID REFERENCES recipe_steps(id) ON DELETE SET NULL,  -- NULL if step deleted
    machine_id UUID NOT NULL REFERENCES machines_base(id) ON DELETE CASCADE,

    -- Operation identification
    operation_type recipe_operation_type NOT NULL,
    parameter_name TEXT NOT NULL,  -- Human-readable: 'Valve_1', 'Chamber_Temperature', etc.
    component_parameter_id UUID REFERENCES component_parameters(id) ON DELETE SET NULL,

    -- Operation details
    target_value NUMERIC NOT NULL,  -- Commanded value
    actual_value NUMERIC,  -- Verified value (if verification performed)
    duration_ms INTEGER,  -- For valve/purge operations

    -- Sequencing within recipe
    step_sequence INTEGER NOT NULL,  -- Order within recipe (1, 2, 3...)
    loop_iteration INTEGER DEFAULT 0,  -- Current iteration if inside loop
    parent_step_id UUID REFERENCES recipe_steps(id) ON DELETE SET NULL,  -- For nested operations

    -- Timing (microsecond precision for performance analysis)
    operation_initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    plc_write_start_time TIMESTAMPTZ,
    plc_write_end_time TIMESTAMPTZ,
    plc_write_duration_ms INTEGER GENERATED ALWAYS AS (
        CASE
            WHEN plc_write_start_time IS NOT NULL AND plc_write_end_time IS NOT NULL
            THEN EXTRACT(EPOCH FROM (plc_write_end_time - plc_write_start_time))::INTEGER * 1000
            ELSE NULL
        END
    ) STORED,
    operation_completed_at TIMESTAMPTZ,

    -- Verification
    verification_attempted BOOLEAN DEFAULT false,
    verification_success BOOLEAN,
    verification_details JSONB,  -- Optional verification metadata

    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    final_status recipe_operation_status NOT NULL,

    -- Modbus details (for debugging PLC communication)
    modbus_address INTEGER,  -- Address written to
    modbus_register_type TEXT,  -- 'holding_register', 'coil', etc.

    -- Extensibility
    metadata JSONB DEFAULT '{}',  -- Additional context (e.g., operator notes, environmental conditions)

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add comments for documentation
COMMENT ON TABLE recipe_execution_audit IS 'Comprehensive audit trail for recipe execution operations. Tracks all valve, parameter, and control operations with full context for traceability, debugging, and compliance. Separate from parameter_control_commands which handles manual/external commands.';

COMMENT ON COLUMN recipe_execution_audit.process_id IS 'Links to process_executions table - identifies which recipe run this operation belongs to';
COMMENT ON COLUMN recipe_execution_audit.recipe_id IS 'Links to recipes table - identifies which recipe was being executed';
COMMENT ON COLUMN recipe_execution_audit.step_id IS 'Links to recipe_steps table - identifies the specific recipe step';
COMMENT ON COLUMN recipe_execution_audit.machine_id IS 'Links to machines_base table - identifies which machine performed this operation';
COMMENT ON COLUMN recipe_execution_audit.operation_type IS 'Type of operation: valve, parameter, purge, loop, or wait';
COMMENT ON COLUMN recipe_execution_audit.parameter_name IS 'Human-readable parameter name (e.g., Valve_1, Chamber_Temperature) for easy debugging';
COMMENT ON COLUMN recipe_execution_audit.component_parameter_id IS 'Direct reference to component_parameters table for precise lookup';
COMMENT ON COLUMN recipe_execution_audit.target_value IS 'The value that was commanded/set';
COMMENT ON COLUMN recipe_execution_audit.actual_value IS 'The value that was verified (if verification was performed)';
COMMENT ON COLUMN recipe_execution_audit.duration_ms IS 'Duration for valve/purge operations in milliseconds';
COMMENT ON COLUMN recipe_execution_audit.step_sequence IS 'Sequential order of this operation within the recipe (1, 2, 3...)';
COMMENT ON COLUMN recipe_execution_audit.loop_iteration IS 'If inside a loop, which iteration this operation belongs to (0 for non-looped)';
COMMENT ON COLUMN recipe_execution_audit.parent_step_id IS 'For nested operations (e.g., steps inside a loop), references the parent step';
COMMENT ON COLUMN recipe_execution_audit.plc_write_start_time IS 'Timestamp when PLC write operation began';
COMMENT ON COLUMN recipe_execution_audit.plc_write_end_time IS 'Timestamp when PLC write operation completed';
COMMENT ON COLUMN recipe_execution_audit.plc_write_duration_ms IS 'Calculated duration of PLC write in milliseconds for performance analysis';
COMMENT ON COLUMN recipe_execution_audit.verification_attempted IS 'Whether verification was attempted after write';
COMMENT ON COLUMN recipe_execution_audit.verification_success IS 'If verification was attempted, whether it succeeded';
COMMENT ON COLUMN recipe_execution_audit.verification_details IS 'JSONB with verification details (expected vs actual, tolerance, etc.)';
COMMENT ON COLUMN recipe_execution_audit.error_message IS 'Error details if operation failed';
COMMENT ON COLUMN recipe_execution_audit.retry_count IS 'Number of times this operation was retried before success/failure';
COMMENT ON COLUMN recipe_execution_audit.final_status IS 'Final status of the operation';
COMMENT ON COLUMN recipe_execution_audit.modbus_address IS 'Modbus address that was written to (for debugging PLC communication)';
COMMENT ON COLUMN recipe_execution_audit.metadata IS 'JSONB for additional context (operator notes, environmental conditions, etc.)';

-- Create indexes for common query patterns
CREATE INDEX idx_recipe_audit_process_id ON recipe_execution_audit(process_id);
CREATE INDEX idx_recipe_audit_recipe_id ON recipe_execution_audit(recipe_id);
CREATE INDEX idx_recipe_audit_step_id ON recipe_execution_audit(step_id) WHERE step_id IS NOT NULL;
CREATE INDEX idx_recipe_audit_machine_id ON recipe_execution_audit(machine_id);
CREATE INDEX idx_recipe_audit_created_at ON recipe_execution_audit(created_at DESC);
CREATE INDEX idx_recipe_audit_operation_type ON recipe_execution_audit(operation_type);
CREATE INDEX idx_recipe_audit_final_status ON recipe_execution_audit(final_status);

-- Composite index for common query: "show me all operations for a specific process, ordered by sequence"
CREATE INDEX idx_recipe_audit_process_sequence ON recipe_execution_audit(process_id, step_sequence);

-- Composite index for: "show me recent valve operations on this machine"
CREATE INDEX idx_recipe_audit_machine_type_time ON recipe_execution_audit(machine_id, operation_type, created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE recipe_execution_audit ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can read audit records for their assigned machines
CREATE POLICY recipe_audit_select_policy ON recipe_execution_audit
    FOR SELECT
    USING (
        machine_id IN (
            SELECT machine_id
            FROM user_machine_assignments
            WHERE user_id = auth.uid()
            AND is_active = true
        )
    );

-- RLS Policy: Service role can insert audit records (Terminal 2 uses service role)
CREATE POLICY recipe_audit_insert_policy ON recipe_execution_audit
    FOR INSERT
    WITH CHECK (true);  -- Service role bypasses RLS anyway, but explicit policy for clarity

-- RLS Policy: Admins can see all audit records
CREATE POLICY recipe_audit_admin_all_policy ON recipe_execution_audit
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_recipe_audit_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER recipe_audit_updated_at
    BEFORE UPDATE ON recipe_execution_audit
    FOR EACH ROW
    EXECUTE FUNCTION update_recipe_audit_updated_at();

-- Create helper view for common queries
CREATE VIEW recipe_audit_summary AS
SELECT
    rea.id,
    rea.process_id,
    pe.status as process_status,
    r.name as recipe_name,
    rs.name as step_name,
    rea.operation_type,
    rea.parameter_name,
    rea.target_value,
    rea.actual_value,
    rea.duration_ms,
    rea.step_sequence,
    rea.loop_iteration,
    rea.plc_write_duration_ms,
    rea.verification_attempted,
    rea.verification_success,
    rea.final_status,
    rea.error_message,
    rea.created_at,
    rea.operation_completed_at,
    EXTRACT(EPOCH FROM (rea.operation_completed_at - rea.operation_initiated_at))::INTEGER * 1000 as total_duration_ms
FROM recipe_execution_audit rea
LEFT JOIN process_executions pe ON rea.process_id = pe.id
LEFT JOIN recipes r ON rea.recipe_id = r.id
LEFT JOIN recipe_steps rs ON rea.step_id = rs.id;

COMMENT ON VIEW recipe_audit_summary IS 'Convenient view joining audit records with related tables for easy querying and reporting';

-- Grant permissions
GRANT SELECT ON recipe_execution_audit TO authenticated;
GRANT SELECT ON recipe_audit_summary TO authenticated;
GRANT ALL ON recipe_execution_audit TO service_role;
