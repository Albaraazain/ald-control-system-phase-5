-- Step Execution History: Table, Functions, Triggers (idempotent)

-- 1) Table: public.step_execution_history
CREATE TABLE IF NOT EXISTS public.step_execution_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  process_id uuid NOT NULL REFERENCES public.process_executions(id),
  step_number integer,
  step_type text,
  step_name text,
  started_at timestamptz DEFAULT now(),
  ended_at timestamptz,
  parameters jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_step_execution_history_proc_started_at
  ON public.step_execution_history (process_id, started_at);

CREATE INDEX IF NOT EXISTS idx_step_execution_history_open_by_process
  ON public.step_execution_history (process_id)
  WHERE ended_at IS NULL;

-- 2) Function: public.fn_record_step_history()
CREATE OR REPLACE FUNCTION public.fn_record_step_history()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF (NEW.current_step_index IS DISTINCT FROM OLD.current_step_index)
     OR (NEW.current_step_type IS DISTINCT FROM OLD.current_step_type)
     OR (NEW.current_step_name IS DISTINCT FROM OLD.current_step_name) THEN

    -- Close any open history rows for this process
    UPDATE public.step_execution_history
    SET ended_at = now()
    WHERE process_id = NEW.execution_id
      AND ended_at IS NULL;

    -- Insert a new step history row
    INSERT INTO public.step_execution_history (
      process_id, step_number, step_type, step_name, started_at, parameters
    )
    VALUES (
      NEW.execution_id,
      COALESCE(NEW.current_overall_step, NEW.current_step_index),
      NEW.current_step_type,
      NEW.current_step_name,
      now(),
      jsonb_strip_nulls(
        jsonb_build_object(
          'current_step', NEW.current_step,
          'valve_number', NEW.current_valve_number,
          'valve_duration_ms', NEW.current_valve_duration_ms,
          'purge_duration_ms', NEW.current_purge_duration_ms,
          'parameter_id', NEW.current_parameter_id,
          'parameter_value', NEW.current_parameter_value,
          'loop_count', NEW.current_loop_count,
          'loop_iteration', NEW.current_loop_iteration
        )
      )
    );
  END IF;

  RETURN NEW;
END;
$$;

-- 3) Trigger: trg_process_state_history on public.process_execution_state
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_trigger
    WHERE tgname = 'trg_process_state_history'
      AND tgrelid = 'public.process_execution_state'::regclass
  ) THEN
    CREATE TRIGGER trg_process_state_history
    AFTER UPDATE ON public.process_execution_state
    FOR EACH ROW
    WHEN (
      (NEW.current_step_index IS DISTINCT FROM OLD.current_step_index)
      OR (NEW.current_step_type IS DISTINCT FROM OLD.current_step_type)
      OR (NEW.current_step_name IS DISTINCT FROM OLD.current_step_name)
    )
    EXECUTE FUNCTION public.fn_record_step_history();
  END IF;
END;
$$;

-- 4) Function + Trigger to close open step history rows when process ends
CREATE OR REPLACE FUNCTION public.fn_close_open_step_history_on_process_end()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF (NEW.status IS DISTINCT FROM OLD.status)
     AND (NEW.status IN ('completed','failed','aborted')) THEN
    UPDATE public.step_execution_history
    SET ended_at = now()
    WHERE process_id = NEW.id
      AND ended_at IS NULL;
  END IF;

  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_trigger
    WHERE tgname = 'trg_process_end_close_history'
      AND tgrelid = 'public.process_executions'::regclass
  ) THEN
    CREATE TRIGGER trg_process_end_close_history
    AFTER UPDATE ON public.process_executions
    FOR EACH ROW
    WHEN (
      (NEW.status IS DISTINCT FROM OLD.status)
      AND (NEW.status IN ('completed','failed','aborted'))
    )
    EXECUTE FUNCTION public.fn_close_open_step_history_on_process_end();
  END IF;
END;
$$;

-- 5) ROLLBACK SECTION (commented out)
-- To rollback, run the following statements manually:
--
-- DROP TRIGGER IF EXISTS trg_process_state_history ON public.process_execution_state;
-- DROP TRIGGER IF EXISTS trg_process_end_close_history ON public.process_executions;
-- DROP FUNCTION IF EXISTS public.fn_record_step_history();
-- DROP FUNCTION IF EXISTS public.fn_close_open_step_history_on_process_end();
-- Optional: drop the history table (will remove historical data!)
-- DROP TABLE IF EXISTS public.step_execution_history;

