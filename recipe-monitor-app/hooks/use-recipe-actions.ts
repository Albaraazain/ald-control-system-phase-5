'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { useDashboardStore } from '@/lib/store/dashboard-store'
import { useToast } from './use-toast'
import type { RecipeCommandInsert } from '@/lib/types/database'

const MACHINE_ID = process.env.NEXT_PUBLIC_MACHINE_ID!

/**
 * Hook for recipe command actions
 * Implements actions from HTML lines 610-658
 */
export function useRecipeActions() {
  const [isLoading, setIsLoading] = useState(false)
  const { currentProcess, addLog } = useDashboardStore()
  const { showToast, showSuccess, showError } = useToast()

  /**
   * Start a recipe by inserting a command into recipe_commands table
   * Schema: recipe_commands has recipe_step_id (nullable) and type fields
   * For whole-recipe commands, recipe_step_id is null and recipe_id goes in parameters
   */
  const startRecipe = async (recipeId: string) => {
    if (!recipeId) {
      showToast('Select a recipe first')
      return
    }

    setIsLoading(true)
    try {
      const supabase = createClient()
      const command = {
        recipe_step_id: null,
        machine_id: MACHINE_ID,
        type: 'start',
        status: 'pending',
        parameters: { recipe_id: recipeId },
      }
      const { data, error } = await supabase
        .from('recipe_commands')
        .insert(command)
        .select()

      if (error) {
        showError(`⚠️ ${error.message}`)
        return
      }

      showSuccess('✅ Recipe command sent! Watch Terminal 2 process it.')
      addLog(`Command: start recipe ${recipeId}`)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to start recipe'
      showError(`⚠️ ${errorMsg}`)
      console.error('Start recipe error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Pause the current recipe
   * Schema: recipe_commands has recipe_step_id (nullable) and type fields
   */
  const pauseRecipe = async () => {
    if (!currentProcess) {
      showToast('No active process to pause')
      return
    }

    setIsLoading(true)
    try {
      const supabase = createClient()
      const command = {
        recipe_step_id: null,
        machine_id: MACHINE_ID,
        type: 'pause',
        status: 'pending',
        parameters: { recipe_id: currentProcess.recipe_id },
      }
      const { error } = await supabase
        .from('recipe_commands')
        .insert(command)

      if (error) {
        showError(`⚠️ ${error.message}`)
        return
      }

      showToast('⏸ Pause requested')
      addLog('Command: pause')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to pause recipe'
      showError(`⚠️ ${errorMsg}`)
      console.error('Pause recipe error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  /**
   * Stop the current recipe
   * Schema: recipe_commands has recipe_step_id (nullable) and type fields
   */
  const stopRecipe = async () => {
    if (!currentProcess) {
      showToast('No active process to stop')
      return
    }

    setIsLoading(true)
    try {
      const supabase = createClient()
      const command = {
        recipe_step_id: null,
        machine_id: MACHINE_ID,
        type: 'stop',
        status: 'pending',
        parameters: { recipe_id: currentProcess.recipe_id },
      }
      const { error } = await supabase
        .from('recipe_commands')
        .insert(command)

      if (error) {
        showError(`⚠️ ${error.message}`)
        return
      }

      showToast('🛑 Stop requested')
      addLog('Command: stop')
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to stop recipe'
      showError(`⚠️ ${errorMsg}`)
      console.error('Stop recipe error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  return {
    startRecipe,
    pauseRecipe,
    stopRecipe,
    isLoading,
  }
}
