-- Migration: RPC Function for Wide Parameter Insert
-- Purpose: High-performance insert for parameter_readings wide table
-- Created: 2025-10-14

-- Drop existing function if it exists
DROP FUNCTION IF EXISTS insert_parameter_reading_wide(timestamptz, jsonb);

-- Create optimized wide insert function
CREATE OR REPLACE FUNCTION insert_parameter_reading_wide(
  p_timestamp timestamptz,
  p_params jsonb
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  insert_query text;
  columns_list text[];
  values_list text[];
  param_key text;
  param_value numeric;
  inserted_count integer := 0;
BEGIN
  -- Build dynamic INSERT based on provided parameters
  columns_list := ARRAY['timestamp'];
  values_list := ARRAY[quote_literal(p_timestamp)];
  
  -- Iterate through JSONB parameters and build column/value lists
  FOR param_key, param_value IN
    SELECT key, (value::text)::numeric
    FROM jsonb_each_text(p_params)
  LOOP
    columns_list := array_append(columns_list, param_key);
    values_list := array_append(values_list, param_value::text);
  END LOOP;
  
  -- Build and execute INSERT with ON CONFLICT to handle duplicate timestamps
  insert_query := format(
    'INSERT INTO parameter_readings (%s) VALUES (%s) 
     ON CONFLICT (timestamp) DO UPDATE SET %s',
    array_to_string(columns_list, ', '),
    array_to_string(values_list, ', '),
    array_to_string(
      ARRAY(
        SELECT format('%I = EXCLUDED.%I', col, col)
        FROM unnest(columns_list[2:]) col
      ),
      ', '
    )
  );
  
  EXECUTE insert_query;
  
  -- Return number of parameters inserted
  inserted_count := array_length(columns_list, 1) - 1;  -- Subtract timestamp column
  RETURN inserted_count;
  
EXCEPTION
  WHEN OTHERS THEN
    RAISE WARNING 'insert_parameter_reading_wide failed: %', SQLERRM;
    RAISE;
END;
$$;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION insert_parameter_reading_wide(timestamptz, jsonb) TO authenticated;
GRANT EXECUTE ON FUNCTION insert_parameter_reading_wide(timestamptz, jsonb) TO anon;

-- Add documentation
COMMENT ON FUNCTION insert_parameter_reading_wide(timestamptz, jsonb) IS 
'High-performance wide-format parameter insert for parameter_readings table.
Accepts timestamp and JSONB object with parameter columns (param_XXXXXXXX).
Returns count of parameters inserted.
Used by Terminal 1 PLC Data Service for optimal performance.
Performance: ~50-80ms vs ~180ms for narrow table bulk_insert_parameter_history.';

