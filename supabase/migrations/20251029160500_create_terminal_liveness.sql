-- Migration: Terminal Liveness Management System
-- Purpose: Track terminal instance health, prevent duplicates, enable monitoring and auto-recovery
-- Author: Claude Code
-- Date: 2025-10-29

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE terminal_type AS ENUM (
    'terminal1',  -- PLC Read Service
    'terminal2',  -- Recipe Execution Service
    'terminal3'   -- Parameter Control Service
);

CREATE TYPE terminal_status AS ENUM (
    'starting',   -- Terminal is initializing
    'healthy',    -- Terminal is running normally
    'degraded',   -- Terminal is running but experiencing issues
    'stopping',   -- Terminal is shutting down gracefully
    'stopped',    -- Terminal has stopped gracefully
    'crashed'     -- Terminal died unexpectedly (detected by missed heartbeats)
);

-- ============================================================
-- MAIN TABLE: terminal_instances
-- ============================================================

CREATE TABLE terminal_instances (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Terminal identification
    terminal_type terminal_type NOT NULL,
    machine_id UUID NOT NULL REFERENCES machines_base(id) ON DELETE CASCADE,

    -- Process information
    hostname TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    python_version TEXT,
    git_commit_hash TEXT,

    -- Status tracking
    status terminal_status NOT NULL DEFAULT 'starting',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_heartbeat TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    crash_detected_at TIMESTAMPTZ,

    -- Health metrics
    heartbeat_interval_seconds INTEGER NOT NULL DEFAULT 10,
    missed_heartbeats INTEGER NOT NULL DEFAULT 0,
    commands_processed INTEGER NOT NULL DEFAULT 0,
    errors_encountered INTEGER NOT NULL DEFAULT 0,
    avg_command_latency_ms INTEGER,
    last_error_message TEXT,
    last_error_at TIMESTAMPTZ,

    -- Operational metadata
    environment TEXT CHECK (environment IN ('production', 'development', 'testing')),
    log_file_path TEXT,
    config JSONB DEFAULT '{}',

    -- Performance metrics (updated periodically)
    cpu_percent NUMERIC(5,2),
    memory_mb INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CRITICAL CONSTRAINT: Only ONE active terminal per type per machine
-- ============================================================

CREATE UNIQUE INDEX idx_terminal_active_unique
ON terminal_instances(terminal_type, machine_id)
WHERE status IN ('starting', 'healthy', 'degraded', 'stopping');

COMMENT ON INDEX idx_terminal_active_unique IS 'Ensures only one active terminal instance per type per machine. Prevents race conditions and duplicate processes.';

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

-- Find all active terminals quickly
CREATE INDEX idx_terminal_status ON terminal_instances(status)
WHERE status IN ('starting', 'healthy', 'degraded');

-- Find terminals by machine
CREATE INDEX idx_terminal_machine ON terminal_instances(machine_id, terminal_type);

-- Find terminals needing health check (dead detection)
CREATE INDEX idx_terminal_heartbeat ON terminal_instances(last_heartbeat)
WHERE status IN ('starting', 'healthy', 'degraded');

-- Recent terminal history
CREATE INDEX idx_terminal_started ON terminal_instances(started_at DESC);

-- ============================================================
-- AUDIT TABLE: terminal_health_history
-- ============================================================

CREATE TABLE terminal_health_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    terminal_instance_id UUID NOT NULL REFERENCES terminal_instances(id) ON DELETE CASCADE,

    -- Status change
    previous_status terminal_status,
    new_status terminal_status NOT NULL,

    -- Context
    reason TEXT,
    error_details TEXT,

    -- Metrics at time of change
    uptime_seconds INTEGER,
    commands_processed INTEGER,
    errors_encountered INTEGER,

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_health_history_terminal ON terminal_health_history(terminal_instance_id, created_at DESC);
CREATE INDEX idx_health_history_status ON terminal_health_history(new_status, created_at DESC);

COMMENT ON TABLE terminal_health_history IS 'Audit trail of terminal status changes for debugging and analysis';

-- ============================================================
-- TABLE COMMENTS
-- ============================================================

COMMENT ON TABLE terminal_instances IS 'Tracks all terminal instances (Terminal 1/2/3) with health status, heartbeats, and metrics. Enables duplicate prevention, health monitoring, and auto-recovery.';

COMMENT ON COLUMN terminal_instances.terminal_type IS 'Type of terminal: terminal1 (PLC Read), terminal2 (Recipe Execution), terminal3 (Parameter Control)';
COMMENT ON COLUMN terminal_instances.machine_id IS 'Machine this terminal is serving';
COMMENT ON COLUMN terminal_instances.hostname IS 'Hostname where terminal is running (for distributed deployments)';
COMMENT ON COLUMN terminal_instances.process_id IS 'OS process ID (PID) for terminal process';
COMMENT ON COLUMN terminal_instances.python_version IS 'Python version running the terminal';
COMMENT ON COLUMN terminal_instances.git_commit_hash IS 'Git commit hash of deployed code';
COMMENT ON COLUMN terminal_instances.status IS 'Current health status of terminal';
COMMENT ON COLUMN terminal_instances.started_at IS 'When terminal started';
COMMENT ON COLUMN terminal_instances.last_heartbeat IS 'Last heartbeat received from terminal';
COMMENT ON COLUMN terminal_instances.stopped_at IS 'When terminal stopped (graceful shutdown)';
COMMENT ON COLUMN terminal_instances.crash_detected_at IS 'When terminal crash was detected (missed heartbeats)';
COMMENT ON COLUMN terminal_instances.heartbeat_interval_seconds IS 'How often terminal should send heartbeat (default 10s)';
COMMENT ON COLUMN terminal_instances.missed_heartbeats IS 'Counter of consecutive missed heartbeats';
COMMENT ON COLUMN terminal_instances.commands_processed IS 'Total commands/operations processed by this terminal';
COMMENT ON COLUMN terminal_instances.errors_encountered IS 'Total errors encountered by this terminal';
COMMENT ON COLUMN terminal_instances.avg_command_latency_ms IS 'Average command processing latency in milliseconds';
COMMENT ON COLUMN terminal_instances.environment IS 'Deployment environment (production, development, testing)';
COMMENT ON COLUMN terminal_instances.log_file_path IS 'Path to terminal log file for debugging';
COMMENT ON COLUMN terminal_instances.config IS 'JSONB configuration used by terminal';

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Function: Calculate terminal uptime
CREATE OR REPLACE FUNCTION get_terminal_uptime(terminal_instance_id UUID)
RETURNS INTERVAL AS $$
DECLARE
    instance RECORD;
    end_time TIMESTAMPTZ;
BEGIN
    SELECT started_at, stopped_at, status INTO instance
    FROM terminal_instances
    WHERE id = terminal_instance_id;

    IF instance.status IN ('stopped', 'crashed') THEN
        end_time := COALESCE(instance.stopped_at, NOW());
    ELSE
        end_time := NOW();
    END IF;

    RETURN end_time - instance.started_at;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_terminal_uptime IS 'Calculate uptime for a terminal instance (now - started_at or stopped_at - started_at)';

-- Function: Detect dead terminals
CREATE OR REPLACE FUNCTION detect_dead_terminals(heartbeat_timeout_seconds INTEGER DEFAULT 30)
RETURNS TABLE(
    terminal_id UUID,
    terminal_type terminal_type,
    machine_id UUID,
    last_heartbeat TIMESTAMPTZ,
    seconds_since_heartbeat INTEGER,
    hostname TEXT,
    process_id INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ti.id,
        ti.terminal_type,
        ti.machine_id,
        ti.last_heartbeat,
        EXTRACT(EPOCH FROM (NOW() - ti.last_heartbeat))::INTEGER as seconds_since_heartbeat,
        ti.hostname,
        ti.process_id
    FROM terminal_instances ti
    WHERE ti.status IN ('starting', 'healthy', 'degraded')
      AND ti.last_heartbeat < NOW() - (heartbeat_timeout_seconds || ' seconds')::INTERVAL
    ORDER BY ti.last_heartbeat;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_dead_terminals IS 'Find terminals that have not sent heartbeat within timeout period (default 30s = 3 missed heartbeats)';

-- Function: Mark terminal as crashed
CREATE OR REPLACE FUNCTION mark_terminal_crashed(terminal_instance_id UUID, crash_reason TEXT DEFAULT 'Missed heartbeats')
RETURNS VOID AS $$
DECLARE
    old_status terminal_status;
    uptime_secs INTEGER;
BEGIN
    -- Get current status
    SELECT status INTO old_status FROM terminal_instances WHERE id = terminal_instance_id;

    -- Calculate uptime
    SELECT EXTRACT(EPOCH FROM get_terminal_uptime(terminal_instance_id))::INTEGER INTO uptime_secs;

    -- Update terminal status
    UPDATE terminal_instances
    SET status = 'crashed',
        crash_detected_at = NOW(),
        updated_at = NOW()
    WHERE id = terminal_instance_id;

    -- Record status change in history
    INSERT INTO terminal_health_history (
        terminal_instance_id,
        previous_status,
        new_status,
        reason,
        uptime_seconds,
        commands_processed,
        errors_encountered
    )
    SELECT
        terminal_instance_id,
        old_status,
        'crashed'::terminal_status,
        crash_reason,
        uptime_secs,
        commands_processed,
        errors_encountered
    FROM terminal_instances
    WHERE id = terminal_instance_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mark_terminal_crashed IS 'Mark terminal as crashed and record in health history';

-- ============================================================
-- TRIGGER: Update updated_at timestamp
-- ============================================================

CREATE OR REPLACE FUNCTION update_terminal_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER terminal_instances_updated_at
    BEFORE UPDATE ON terminal_instances
    FOR EACH ROW
    EXECUTE FUNCTION update_terminal_updated_at();

-- ============================================================
-- TRIGGER: Record status changes in health history
-- ============================================================

CREATE OR REPLACE FUNCTION record_terminal_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only record if status actually changed
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO terminal_health_history (
            terminal_instance_id,
            previous_status,
            new_status,
            uptime_seconds,
            commands_processed,
            errors_encountered
        ) VALUES (
            NEW.id,
            OLD.status,
            NEW.status,
            EXTRACT(EPOCH FROM (NOW() - NEW.started_at))::INTEGER,
            NEW.commands_processed,
            NEW.errors_encountered
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER terminal_status_change_audit
    AFTER UPDATE ON terminal_instances
    FOR EACH ROW
    WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION record_terminal_status_change();

-- ============================================================
-- HELPER VIEWS
-- ============================================================

-- View: Active terminals with health indicators
CREATE VIEW active_terminals AS
SELECT
    ti.id,
    ti.terminal_type,
    ti.machine_id,
    mb.serial_number as machine_serial,
    ti.hostname,
    ti.process_id,
    ti.status,
    ti.started_at,
    ti.last_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - ti.last_heartbeat))::INTEGER as seconds_since_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - ti.started_at))::INTEGER as uptime_seconds,
    ti.commands_processed,
    ti.errors_encountered,
    ti.avg_command_latency_ms,
    ti.environment,
    CASE
        WHEN ti.status = 'crashed' THEN '❌ Crashed'
        WHEN ti.status IN ('starting', 'healthy', 'degraded') AND
             ti.last_heartbeat < NOW() - INTERVAL '30 seconds' THEN '⚠️ Dead (No heartbeat)'
        WHEN ti.status = 'degraded' THEN '⚠️ Degraded'
        WHEN ti.status = 'healthy' THEN '✅ Healthy'
        WHEN ti.status = 'stopping' THEN '🛑 Stopping'
        ELSE ti.status::TEXT
    END as health_indicator
