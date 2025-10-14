'use client'

import { useDashboardStore } from '@/lib/store/dashboard-store'
import type { StepExecutionStatus } from '@/lib/types'

/**
 * StepsPanel Component
 * Implements recipe steps list UI from HTML lines 213-217, 351-383
 * - Render list of recipe steps
 * - Step status indicators: pending/running/completed/failed
 * - Step cards with icon, title, duration, status
 * - Animated pulse for running steps
 * - Color coding: completed (green), failed (red), running (blue), pending (gray)
 */
export default function StepsPanel() {
  const steps = useDashboardStore((state) => state.steps)
  const stepExecutions = useDashboardStore((state) => state.stepExecutions)

  return (
    <section
      className="bg-gradient-panel border border-border rounded-xl p-4 shadow-panel"
      aria-label="Recipe Steps Execution"
    >
      {/* Header (HTML line 215) */}
      <h2 className="font-bold mb-2 tracking-wide">Recipe Steps Execution</h2>

      {/* Steps List (HTML lines 216-217, 351-383) */}
      <div className="grid gap-2" id="steps-list">
        {steps.length === 0 ? (
          <div className="text-text-muted text-sm py-4 text-center">
            No recipe loaded
          </div>
        ) : (
          steps.map((step) => {
            const execution = stepExecutions.get(step.step_order) || { status: 'pending' as StepExecutionStatus }
            const status = execution.status || 'pending'

            return (
              <StepCard
                key={step.id}
                stepOrder={step.step_order}
                action={step.action}
                stepType={step.step_type}
                duration={step.duration}
                status={status}
              />
            )
          })
        )}
      </div>
    </section>
  )
}

/**
 * StepCard Component
 * Individual step card with icon, title, and metadata
 * Implements HTML lines 123-136, 356-377
 */
interface StepCardProps {
  stepOrder: number
  action: string | null
  stepType: string | null
  duration: number | null
  status: StepExecutionStatus
}

function StepCard({ stepOrder, action, stepType, duration, status }: StepCardProps) {
  // Step icon based on status (HTML lines 362-367)
  const getStepIcon = (status: StepExecutionStatus): string => {
    switch (status) {
      case 'completed':
        return '✅'
      case 'running':
        return '🔵'
      case 'failed':
        return '❌'
      case 'pending':
      default:
        return '⏸'
    }
  }

  // Step class based on status (HTML lines 137-141)
  const getStepClass = (status: StepExecutionStatus): string => {
    const baseClasses = 'grid grid-cols-[28px_1fr_auto] gap-2.5 items-center border rounded-[10px] px-3 py-2.5'

    switch (status) {
      case 'pending':
        return `${baseClasses} bg-panel-darker border-border`
      case 'running':
        return `${baseClasses} bg-[#1a2a55] border-border animate-pulse-status text-text-bright`
      case 'completed':
        return `${baseClasses} bg-[#0f1f1b] border-[#1d3f34]`
      case 'failed':
        return `${baseClasses} bg-[#2a1414] border-[#5a2222]`
      default:
        return `${baseClasses} bg-panel-darker border-border`
    }
  }

  const icon = getStepIcon(status)
  const stepClass = getStepClass(status)

  // Step label (HTML lines 369-370)
  const label = action ? action : `${stepType || 'Step'} ${stepOrder}`

  // Duration and status text (HTML lines 372-374)
  const durationText = duration != null ? `${Number(duration).toFixed(1)}s` : ''
  const statusText = status ? status.toUpperCase() : 'PENDING'
  const metaText = `${durationText} ${statusText}`.trim()

  return (
    <div
      id={`step-${stepOrder}`}
      className={stepClass}
    >
      {/* Icon (HTML lines 133, 358) */}
      <div className="text-center w-7">
        {icon}
      </div>

      {/* Title (HTML lines 134, 359-370) */}
      <div className="font-semibold">
        Step {stepOrder}: {label}
      </div>

      {/* Meta (duration + status) (HTML lines 135-136, 360, 372-374) */}
      <div className="text-text-muted text-xs text-right">
        {metaText}
      </div>
    </div>
  )
}
