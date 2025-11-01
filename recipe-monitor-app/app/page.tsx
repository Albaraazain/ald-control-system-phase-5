'use client'

import { useDashboardData } from '@/hooks/use-dashboard-data'
import { useRealtimeSubscriptions } from '@/hooks/use-realtime-subscriptions'
import TerminalHealthPanel from '@/components/TerminalHealthPanel'
import ControlPanel from '@/components/ControlPanel'
import StepsPanel from '@/components/StepsPanel'
import ComponentsPanel from '@/components/ComponentsPanel'
import LogPanel from '@/components/LogPanel'
import Toast from '@/components/Toast'

/**
 * Main Dashboard Page
 * Integrates all components with proper data flow and initialization
 * Layout matches HTML reference lines 45-243
 */
export default function DashboardPage() {
  // Initialize dashboard data (loads recipes, processes, steps, components)
  // Implements HTML lines 661-693
  const { isLoading, error } = useDashboardData()

  // Subscribe to realtime updates (process_executions, components, step_executions)
  // Implements HTML lines 697-716
  useRealtimeSubscriptions()

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="mt-4 text-lg text-slate-300">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-red-400 mb-2">Failed to Load Dashboard</h2>
          <p className="text-slate-400">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Main dashboard layout - matches HTML lines 45-243
  return (
    <>
      {/* Container with max-width and centered (HTML lines 45-47) */}
      <div className="container mx-auto max-w-screen-xl px-4 py-6">
        {/* Dashboard Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-slate-100 mb-2">
            ALD Recipe Monitor
          </h1>
          <p className="text-slate-400">
            Real-time monitoring of recipe execution and component status
          </p>
        </div>

        {/* Main Dashboard Layout */}
        <div className="space-y-6">
          {/* Terminal Health Panel - Top priority system status */}
          <div className="w-full">
            <TerminalHealthPanel />
          </div>

          {/* Control Panel - Recipe control section (HTML lines 48-96) */}
          <div className="w-full">
            <ControlPanel />
          </div>

          {/* Steps Panel - Middle section (HTML lines 98-146) */}
          <div className="w-full">
            <StepsPanel />
          </div>

          {/* Two-column grid for Components and Log (HTML lines 112-243) */}
          {/* Single column on mobile, 2 columns on desktop (md:grid-cols-2) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Components Panel - Left column (HTML lines 148-221) */}
            <div>
              <ComponentsPanel />
            </div>

            {/* Log Panel - Right column (HTML lines 223-240) */}
            <div>
              <LogPanel />
            </div>
          </div>
        </div>
      </div>

      {/* Toast Notifications - Fixed position overlay */}
      <Toast />
    </>
  )
}
