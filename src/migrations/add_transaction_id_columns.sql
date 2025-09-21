-- Add transaction_id columns to support atomic dual-mode operations
-- Required for transactional data integrity and rollback capabilities

-- Add transaction_id column to parameter_value_history table
ALTER TABLE parameter_value_history
ADD COLUMN IF NOT EXISTS transaction_id TEXT;

-- Add transaction_id column to process_data_points table
ALTER TABLE process_data_points
ADD COLUMN IF NOT EXISTS transaction_id TEXT;

-- Create indexes for efficient transaction tracking and cleanup
CREATE INDEX IF NOT EXISTS idx_parameter_value_history_transaction_id
ON parameter_value_history(transaction_id);

CREATE INDEX IF NOT EXISTS idx_process_data_points_transaction_id
ON process_data_points(transaction_id);

-- Create partial indexes for non-null transaction_ids (for better performance)
CREATE INDEX IF NOT EXISTS idx_parameter_value_history_transaction_id_not_null
ON parameter_value_history(transaction_id)
WHERE transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_process_data_points_transaction_id_not_null
ON process_data_points(transaction_id)
WHERE transaction_id IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN parameter_value_history.transaction_id IS
'Transaction ID for atomic operations and rollback capability. Used by transactional data layer for ensuring data consistency.';

COMMENT ON COLUMN process_data_points.transaction_id IS
'Transaction ID for atomic operations and rollback capability. Used by transactional data layer for ensuring data consistency.';