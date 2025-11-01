'use client'

import { useTerminalStatus } from '@/hooks/use-terminal-status'
import TerminalStatusCard from '@/components/TerminalStatusCard'

// Get machine ID from environment at module level (build time)
const MACHINE_ID = process.env.NEXT_PUBLIC_MACHINE_ID!

/**
 * TerminalHealthPanel Component
 *
 * Displays real-time health status for all 3 terminals (Terminal 1, 2, 3)
 * integrated with the Terminal Liveness Management System.
 *
 * Features:
 * - Real-time status updates via Supabase subscriptions
 * - Health indicators with color coding (green=healthy, red=crashed, yellow=degraded)
 * - Key metrics: uptime, commands processed, errors, last heartbeat
 * - Manual refresh capability
 * - Loading and error states
 * - Responsive grid layout (1 col mobile, 3 cols desktop)
 * - Dark theme matching dashboard style
 */
export default function TerminalHealthPanel() {
  // Fetch terminal status with realtime subscription
  const { terminals, isLoading, error, refresh } = useTerminalStatus(MACHINE_ID)

  return (
    <section
      className="bg-gradient-panel border border-border rounded-xl p-4 shadow-panel"
      aria-label="Terminal Health Status"
    >
      {/* Header Row: Title + Refresh Button */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-bold tracking-wide">Terminal Status</h2>

        <button
          onClick={refresh}
          disabled={isLoading}
          className="
            px-3 py-1.5
            rounded-lg
            border border-input-border
            bg-input-bg
            text-text
            text-sm
            hover:opacity-90
            disabled:opacity-60
            disabled:cursor-not-allowed
            transition-opacity
            flex items-center gap-1.5
          "
          aria-label="Refresh terminal status"
        >
          <span className={isLoading ? 'animate-spin' : ''}>↻</span>
          <span>Refresh</span>
        </button>
      </div>

      {/* Loading State */}
      {isLoading && !terminals && (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin text-3xl">↻</div>
            <div className="text-text-muted text-sm">Loading terminal status...</div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className="
          bg-danger/10
          border border-danger-dark
          rounded-lg
          p-4
          text-center
        ">
          <div className="text-danger text-sm font-medium mb-2">
            ❌ Failed to load terminal status
          </div>
          <div className="text-text-muted text-xs mb-3">
            {error}
          </div>
          <button
            onClick={refresh}
            className="
              px-3 py-1.5
              rounded-lg
              border border-danger-dark
              bg-danger
              text-text
              text-sm
              font-medium
              hover:opacity-90
              transition-opacity
            "
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && terminals && terminals.length === 0 && (
        <div className="text-text-muted text-sm py-8 text-center">
          ⚠️ No active terminals detected
        </div>
      )}

      {/* Terminal Cards Grid */}
      {!isLoading && !error && terminals && terminals.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {terminals.map((terminal) => (
            <TerminalStatusCard
              key={terminal.id}
              terminal={terminal}
            />
          ))}
        </div>
      )}
    </section>
  )
}
