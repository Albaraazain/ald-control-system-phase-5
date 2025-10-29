/**
 * Terminal Liveness Utility Functions
 *
 * Helper functions for formatting and displaying terminal health status.
 * Used by Terminal Liveness components for consistent UI display.
 *
 * NOTE: This file provides UI-focused utilities that complement the types
 * and basic functions in lib/types/terminal.ts. Imports types from terminal.ts
 * to avoid duplication and ensure consistency with database schema.
 */

import type {
  TerminalStatus,
  TerminalType,
  TerminalInstance,
  ActiveTerminal,
} from '../types/terminal';

import {
  isTerminalActive,
  calculateUptimeSeconds,
  formatUptime as formatUptimeBase,
  TERMINAL_STATUS_CONFIG,
} from '../types/terminal';

// Re-export commonly used types and functions for convenience
export type { TerminalStatus, TerminalType, TerminalInstance, ActiveTerminal };
export { isTerminalActive, calculateUptimeSeconds, TERMINAL_STATUS_CONFIG };

/**
 * Simplified terminal interface for health check utilities
 */
export interface TerminalHealthCheck {
  status: TerminalStatus;
  last_heartbeat: string; // ISO timestamp
}

// ============================================================
// STATUS COLOR UTILITIES
// ============================================================

/**
 * Get Tailwind color class based on terminal status
 *
 * @param status - Terminal status from database
 * @returns Tailwind color name (without prefix)
 *
 * @example
 * ```ts
 * const color = getStatusColor('healthy'); // 'green'
 * const className = `text-${color}-500`; // 'text-green-500'
 * ```
 */
