-- PostgreSQL stored procedure for atomic machine state updates
-- Eliminates dual table race condition by wrapping both updates in a single transaction

CREATE OR REPLACE FUNCTION atomic_update_machine_state(
    p_machine_id UUID,
    p_machine_status TEXT,
    p_current_process_id UUID DEFAULT NULL,
    p_machine_state_current_state TEXT,
    p_machine_state_process_id UUID DEFAULT NULL,
    p_is_failure_mode BOOLEAN DEFAULT FALSE,
    p_failure_description TEXT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result_data JSON;
    machine_record RECORD;
    machine_state_record RECORD;
    update_timestamp TIMESTAMPTZ := NOW();
BEGIN
    -- Set transaction isolation level for consistency
    SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;

    -- Update machines table
    UPDATE public.machines
    SET
        status = p_machine_status,
        current_process_id = p_current_process_id,
        updated_at = update_timestamp
    WHERE id = p_machine_id
    RETURNING * INTO machine_record;

    -- Check if machine update succeeded
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Machine with id % not found', p_machine_id;
    END IF;

    -- Update machine_state table
    UPDATE public.machine_state
    SET
        current_state = p_machine_state_current_state,
        state_since = update_timestamp,
        process_id = p_machine_state_process_id,
        is_failure_mode = p_is_failure_mode,
        failure_description = CASE
            WHEN p_failure_description IS NOT NULL THEN p_failure_description
            ELSE failure_description
        END,
        updated_at = update_timestamp
    WHERE machine_id = p_machine_id
    RETURNING * INTO machine_state_record;

    -- Check if machine_state update succeeded
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Machine state for machine_id % not found', p_machine_id;
    END IF;

    -- Return combined result as JSON
    SELECT json_build_object(
        'success', true,
        'machine', row_to_json(machine_record),
        'machine_state', row_to_json(machine_state_record),
        'updated_at', update_timestamp
    ) INTO result_data;

    RETURN result_data;

EXCEPTION
    WHEN OTHERS THEN
        -- Log error and re-raise
        RAISE EXCEPTION 'Atomic machine state update failed: %', SQLERRM;
END;
$$;

-- Create atomic machine state completion function (idle state)
CREATE OR REPLACE FUNCTION atomic_complete_machine_state(
    p_machine_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN atomic_update_machine_state(
        p_machine_id := p_machine_id,
        p_machine_status := 'idle',
        p_current_process_id := NULL,
        p_machine_state_current_state := 'idle',
        p_machine_state_process_id := NULL,
        p_is_failure_mode := FALSE
    );
END;
$$;

-- Create atomic machine state error function (error state)
CREATE OR REPLACE FUNCTION atomic_error_machine_state(
    p_machine_id UUID,
    p_error_message TEXT
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN atomic_update_machine_state(
        p_machine_id := p_machine_id,
        p_machine_status := 'error',
        p_current_process_id := NULL,
        p_machine_state_current_state := 'error',
        p_machine_state_process_id := NULL,
        p_is_failure_mode := TRUE,
        p_failure_description := CONCAT('Recipe execution error: ', p_error_message)
    );
END;
$$;

-- Create atomic machine state processing function (processing state)
CREATE OR REPLACE FUNCTION atomic_processing_machine_state(
    p_machine_id UUID,
    p_process_id UUID
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN atomic_update_machine_state(
        p_machine_id := p_machine_id,
        p_machine_status := 'processing',
        p_current_process_id := p_process_id,
        p_machine_state_current_state := 'processing',
        p_machine_state_process_id := p_process_id,
        p_is_failure_mode := FALSE
    );
END;
$$;

-- Add comments for documentation
COMMENT ON FUNCTION atomic_update_machine_state IS 'Atomically updates both machines and machine_state tables to eliminate race condition. Returns combined JSON result.';
COMMENT ON FUNCTION atomic_complete_machine_state IS 'Convenience function to atomically set machine to idle state (recipe completion)';
COMMENT ON FUNCTION atomic_error_machine_state IS 'Convenience function to atomically set machine to error state with failure description';
COMMENT ON FUNCTION atomic_processing_machine_state IS 'Convenience function to atomically set machine to processing state with process ID';