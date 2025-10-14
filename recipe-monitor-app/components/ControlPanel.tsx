'use client'

import { useState } from 'react'
import { useDashboardStore } from '@/lib/store/dashboard-store'
import { useRecipeActions } from '@/hooks/use-recipe-actions'
import type { ProcessStatus } from '@/lib/types'

/**
 * ControlPanel Component
 * Implements recipe control UI from HTML lines 190-210
 * - Recipe dropdown selector
 * - Action buttons (Start, Pause, Stop)
 * - Status chip with animated dot
 * - Progress bar with percentage
 * - Current step indicator
 */
export default function ControlPanel() {
  const [selectedRecipeId, setSelectedRecipeId] = useState<string>('')

  // Recipe action hooks (Agent 7)
  const { startRecipe, pauseRecipe, stopRecipe, isLoading } = useRecipeActions()

  const recipes = useDashboardStore((state) => state.recipes)
  const currentProcess = useDashboardStore((state) => state.currentProcess)
  const steps = useDashboardStore((state) => state.steps)
  const getCurrentStepIndex = useDashboardStore((state) => state.getCurrentStepIndex)
  const getProgress = useDashboardStore((state) => state.getProgress)

  const status: ProcessStatus = currentProcess?.status || 'idle'
  const progress = getProgress()
  const currentStepIndex = getCurrentStepIndex()
  const totalSteps = steps.length

  // Button enable/disable logic from HTML lines 306-310
  const isRunning = status === 'running'

  // Status chip configuration from HTML lines 312-326
  const getStatusConfig = (status: ProcessStatus) => {
    switch (status) {
      case 'running':
        return { text: '🔵 RUNNING', dotClass: 'bg-status-running animate-pulse-status' }
      case 'paused':
        return { text: '⏸ PAUSED', dotClass: 'bg-status-paused' }
      case 'completed':
        return { text: '✅ DONE', dotClass: 'bg-status-completed' }
      case 'failed':
        return { text: '❌ FAILED', dotClass: 'bg-status-failed' }
      default:
        return { text: '⚪ IDLE', dotClass: 'bg-status-idle' }
    }
  }

  const statusConfig = getStatusConfig(status)

  // Action handlers (HTML lines 610-658) - Integrated with use-recipe-actions hook
  const handleStart = async () => {
    await startRecipe(selectedRecipeId)
  }

  const handlePause = async () => {
    await pauseRecipe()
  }

  const handleStop = async () => {
    await stopRecipe()
  }

  return (
    <section
      className="bg-gradient-panel border border-border rounded-xl p-4 shadow-panel"
      aria-label="Recipe Control Panel"
    >
      {/* Header Row: Title + Controls (HTML lines 191-197) */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-center">
        <h1 className="text-xl font-bold tracking-wide">
          Machine 001 - Recipe Execution Monitor
        </h1>

        <div className="flex gap-2 items-center flex-wrap">
          {/* Recipe Dropdown (HTML line 193) */}
          <select
            id="recipe-select"
            value={selectedRecipeId}
            onChange={(e) => setSelectedRecipeId(e.target.value)}
            className="h-9 rounded-lg border border-input-border bg-input-bg text-text px-2.5 text-sm"
            aria-label="Recipe Dropdown"
          >
            <option value="">Select Recipe...</option>
            {recipes.map((recipe) => (
              <option key={recipe.id} value={recipe.id}>
                {recipe.name || recipe.id}
              </option>
            ))}
          </select>

          {/* Action Buttons (HTML lines 194-196) */}
          <button
            id="btn-start"
            onClick={handleStart}
            disabled={isLoading} // Disable while loading
            className="h-9 px-2.5 rounded-lg border border-primary-dark bg-primary text-text text-sm font-medium hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed transition-opacity"
          >
            {isLoading ? 'Loading...' : 'Start'}
          </button>

          <button
            id="btn-pause"
            onClick={handlePause}
            disabled={!isRunning || isLoading}
            className="h-9 px-2.5 rounded-lg border border-warning-dark bg-warning text-bg text-sm font-semibold hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed transition-opacity"
          >
            Pause
          </button>

          <button
            id="btn-stop"
            onClick={handleStop}
            disabled={!isRunning || isLoading}
            className="h-9 px-2.5 rounded-lg border border-danger-dark bg-danger text-text text-sm font-medium hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed transition-opacity"
          >
            Stop
          </button>
        </div>
      </div>

      {/* Status Row (HTML lines 199-210) */}
      <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
        {/* Status Chip (HTML lines 200-201) */}
        <div className="text-sm text-text-muted">
          <span
            id="status-chip"
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs border border-input-border bg-input-bg text-text-light"
          >
            <span
              id="status-dot"
              className={`w-2.5 h-2.5 rounded-full ${statusConfig.dotClass}`}
            />
            <span id="status-text">{statusConfig.text}</span>
          </span>
        </div>

        {/* Current Step (HTML line 203) */}
        <div className="text-sm text-text-muted">
          Current Step: <span id="current-step">{currentStepIndex}</span> / <span id="total-steps">{totalSteps}</span>
        </div>

        {/* Progress Bar (HTML lines 205-209) */}
        <div className="text-sm text-text-muted">
          <div
            className="h-3.5 bg-[#1b2447] rounded-[7px] overflow-hidden border border-border-darker"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
          >
            <div
              id="progress-fill"
              className="h-full bg-primary transition-all duration-400 ease-in-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="text-xs text-text-muted mt-0.5" id="progress-percent">
            {Math.round(progress)}%
          </div>
        </div>
      </div>
    </section>
  )
}