FROM terminal_instances ti
LEFT JOIN machines_base mb ON ti.machine_id = mb.id
WHERE ti.status IN ('starting', 'healthy', 'degraded', 'stopping')
ORDER BY ti.terminal_type, ti.machine_id;

COMMENT ON VIEW active_terminals IS 'Convenient view of active terminals with health indicators and metrics';

-- View: Terminal health summary
CREATE VIEW terminal_health_summary AS
SELECT
    ti.terminal_type,
    ti.machine_id,
    ti.status,
    COUNT(*) as instance_count,
    AVG(EXTRACT(EPOCH FROM (NOW() - ti.started_at)))::INTEGER as avg_uptime_seconds,
    SUM(ti.commands_processed) as total_commands,
    SUM(ti.errors_encountered) as total_errors,
    MAX(ti.last_heartbeat) as most_recent_heartbeat
FROM terminal_instances ti
WHERE ti.created_at > NOW() - INTERVAL '24 hours'
GROUP BY ti.terminal_type, ti.machine_id, ti.status;

COMMENT ON VIEW terminal_health_summary IS 'Summary statistics of terminal health over last 24 hours';

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================

ALTER TABLE terminal_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE terminal_health_history ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view terminals for their assigned machines
CREATE POLICY terminal_instances_select_policy ON terminal_instances
    FOR SELECT
    USING (
        machine_id IN (
            SELECT machine_id
            FROM user_machine_assignments
            WHERE user_id = auth.uid()
            AND is_active = true
        )
    );

