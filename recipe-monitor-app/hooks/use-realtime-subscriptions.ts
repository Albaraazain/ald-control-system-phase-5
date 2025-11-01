'use client'

import { useEffect } from 'react'
import { createClient } from '@/lib/supabase/client'
import { useDashboardStore } from '@/lib/store/dashboard-store'
import type { ComponentParameter } from '@/lib/store/dashboard-store'
import type { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js'
import type { ProcessExecution, ComponentParameter as ComponentParameterDB, RecipeStepExecution } from '@/lib/types/database'

const MACHINE_ID = process.env.NEXT_PUBLIC_MACHINE_ID!

/**
 * Hook for subscribing to realtime database updates
 * Implements subscription logic from HTML lines 493-604
 */
export function useRealtimeSubscriptions() {
  const {
    currentProcess,
    setCurrentProcess,
    setSteps,
    updateStepExecution,
    updateComponent,
    addLog,
    componentsIndex,
  } = useDashboardStore()

  useEffect(() => {
    const supabase = createClient()
    const channels: RealtimeChannel[] = []

    // Subscribe to process_executions for this machine (HTML lines 493-498)
    const processChannel = supabase
      .channel('process-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'process_executions',
          filter: `machine_id=eq.${MACHINE_ID}`,
        },
        async (payload: RealtimePostgresChangesPayload<ProcessExecution>) => {
          const row = (payload.new || payload.old) as ProcessExecution
          if (!row || !row.id) return

          // Reload active process context (HTML lines 520-545)
          if (!currentProcess || row.id === currentProcess.id || row.status === 'running') {
            const previousStatus = currentProcess?.status

            // Reload active process
            const { data, error } = await supabase
              .from('process_executions')
              .select(`id, recipe_id, status, current_step_index, started_at, completed_at, recipes(name)`)
              .eq('machine_id', MACHINE_ID)
              .eq('status', 'running')
              .order('started_at', { ascending: false })
              .limit(1)
              .maybeSingle()

            if (error) {
              console.warn('process reload error', error)
              return
            }

            const activeProcess = data ? (data as any) : null
            setCurrentProcess(activeProcess)

            if (!activeProcess) {
              // Process ended
              setSteps([])
              addLog(`Process ${row.id} ${row.status}`)
              return
            }

            // Status change log
            if (previousStatus && previousStatus !== activeProcess.status) {
              addLog(`Process is now ${activeProcess.status.toUpperCase()}`)
            }

            // Reload steps for new or updated process
            const { data: stepsData, error: stepsError } = await supabase
              .from('recipe_steps')
              .select('*')
              .eq('recipe_id', activeProcess.recipe_id)
              .order('step_order', { ascending: true })

            if (!stepsError && stepsData) {
              setSteps(stepsData as any)
            }
          }
        }
      )
      .subscribe()
    channels.push(processChannel)

    // Subscribe to component_parameters (no machine_id filter since it doesn't exist on this table)
    // Filter by machine in the handler using componentsIndex
    const componentChannel = supabase
      .channel('component-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'component_parameters',
        },
        (payload: RealtimePostgresChangesPayload<ComponentParameterDB>) => {
          const comp = payload.new as ComponentParameterDB
          if (!comp || !comp.id) return

          // Filter to only components we care about (from this machine)
          // componentsIndex only contains components loaded for this machine
          const existing = componentsIndex.get(comp.id)
          if (!existing) return // Ignore updates for components not on this machine

          // Update component state
          updateComponent(comp.id, {
            id: comp.id,
            current_value: comp.current_value,
            target_value: comp.set_value, // Note: database has set_value, not target_value
            updated_at: comp.updated_at,
          } as Partial<ComponentParameter>)

          // Derive human-readable log message
          const val = Number(comp.current_value ?? 0)
          const name = existing.name || `Component ${comp.id}`
          if (existing.type === 'valve') {
            const state = val >= 0.999 ? 'OPENED' : val <= 0.001 ? 'CLOSED' : 'PARTIAL'
            addLog(`${name}: ${state}`)
          } else if (existing.type === 'mfc') {
            addLog(`${name}: ${val.toFixed(0)} sccm`)
          } else if (existing.type === 'chamber_heater') {
            const tgt = comp.set_value != null ? Number(comp.set_value).toFixed(0) : '--'
            addLog(`${name}: ${val.toFixed(0)}°C / ${tgt}°C`)
          }
        }
      )
      .subscribe()
    channels.push(componentChannel)

    // Subscribe to step_execution_history (actual table name)
    // Filter by current process inside handler
    const stepChannel = supabase
      .channel('step-updates')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'step_execution_history',
        },
        (payload: RealtimePostgresChangesPayload<any>) => {
          const s = payload.new as any
          if (!s || !s.id) return

          // Only reflect for the active process (process_id is the correct column name)
          if (currentProcess && s.process_id !== currentProcess.id) return

          // Update execution state (step_number is the correct column name)
          // Derive status from started_at/ended_at since there's no status column
          const status = s.ended_at ? 'completed' : s.started_at ? 'running' : 'pending'
          updateStepExecution(s.step_number, {
            status,
            started_at: s.started_at,
            completed_at: s.ended_at, // ended_at is the correct column name
          })
        }
      )
      .subscribe()
    channels.push(stepChannel)

    addLog('Realtime subscriptions active')

    // Cleanup subscriptions on unmount
    return () => {
      channels.forEach((channel) => {
        supabase.removeChannel(channel)
      })
      addLog('Realtime subscriptions closed')
    }
  }, [currentProcess, setCurrentProcess, setSteps, updateStepExecution, updateComponent, addLog, componentsIndex])
}
