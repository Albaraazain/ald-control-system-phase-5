'use client'

import type { ActiveTerminal } from '@/lib/types'
import {
  getTerminalDisplayName,
  getStatusIcon,
  getStatusLabel,
  formatUptime,
  formatLastHeartbeat,
  formatCommandCount,
  formatErrorCount,
  getSecondsSinceHeartbeat,
  getStatusColor,
} from '@/lib/utils/terminal-utils'

/**
 * TerminalStatusCard Component
 *
 * Displays individual terminal health status with metrics.
 * Features:
 * - Terminal type with icon/emoji
 * - Status badge with color coding
 * - Key metrics: uptime, commands processed, errors, last heartbeat
 * - Dark theme matching dashboard style
 * - Responsive design
 */

interface TerminalStatusCardProps {
  terminal: ActiveTerminal
  className?: string
}

export default function TerminalStatusCard({ terminal, className = '' }: TerminalStatusCardProps) {
  // Calculate derived values
  const displayName = getTerminalDisplayName(terminal.terminal_type)
  const statusIcon = getStatusIcon(terminal.status)
  const statusLabel = getStatusLabel(terminal.status)
  const statusColor = getStatusColor(terminal.status)
  const uptimeFormatted = formatUptime(terminal.uptime_seconds || 0)
  const secondsSinceHeartbeat = getSecondsSinceHeartbeat(terminal.last_heartbeat)
  const heartbeatFormatted = formatLastHeartbeat(secondsSinceHeartbeat)
  const commandsFormatted = formatCommandCount(terminal.commands_processed)
  const errorsFormatted = formatErrorCount(terminal.errors_encountered)

  // Status badge color classes (using explicit mapping for Tailwind JIT)
  const statusColorClasses = {
    green: {
      bg: 'bg-green-500/10',
      text: 'text-green-500',
      border: 'border-green-500/30',
    },
    blue: {
      bg: 'bg-blue-500/10',
      text: 'text-blue-500',
      border: 'border-blue-500/30',
    },
    yellow: {
      bg: 'bg-yellow-500/10',
      text: 'text-yellow-500',
      border: 'border-yellow-500/30',
    },
    orange: {
      bg: 'bg-orange-500/10',
      text: 'text-orange-500',
      border: 'border-orange-500/30',
    },
    red: {
      bg: 'bg-red-500/10',
      text: 'text-red-500',
      border: 'border-red-500/30',
    },
    gray: {
      bg: 'bg-gray-500/10',
      text: 'text-gray-500',
      border: 'border-gray-500/30',
    },
  }

  const colorClasses = statusColorClasses[statusColor as keyof typeof statusColorClasses] || statusColorClasses.gray

  return (
    <div
      className={`
        bg-slate-800
        border border-slate-700
        rounded-lg
        p-6
        shadow-lg
        hover:shadow-xl
        transition-shadow
        ${className}
      `.trim()}
    >
      {/* Header: Terminal name and status */}
      <div className="flex justify-between items-start mb-4">
        {/* Terminal name with icon */}
        <div className="flex items-center gap-2">
          <span className="text-2xl" role="img" aria-label="terminal-icon">
            {terminal.terminal_type === 'terminal1' && '🔄'}
            {terminal.terminal_type === 'terminal2' && '🍳'}
            {terminal.terminal_type === 'terminal3' && '⚙️'}
          </span>
          <h3 className="text-lg font-semibold text-slate-100">
            {displayName}
          </h3>
        </div>

        {/* Status badge */}
        <div
          className={`
            flex items-center gap-1
            px-3 py-1
            rounded-full
            border
            ${colorClasses.bg}
            ${colorClasses.border}
          `.trim()}
        >
          <span className="text-sm" role="img" aria-label="status-icon">
            {statusIcon}
          </span>
          <span className={`text-sm font-medium ${colorClasses.text}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Uptime */}
        <div className="bg-slate-700/30 rounded-lg p-3 border border-slate-600/50">
          <div className="text-xs text-slate-400 mb-1">Uptime</div>
          <div className="text-lg font-semibold text-slate-100">
            {uptimeFormatted}
          </div>
        </div>

        {/* Commands Processed */}
        <div className="bg-slate-700/30 rounded-lg p-3 border border-slate-600/50">
          <div className="text-xs text-slate-400 mb-1">Commands</div>
          <div className="text-lg font-semibold text-slate-100">
            {commandsFormatted}
          </div>
        </div>

        {/* Errors Encountered */}
        <div className="bg-slate-700/30 rounded-lg p-3 border border-slate-600/50">
          <div className="text-xs text-slate-400 mb-1">Errors</div>
          <div className="text-lg font-semibold text-slate-100">
            {errorsFormatted}
          </div>
        </div>

        {/* Last Heartbeat */}
        <div className="bg-slate-700/30 rounded-lg p-3 border border-slate-600/50">
          <div className="text-xs text-slate-400 mb-1">Heartbeat</div>
          <div className="text-lg font-semibold text-slate-100">
            {heartbeatFormatted}
          </div>
        </div>
      </div>

      {/* Footer: System info */}
      <div className="flex justify-between items-center pt-3 border-t border-slate-700">
        <div className="text-xs text-slate-400">
          PID: {terminal.process_id || 'N/A'}
        </div>
        <div className="text-xs text-slate-400">
          {terminal.hostname || 'Unknown Host'}
        </div>
      </div>
    </div>
  )
}