export function getStatusColor(status: TerminalStatus): string {
  switch (status) {
    case 'healthy':
      return 'green';
    case 'starting':
      return 'blue';
    case 'degraded':
      return 'yellow';
    case 'stopping':
      return 'orange';
    case 'stopped':
      return 'gray';
    case 'crashed':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get full Tailwind text color class for status
 *
 * @param status - Terminal status
 * @returns Full Tailwind class string
 */
export function getStatusTextColor(status: TerminalStatus): string {
  const color = getStatusColor(status);
  return `text-${color}-500`;
}

/**
 * Get full Tailwind background color class for status
 *
 * @param status - Terminal status
 * @returns Full Tailwind class string
 */
export function getStatusBgColor(status: TerminalStatus): string {
  const color = getStatusColor(status);
  return `bg-${color}-500/10`;
}

/**
 * Get full Tailwind border color class for status
 *
 * @param status - Terminal status
 * @returns Full Tailwind class string
 */
export function getStatusBorderColor(status: TerminalStatus): string {
  const color = getStatusColor(status);
  return `border-${color}-500/30`;
}

// ============================================================
// STATUS ICON UTILITIES
// ============================================================

/**
 * Get emoji icon for terminal status
 *
 * @param status - Terminal status from database
 * @returns Emoji string
 *
 * @example
 * ```ts
 * const icon = getStatusIcon('healthy'); // '✅'
 * ```
 */
export function getStatusIcon(status: TerminalStatus): string {
  switch (status) {
    case 'healthy':
      return '✅';
    case 'starting':
      return '🔄';
    case 'degraded':
      return '⚠️';
    case 'stopping':
      return '🛑';
    case 'stopped':
      return '⏹️';
    case 'crashed':
      return '❌';
    default:
      return '❓';
  }
}

/**
 * Get status label for display
 *
 * @param status - Terminal status
 * @returns Human-readable status label
 */
export function getStatusLabel(status: TerminalStatus): string {
  switch (status) {
    case 'healthy':
      return 'Healthy';
    case 'starting':
      return 'Starting';
    case 'degraded':
      return 'Degraded';
    case 'stopping':
      return 'Stopping';
    case 'stopped':
      return 'Stopped';
    case 'crashed':
      return 'Crashed';
    default:
      return 'Unknown';
  }
}

// ============================================================
// TIME FORMATTING UTILITIES
// ============================================================

/**
 * Format uptime seconds to human-readable string
 *
 * Enhanced version that shows more detail for short uptimes.
 * Uses base formatUptime from terminal.ts for consistency.
 *
 * @param seconds - Uptime in seconds
 * @param detailed - If true, shows seconds for < 1 minute uptimes
 * @returns Formatted uptime string
 *
 * @example
 * ```ts
 * formatUptime(45) // "45s"
 * formatUptime(125) // "2m"
 * formatUptime(125, true) // "2m 5s"
 * formatUptime(3725) // "1h 2m"
 * formatUptime(90125) // "1d 1h"
 * ```
 */
export function formatUptime(seconds: number, detailed: boolean = false): string {
  // Handle edge cases
  if (!seconds || seconds < 0) {
    return '0s';
  }

  // For detailed view under 1 minute, show seconds
  if (detailed && seconds < 60) {
    return `${Math.floor(seconds)}s`;
  }

  // For detailed view under 1 hour, show minutes and seconds
  if (detailed && seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return secs > 0 ? `${minutes}m ${secs}s` : `${minutes}m`;
  }

  // Otherwise use base implementation
  return formatUptimeBase(seconds);
}

/**
 * Format seconds since last heartbeat to human-readable string
 *
 * @param seconds - Seconds since last heartbeat
 * @returns Formatted string with optional warning indicator
 *
 * @example
 * ```ts
 * formatLastHeartbeat(5) // "Just now"
 * formatLastHeartbeat(25) // "25s ago"
 * formatLastHeartbeat(90) // "2m ago"
 * formatLastHeartbeat(45) // "45s ago ⚠️" (warning if > 30s)
 * ```
 */
export function formatLastHeartbeat(seconds: number): string {
  // Handle edge cases
  if (!seconds || seconds < 0) {
    return 'Just now';
  }

  // < 10s: "Just now"
  if (seconds < 10) {
    return 'Just now';
  }

  // < 60s: "Xs ago"
  if (seconds < 60) {
    const warning = seconds > 30 ? ' ⚠️' : '';
    return `${Math.floor(seconds)}s ago${warning}`;
  }

  // >= 60s: "Xm ago"
  const minutes = Math.floor(seconds / 60);
  const warning = seconds > 30 ? ' ⚠️' : '';

  if (minutes === 1) {
    return `1 minute ago${warning}`;
  }

  return `${minutes} minutes ago${warning}`;
}

/**
 * Check if heartbeat is stale (> 30 seconds old)
 *
 * @param secondsSinceHeartbeat - Seconds since last heartbeat
 * @returns True if heartbeat is stale
 */
export function isHeartbeatStale(secondsSinceHeartbeat: number): boolean {
  return secondsSinceHeartbeat > 30;
}

// ============================================================
// TERMINAL DISPLAY NAME UTILITIES
// ============================================================

/**
 * Get friendly display name for terminal type
 * Uses TERMINAL_TYPE_LABELS from terminal.ts
 *
 * @param type - Terminal type from database
 * @returns Human-readable terminal name
 *
 * @example
 * ```ts
 * getTerminalDisplayName('terminal1') // "PLC Data Service"
 * getTerminalDisplayName('terminal2') // "Recipe Service"
 * getTerminalDisplayName('terminal3') // "Parameter Service"
 * ```
 */
export function getTerminalDisplayName(type: TerminalType): string {
  const labels: Record<TerminalType, string> = {
    terminal1: 'PLC Data Service',
    terminal2: 'Recipe Service',
    terminal3: 'Parameter Service',
  };
  return labels[type] || 'Unknown Terminal';
}

/**
 * Get short display name for terminal type
 *
 * @param type - Terminal type from database
 * @returns Short name
 */
export function getTerminalShortName(type: TerminalType): string {
  const labels: Record<TerminalType, string> = {
    terminal1: 'Terminal 1',
    terminal2: 'Terminal 2',
    terminal3: 'Terminal 3',
  };
  return labels[type] || 'Unknown';
}

/**
 * Get description for terminal type
 *
 * @param type - Terminal type from database
 * @returns Terminal description
 */
export function getTerminalDescription(type: TerminalType): string {
  const descriptions: Record<TerminalType, string> = {
    terminal1: 'Continuous PLC data collection and monitoring',
    terminal2: 'Recipe command processing and execution',
    terminal3: 'Parameter control and writing',
  };
  return descriptions[type] || 'Unknown terminal service';
}

// ============================================================
// HEALTH CHECK UTILITIES
// ============================================================

/**
 * Check if terminal is healthy
 *
 * Considers both status and heartbeat freshness.
 * Terminal is healthy if status is 'healthy' AND last heartbeat < 30s ago.
 *
 * @param terminal - Terminal instance with status and last_heartbeat
 * @returns True if terminal is healthy
 *
 * @example
 * ```ts
 * const terminal = {
 *   status: 'healthy',
 *   last_heartbeat: '2025-10-29T17:30:00Z'
 * };
 * isTerminalHealthy(terminal) // depends on current time
 * ```
 */
export function isTerminalHealthy(terminal: TerminalHealthCheck): boolean {
  if (terminal.status !== 'healthy') {
    return false;
  }

  // Calculate seconds since last heartbeat
  const lastHeartbeat = new Date(terminal.last_heartbeat);
  const now = new Date();
  const secondsSinceHeartbeat = (now.getTime() - lastHeartbeat.getTime()) / 1000;

  return !isHeartbeatStale(secondsSinceHeartbeat);
}

/**
 * Calculate seconds since last heartbeat
 *
 * @param lastHeartbeat - ISO timestamp string of last heartbeat
 * @returns Seconds since last heartbeat
 */
export function getSecondsSinceHeartbeat(lastHeartbeat: string): number {
  const lastHeartbeatDate = new Date(lastHeartbeat);
  const now = new Date();
  return Math.floor((now.getTime() - lastHeartbeatDate.getTime()) / 1000);
}

/**
 * Check if terminal needs attention (degraded or crashed)
 *
 * @param status - Terminal status
 * @returns True if terminal needs attention
 */
export function needsAttention(status: TerminalStatus): boolean {
  return ['degraded', 'crashed'].includes(status);
}

/**
 * Get health severity level
 *
 * @param status - Terminal status
 * @returns Severity: 'critical' | 'warning' | 'normal'
 */
export function getHealthSeverity(status: TerminalStatus): 'critical' | 'warning' | 'normal' {
  if (status === 'crashed') {
    return 'critical';
  }
  if (status === 'degraded' || status === 'stopping') {
    return 'warning';
  }
  return 'normal';
}

// ============================================================
// METRIC FORMATTING UTILITIES
// ============================================================

/**
 * Format commands processed count with K/M suffix
 *
 * @param count - Number of commands
 * @returns Formatted string
 *
 * @example
 * ```ts
 * formatCommandCount(543) // "543"
 * formatCommandCount(1234) // "1.2K"
 * formatCommandCount(1234567) // "1.2M"
 * ```
 */
export function formatCommandCount(count: number | null | undefined): string {
  if (count === null || count === undefined) {
    return '0';
  }

  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`;
  }
  return count.toString();
}

/**
 * Format latency in milliseconds
 *
 * @param ms - Latency in milliseconds
 * @returns Formatted string with unit
 *
 * @example
 * ```ts
 * formatLatency(45) // "45ms"
 * formatLatency(1234) // "1.23s"
 * formatLatency(null) // "N/A"
 * ```
 */
export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) {
    return 'N/A';
  }

  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }
  return `${Math.round(ms)}ms`;
}

/**
 * Format error count with indicator
 *
 * @param count - Number of errors
 * @returns Formatted string with indicator
 *
 * @example
 * ```ts
 * formatErrorCount(0) // "0"
 * formatErrorCount(5) // "5 ⚠️"
 * formatErrorCount(null) // "0"
 * ```
 */
export function formatErrorCount(count: number | null | undefined): string {
  const errorCount = count ?? 0;

  if (errorCount === 0) {
    return '0';
  }

  return errorCount > 10 ? `${errorCount} ⚠️⚠️` : `${errorCount} ⚠️`;
}

// ============================================================
// SORTING AND FILTERING UTILITIES
// ============================================================

/**
 * Sort terminals by priority (health status)
 *
 * Priority order: crashed > degraded > starting > stopping > healthy > stopped
 *
 * @param terminals - Array of terminals to sort
 * @returns Sorted array (does not mutate original)
 */
export function sortTerminalsByPriority<T extends { status: TerminalStatus }>(
  terminals: T[]
): T[] {
  const priorityOrder: Record<TerminalStatus, number> = {
    crashed: 0,
    degraded: 1,
    starting: 2,
    stopping: 3,
    healthy: 4,
    stopped: 5,
  };

  return [...terminals].sort((a, b) => {
    return priorityOrder[a.status] - priorityOrder[b.status];
  });
}

/**
 * Filter terminals by health status
 *
 * @param terminals - Array of terminals
 * @param includeHealthy - Include healthy terminals
 * @param includeActive - Include active terminals (starting, degraded)
 * @param includeInactive - Include inactive terminals (stopped, crashed)
 * @returns Filtered array
 */
export function filterTerminalsByHealth<T extends { status: TerminalStatus }>(
  terminals: T[],
  options: {
    includeHealthy?: boolean;
    includeActive?: boolean;
    includeInactive?: boolean;
  } = {}
): T[] {
  const {
    includeHealthy = true,
    includeActive = true,
    includeInactive = false,
  } = options;

  return terminals.filter((terminal) => {
    if (terminal.status === 'healthy' && includeHealthy) return true;
    if (isTerminalActive(terminal.status) && terminal.status !== 'healthy' && includeActive) return true;
    if (!isTerminalActive(terminal.status) && includeInactive) return true;
    return false;
  });
}
