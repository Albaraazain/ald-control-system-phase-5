-- Migration: RPC Bulk Insert for Parameter History
-- Purpose: High-performance batch insert function for Terminal 1 data collection
-- Created: 2025-10-14

-- Drop existing function if it exists
DROP FUNCTION IF EXISTS bulk_insert_parameter_history(JSONB);

-- Create optimized bulk insert function
CREATE OR REPLACE FUNCTION bulk_insert_parameter_history(records JSONB)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  inserted_count INTEGER;
BEGIN
  -- Bulk insert from JSONB array
  -- This approach minimizes overhead and executes as a single transaction
  WITH inserted AS (
    INSERT INTO parameter_value_history (parameter_id, value, timestamp)
    SELECT 
      (record->>'parameter_id')::uuid,
      (record->>'value')::double precision,
      (record->>'timestamp')::timestamptz
    FROM jsonb_array_elements(records) AS record
    RETURNING *
  )
  SELECT COUNT(*) INTO inserted_count FROM inserted;
  
  -- Return the number of successfully inserted records
  RETURN inserted_count;
  
EXCEPTION
  WHEN OTHERS THEN
    -- Log error and re-raise for client-side handling
    RAISE WARNING 'bulk_insert_parameter_history failed: %', SQLERRM;
    RAISE;
END;
$$;

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION bulk_insert_parameter_history(JSONB) TO authenticated;

-- Grant execute permissions to anonymous users (for service account)
GRANT EXECUTE ON FUNCTION bulk_insert_parameter_history(JSONB) TO anon;

-- Add comment for documentation
COMMENT ON FUNCTION bulk_insert_parameter_history(JSONB) IS 
'High-performance batch insert for parameter_value_history table. 
Accepts JSONB array of records with keys: parameter_id, value, timestamp.
Returns count of inserted records.
Used by Terminal 1 PLC Data Service for optimal data collection performance.';

