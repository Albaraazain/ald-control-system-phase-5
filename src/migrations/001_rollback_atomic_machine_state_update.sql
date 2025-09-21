-- Rollback script for atomic machine state update functions
-- Safe to run if functions don't exist (IF EXISTS)

-- Drop all atomic machine state functions
DROP FUNCTION IF EXISTS atomic_update_machine_state(UUID, TEXT, UUID, TEXT, UUID, BOOLEAN, TEXT);
DROP FUNCTION IF EXISTS atomic_complete_machine_state(UUID);
DROP FUNCTION IF EXISTS atomic_error_machine_state(UUID, TEXT);
DROP FUNCTION IF EXISTS atomic_processing_machine_state(UUID, UUID);

-- Log rollback completion
DO $$
BEGIN
    RAISE NOTICE 'Atomic machine state functions have been removed';
END $$;