'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { useDashboardStore } from '@/lib/store/dashboard-store'
import type {
  Recipe,
  ProcessExecutionWithRecipe,
  RecipeStep,
  ComponentParameter,
} from '@/lib/store/dashboard-store'

const MACHINE_ID = process.env.NEXT_PUBLIC_MACHINE_ID!

/**
 * Hook for loading initial dashboard data
 * Implements data loaders from HTML lines 427-488
 */
export function useDashboardData() {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const {
    setRecipes,
    setCurrentProcess,
    setSteps,
    initializeStepExecutions,
    initializeComponents,
    addLog,
  } = useDashboardStore()

  useEffect(() => {
    let mounted = true

    async function loadInitialData() {
      try {
        const supabase = createClient()

        // Step 1: Load recipes (HTML lines 427-436)
        addLog('Loading recipes...')
        const recipes = await loadRecipes(supabase)
        if (!mounted) return
        setRecipes(recipes)
        addLog(`Loaded ${recipes.length} recipes`)

        // Step 2: Load active process (HTML lines 438-449)
        addLog('Checking for active process...')
        const activeProcess = await loadActiveProcess(supabase)
        if (!mounted) return
        setCurrentProcess(activeProcess)

        if (activeProcess) {
          addLog(`Active process: ${activeProcess.recipes?.name || 'Unknown'}`)

          // Step 3: Load recipe steps (HTML lines 451-459)
          addLog('Loading recipe steps...')
          const steps = await loadRecipeSteps(supabase, activeProcess.recipe_id)
          if (!mounted) return
          setSteps(steps)
          addLog(`Loaded ${steps.length} steps`)

          // Step 4: Load step history (HTML lines 479-488)
          addLog('Loading step history...')
          const history = await loadStepHistory(supabase, activeProcess.id)
          if (!mounted) return
          const executions = history.map((h) => ({
            step_order: h.step_order,
            execution: {
              status: h.status,
              started_at: h.started_at,
              completed_at: h.completed_at,
            },
          }))
          initializeStepExecutions(executions)
          addLog(`Loaded ${history.length} step executions`)
        } else {
          addLog('No active process')
        }

        // Step 5: Load components (HTML lines 461-477)
        addLog('Loading components...')
        const components = await loadComponents(supabase)
        if (!mounted) return
        initializeComponents(components)
        addLog(`Loaded ${components.length} components`)

        setIsLoading(false)
        addLog('Dashboard initialized')
      } catch (err) {
        console.error('Failed to load dashboard data:', err)
        if (mounted) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to load data'
          setError(errorMsg)
          addLog(`❌ Error: ${errorMsg}`)
          setIsLoading(false)
        }
      }
    }

    loadInitialData()

    return () => {
      mounted = false
    }
  }, [setRecipes, setCurrentProcess, setSteps, initializeStepExecutions, initializeComponents, addLog])

  return { isLoading, error }
}

/**
 * Load all recipes (schema has no machine_id field)
 */
async function loadRecipes(supabase: ReturnType<typeof createClient>): Promise<Recipe[]> {
  const { data, error } = await supabase
    .from('recipes')
    .select('id, name')
    .order('name', { ascending: true })

  if (error) {
    console.warn('recipes error', error)
    return []
  }
  return (data || []) as Recipe[]
}

/**
 * Load active process for this machine
 * Schema uses start_time/end_time, not started_at/completed_at
 * current_step_index is in process_execution_state table
 */
async function loadActiveProcess(
  supabase: ReturnType<typeof createClient>
): Promise<ProcessExecutionWithRecipe | null> {
  // First get the running process
  const { data: processData, error: processError } = await supabase
    .from('process_executions')
    .select(`
      id,
      recipe_id,
      status,
      start_time,
      end_time,
      recipes(name)
    `)
    .eq('machine_id', MACHINE_ID)
    .eq('status', 'running')
    .order('start_time', { ascending: false })
    .limit(1)
    .maybeSingle()

  if (processError || !processData) {
    console.warn('process error', processError)
    return null
  }

  // Get current_step_index from process_execution_state
  const { data: stateData } = await supabase
    .from('process_execution_state')
    .select('current_step_index')
    .eq('execution_id', processData.id)
    .maybeSingle()

  return {
    id: processData.id,
    recipe_id: processData.recipe_id,
    status: processData.status,
    started_at: processData.start_time,
    completed_at: processData.end_time,
    current_step_index: stateData?.current_step_index || 0,
    recipes: processData.recipes as { name: string; total_steps: number } | null,
  } as ProcessExecutionWithRecipe
}

/**
 * Load recipe steps ordered by sequence_number (not step_order)
 * Schema fields: id, recipe_id, sequence_number, name, description, type, parent_step_id
 */
async function loadRecipeSteps(
  supabase: ReturnType<typeof createClient>,
  recipeId: string
): Promise<RecipeStep[]> {
  const { data, error } = await supabase
    .from('recipe_steps')
    .select('id, recipe_id, sequence_number, name, description, type, parent_step_id, created_at')
    .eq('recipe_id', recipeId)
    .order('sequence_number', { ascending: true })

  if (error) {
    console.warn('steps error', error)
    return []
  }

  // Map sequence_number to step_order for compatibility with store
  return (data || []).map(step => ({
    ...step,
    step_order: step.sequence_number,
    action: null,
    duration: null,
    step_type: step.type,
  })) as RecipeStep[]
}

/**
 * Load components using component_parameters_full view
 * This view has machine_id, component_name, component_type already joined
 * Schema field is set_value (not target_value)
 */
async function loadComponents(supabase: ReturnType<typeof createClient>): Promise<ComponentParameter[]> {
  const { data, error } = await supabase
    .from('component_parameters_full')
    .select('id, component_name, component_type, current_value, set_value, updated_at')
    .eq('machine_id', MACHINE_ID)
    .in('component_type', ['valve', 'mfc', 'chamber_heater'])

  if (error) {
    console.warn('components error', error)
    return []
  }

  return (data || []).map((row) => ({
    id: row.id,
    name: row.component_name,
    type: row.component_type,
    current_value: row.current_value,
    target_value: row.set_value,
    updated_at: row.updated_at,
  })) as ComponentParameter[]
}

/**
 * Load step execution history
 * Table is step_execution_history (not recipe_step_executions)
 * Schema fields: id, process_id, step_number, step_name, step_type, started_at, ended_at
 */
async function loadStepHistory(
  supabase: ReturnType<typeof createClient>,
  processId: string
): Promise<any[]> {
  const { data, error } = await supabase
    .from('step_execution_history')
    .select('id, step_number, step_name, step_type, started_at, ended_at')
    .eq('process_id', processId)
    .order('started_at', { ascending: false })
    .limit(20)

  if (error) {
    console.warn('history error', error)
    return []
  }

  // Map step_number to step_order and ended_at to completed_at
  return (data || []).map(h => ({
    step_order: h.step_number,
    status: h.ended_at ? 'completed' : 'running',
    started_at: h.started_at,
    completed_at: h.ended_at,
  }))
}