-- Policy: Service role can do everything (terminals run as service role)
CREATE POLICY terminal_instances_service_policy ON terminal_instances
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Policy: Admins can see everything
CREATE POLICY terminal_instances_admin_policy ON terminal_instances
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM profiles
            WHERE id = auth.uid()
            AND role = 'admin'
        )
    );

-- Similar policies for health history
CREATE POLICY terminal_health_select_policy ON terminal_health_history
    FOR SELECT
    USING (
        terminal_instance_id IN (
            SELECT id FROM terminal_instances
            WHERE machine_id IN (
                SELECT machine_id
                FROM user_machine_assignments
                WHERE user_id = auth.uid()
                AND is_active = true
            )
        )
    );

CREATE POLICY terminal_health_service_policy ON terminal_health_history
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- GRANTS
-- ============================================================

GRANT SELECT ON terminal_instances TO authenticated;
GRANT SELECT ON terminal_health_history TO authenticated;
GRANT SELECT ON active_terminals TO authenticated;
GRANT SELECT ON terminal_health_summary TO authenticated;

GRANT ALL ON terminal_instances TO service_role;
GRANT ALL ON terminal_health_history TO service_role;

-- Grant execute on functions
GRANT EXECUTE ON FUNCTION get_terminal_uptime TO authenticated;
GRANT EXECUTE ON FUNCTION detect_dead_terminals TO authenticated;
GRANT EXECUTE ON FUNCTION mark_terminal_crashed TO service_role;
