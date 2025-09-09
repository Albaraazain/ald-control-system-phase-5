-- Create machine_health table for tracking connection status
CREATE TABLE IF NOT EXISTS public.machine_health (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    machine_id UUID NOT NULL REFERENCES public.machines(id),
    plc_connected BOOLEAN DEFAULT FALSE,
    plc_last_check TIMESTAMPTZ,
    plc_last_connected TIMESTAMPTZ,
    plc_reconnect_attempts INTEGER DEFAULT 0,
    plc_error TEXT,
    realtime_connected BOOLEAN DEFAULT FALSE,
    realtime_last_check TIMESTAMPTZ,
    realtime_last_message TIMESTAMPTZ,
    realtime_error TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create unique index on machine_id to ensure one health record per machine
CREATE UNIQUE INDEX IF NOT EXISTS idx_machine_health_machine_id 
ON public.machine_health(machine_id);

-- Add RLS policies
ALTER TABLE public.machine_health ENABLE ROW LEVEL SECURITY;

-- Policy for reading machine health (public read)
CREATE POLICY "Enable read access for all users" ON public.machine_health
    FOR SELECT USING (true);

-- Policy for insert/update (only authenticated users)
CREATE POLICY "Enable insert for authenticated users only" ON public.machine_health
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "Enable update for authenticated users only" ON public.machine_health
    FOR UPDATE USING (auth.role() = 'authenticated');

-- Add comment
COMMENT ON TABLE public.machine_health IS 'Real-time health monitoring data for machines including PLC and realtime connection status';