--
-- Migration: Latest Parameter Readings Table with Wide->Narrow Trigger
-- Date: 2025-10-29
-- Purpose: Create denormalized current values table with automatic sync from parameter_value_history
--
-- This migration solves the stale data problem in the Flutter UI by:
-- 1. Creating a fast-query table for current parameter values with timestamps
-- 2. Automatically syncing from parameter_value_history (wide format) via trigger
-- 3. Ensuring atomic updates (if history insert succeeds, latest values always update)
-- 4. Enabling efficient freshness checks for safety indicators
--

-- ============================================================================
-- 1. CREATE latest_parameter_readings TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS latest_parameter_readings (
    parameter_id UUID PRIMARY KEY REFERENCES component_parameters(id) ON DELETE CASCADE,
    value FLOAT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_latest_parameter_readings_timestamp
ON latest_parameter_readings(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_latest_parameter_readings_updated_at
ON latest_parameter_readings(updated_at DESC);

-- Add comment
COMMENT ON TABLE latest_parameter_readings IS
'Denormalized table of latest parameter values with timestamps.
Automatically updated by trigger from parameter_value_history (wide format).
Used by Flutter app for real-time display and freshness checking.';

COMMENT ON COLUMN latest_parameter_readings.timestamp IS
'Timestamp when the value was read from PLC (from parameter_value_history)';

COMMENT ON COLUMN latest_parameter_readings.updated_at IS
'Timestamp when this row was last updated by the trigger';


-- ============================================================================
-- 2. CREATE TRIGGER FUNCTION TO SYNC FROM WIDE TABLE
-- ============================================================================

CREATE OR REPLACE FUNCTION sync_latest_readings_from_wide()
RETURNS TRIGGER AS $$
BEGIN
    -- This function extracts parameter values from the wide-format parameter_value_history row
    -- and UPSERTs them into the narrow-format latest_parameter_readings table.
    --
    -- Each UPSERT handles one parameter:
    -- - If parameter_id exists: UPDATE value and timestamp
    -- - If parameter_id doesn't exist: INSERT new row
    --
    -- NULL checks ensure we only update parameters that have values in this reading.

    -- Float/Value parameters (10 parameters)
    IF NEW.param_0d444e71 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('0d444e71-9767-4956-af7b-787bfa79d080', NEW.param_0d444e71, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_2b2e7952 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('2b2e7952-c68e-40eb-ab67-d182fc460821', NEW.param_2b2e7952, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_35969620 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('35969620-6843-4130-8eca-d6b62dc74dbf', NEW.param_35969620, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_4567ba45 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('4567ba45-1c86-45d2-bf4d-b1cf306f387a', NEW.param_4567ba45, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_500c0329 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('500c0329-946e-48c6-9b52-c08e65bd0292', NEW.param_500c0329, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_62c28aac IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('62c28aac-7300-4d3d-85c7-f043c3226439', NEW.param_62c28aac, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_8fe19753 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('8fe19753-ebac-47ce-8461-a713b4e42695', NEW.param_8fe19753, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_b6433c16 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('b6433c16-cb13-4e6a-b5b8-1b1519f0b44b', NEW.param_b6433c16, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_dcea6a6e IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('dcea6a6e-4349-4287-9b83-4dc72410f6b1', NEW.param_dcea6a6e, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_e00b0f66 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('e00b0f66-3c05-48a1-8318-f7d1da5f628e', NEW.param_e00b0f66, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    -- Binary parameters (24 parameters)
    IF NEW.param_1583a79b IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('1583a79b-079b-4b03-9c64-53b7cfa9d142', NEW.param_1583a79b, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_264bfd7f IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('264bfd7f-6076-4b37-be09-dce51bd250c7', NEW.param_264bfd7f, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_2cadbb74 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('2cadbb74-6e87-4833-96ae-719561a6c435', NEW.param_2cadbb74, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_2d983731 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('2d983731-da39-4c5f-8576-10d2189c7743', NEW.param_2d983731, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_5adac7f8 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('5adac7f8-816a-45bb-8f6e-ca45b8b4330f', NEW.param_5adac7f8, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_5d2cfe0a IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('5d2cfe0a-151c-4745-9865-cd78125f93d0', NEW.param_5d2cfe0a, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_687cf16a IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('687cf16a-8d3d-45ce-8a94-d20ec07f6dcd', NEW.param_687cf16a, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_6c08a1b0 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('6c08a1b0-5674-46c1-9fb5-a4c4eca1adf1', NEW.param_6c08a1b0, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_6dd9ff97 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('6dd9ff97-2e16-4717-96bb-0794575f9425', NEW.param_6dd9ff97, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_73f16b0e IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('73f16b0e-6a82-4027-a1cf-66bfa16dba69', NEW.param_73f16b0e, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_8195ef00 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('8195ef00-f478-48ee-9ee0-e43cc265ef42', NEW.param_8195ef00, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_832228f7 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('832228f7-6f83-490a-b59c-5e151cbe1fb1', NEW.param_832228f7, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_846bc6d6 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('846bc6d6-04df-4318-affb-b97cf7238793', NEW.param_846bc6d6, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_84e86c3e IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('84e86c3e-7109-4b2c-9064-2aea619e6f64', NEW.param_84e86c3e, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_896208fd IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('896208fd-0e1f-49a2-9ef6-46ab0d341bee', NEW.param_896208fd, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_9917618c IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('9917618c-7325-4771-a771-65b42c6d6c73', NEW.param_9917618c, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_9c53f4ef IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('9c53f4ef-5506-4a45-9718-af8a7b233056', NEW.param_9c53f4ef, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_9fc0f785 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('9fc0f785-db56-4752-820a-4aade9962a99', NEW.param_9fc0f785, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_b52bef6d IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('b52bef6d-7656-4b9c-8ca6-0244825a7d7b', NEW.param_b52bef6d, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_b6ffc326 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('b6ffc326-6445-440f-9642-39e86953b399', NEW.param_b6ffc326, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_c6d493fa IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('c6d493fa-adf3-4784-bb80-3425dd276d49', NEW.param_c6d493fa, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_ca61248a IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('ca61248a-9be5-43d2-a204-df6f15ef4fe7', NEW.param_ca61248a, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_ea7ad0f0 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('ea7ad0f0-96ce-4c88-9b9a-bd2cde56d514', NEW.param_ea7ad0f0, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_fe5bd37b IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('fe5bd37b-742b-4383-b9c4-27693262930c', NEW.param_fe5bd37b, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    -- Read-only/sensor parameters (17 parameters)
    IF NEW.param_4d22ccb3 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('4d22ccb3-1e2d-48e1-8ffc-1d8653aea55a', NEW.param_4d22ccb3, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_5a7c8e1e IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('5a7c8e1e-eb2b-4b24-8ea2-a9d1aff699bf', NEW.param_5a7c8e1e, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_66d984b9 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('66d984b9-3503-40c4-bdb7-05bcf1833776', NEW.param_66d984b9, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_6fd0eb4a IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('6fd0eb4a-6179-4cd1-a19a-10bf45e98b92', NEW.param_6fd0eb4a, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_77207a4e IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('77207a4e-07e2-46ea-a2d6-96f144b950df', NEW.param_77207a4e, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_79bb8d15 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('79bb8d15-468b-497b-9810-9c1b913f17a8', NEW.param_79bb8d15, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_7a657f96 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('7a657f96-40ea-4f23-804a-635b716418d6', NEW.param_7a657f96, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_9562d003 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('9562d003-4c64-4914-8e6f-48134ff30389', NEW.param_9562d003, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_995f5fcd IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('995f5fcd-cf30-410e-9f58-2f51e8939439', NEW.param_995f5fcd, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_a9a93623 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('a9a93623-feea-4c76-8115-056357c3b516', NEW.param_a9a93623, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_aea1df61 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('aea1df61-6f23-4077-9312-9244db9b3894', NEW.param_aea1df61, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_aedcf5fe IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('aedcf5fe-ce01-4f03-97a1-025224f8fd4f', NEW.param_aedcf5fe, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_af4f85cd IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('af4f85cd-f0a6-46ac-b2c9-5caa1117899b', NEW.param_af4f85cd, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_b906ef85 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('b906ef85-1915-40ba-898c-0595753e645e', NEW.param_b906ef85, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_cea58380 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('cea58380-2919-483e-b03f-d720b71ecf9f', NEW.param_cea58380, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_e583bb2c IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('e583bb2c-c135-4b0f-97e0-8e074a274a44', NEW.param_e583bb2c, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    IF NEW.param_e76932c8 IS NOT NULL THEN
        INSERT INTO latest_parameter_readings (parameter_id, value, timestamp)
        VALUES ('e76932c8-3ba3-4f74-849e-2b692eba6ff4', NEW.param_e76932c8, NEW.timestamp)
        ON CONFLICT (parameter_id)
        DO UPDATE SET
            value = EXCLUDED.value,
            timestamp = EXCLUDED.timestamp,
            updated_at = NOW();
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add comment
COMMENT ON FUNCTION sync_latest_readings_from_wide() IS
'Trigger function that extracts parameter values from wide-format parameter_value_history
and UPSERTs them into narrow-format latest_parameter_readings table.
Handles all 51 parameters with NULL checks to skip missing values.';


-- ============================================================================
-- 3. CREATE TRIGGER
-- ============================================================================

DROP TRIGGER IF EXISTS sync_latest_readings_trigger ON parameter_value_history;

CREATE TRIGGER sync_latest_readings_trigger
AFTER INSERT ON parameter_value_history
FOR EACH ROW
EXECUTE FUNCTION sync_latest_readings_from_wide();

COMMENT ON TRIGGER sync_latest_readings_trigger ON parameter_value_history IS
'Automatically syncs latest parameter values from parameter_value_history (wide)
to latest_parameter_readings (narrow) on every insert.
Ensures atomic updates: if history insert succeeds, latest values always update.';


-- ============================================================================
-- 4. ENABLE ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE latest_parameter_readings ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (for Terminal 1 writes)
CREATE POLICY "Service role has full access"
ON latest_parameter_readings
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Allow authenticated users to read their machine's parameters
CREATE POLICY "Users can read their machine parameters"
ON latest_parameter_readings
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM component_parameters cp
        WHERE cp.id = parameter_id
        AND cp.machine_id IN (
            SELECT machine_id FROM user_machine_assignments
            WHERE user_id = auth.uid() AND is_active = true
        )
    )
);


-- ============================================================================
-- 5. VERIFICATION QUERIES
-- ============================================================================

-- Query to check trigger is working (run after Terminal 1 collects data):
-- SELECT
--     lpr.parameter_id,
--     lpr.value,
--     lpr.timestamp,
--     NOW() - lpr.timestamp AS age,
--     CASE
--         WHEN NOW() - lpr.timestamp < INTERVAL '2 seconds' THEN 'FRESH'
--         WHEN NOW() - lpr.timestamp < INTERVAL '10 seconds' THEN 'STALE'
--         ELSE 'DISCONNECTED'
--     END AS freshness_status
-- FROM latest_parameter_readings lpr
-- ORDER BY lpr.timestamp DESC
-- LIMIT 10;

-- Query to verify all parameters are being synced:
-- SELECT COUNT(*) as total_parameters,
--        COUNT(DISTINCT parameter_id) as parameters_with_data,
--        MAX(timestamp) as most_recent_reading,
--        NOW() - MAX(timestamp) as time_since_last_reading
-- FROM latest_parameter_readings;
