// Terminal Liveness Management System - TypeScript Types
// Auto-generated from database schema: supabase/migrations/20251029160500_create_terminal_liveness.sql

// ========================================
// ENUMS
// ========================================

/**
 * Terminal type identifier
 * - terminal1: PLC Read Service (data collection)
 * - terminal2: Recipe Execution Service
 * - terminal3: Parameter Control Service
 */
export type TerminalType = 'terminal1' | 'terminal2' | 'terminal3';

/**
 * Terminal health status
 * - starting: Terminal is initializing
 * - healthy: Terminal is running normally
 * - degraded: Terminal is running but experiencing issues
 * - stopping: Terminal is shutting down gracefully
 * - stopped: Terminal has stopped gracefully
 * - crashed: Terminal died unexpectedly (detected by missed heartbeats)
 */
export type TerminalStatus =
  | 'starting'
  | 'healthy'
  | 'degraded'
  | 'stopping'
  | 'stopped'
  | 'crashed';

/**
 * Deployment environment type
 */
export type EnvironmentType = 'production' | 'development' | 'testing';

// ========================================
// MAIN TABLE: terminal_instances
// ========================================

/**
 * Terminal instance record from terminal_instances table
 * Tracks all terminal instances with health status, heartbeats, and metrics
 */
export interface TerminalInstance {
  // Primary identification
  /** UUID primary key */
  id: string;

  // Terminal identification
  /** Type of terminal (terminal1/terminal2/terminal3) */
  terminal_type: TerminalType;
  /** Machine UUID this terminal is serving */
  machine_id: string;

  // Process information
  /** Hostname where terminal is running (for distributed deployments) */
  hostname: string;
  /** OS process ID (PID) for terminal process */
  process_id: number;
  /** Python version running the terminal */
  python_version: string | null;
  /** Git commit hash of deployed code */
  git_commit_hash: string | null;

  // Status tracking
  /** Current health status of terminal */
  status: TerminalStatus;
  /** When terminal started (ISO timestamp) */
  started_at: string;
  /** Last heartbeat received from terminal (ISO timestamp) */
  last_heartbeat: string;
  /** When terminal stopped gracefully (ISO timestamp, nullable) */
  stopped_at: string | null;
  /** When terminal crash was detected (ISO timestamp, nullable) */
  crash_detected_at: string | null;

  // Health metrics
  /** How often terminal should send heartbeat (default 10 seconds) */
  heartbeat_interval_seconds: number;
  /** Counter of consecutive missed heartbeats */
  missed_heartbeats: number;
  /** Total commands/operations processed by this terminal */
  commands_processed: number;
  /** Total errors encountered by this terminal */
  errors_encountered: number;
  /** Average command processing latency in milliseconds */
  avg_command_latency_ms: number | null;
  /** Last error message encountered */
  last_error_message: string | null;
  /** When last error occurred (ISO timestamp, nullable) */
  last_error_at: string | null;

  // Operational metadata
  /** Deployment environment */
  environment: EnvironmentType | null;
  /** Path to terminal log file for debugging */
  log_file_path: string | null;
  /** JSONB configuration used by terminal */
  config: Record<string, unknown>;

  // Performance metrics
  /** CPU usage percentage (0-100) */
  cpu_percent: number | null;
  /** Memory usage in megabytes */
  memory_mb: number | null;

  // Timestamps
  /** Record creation timestamp (ISO format) */
  created_at: string;
  /** Last update timestamp (ISO format) */
  updated_at: string;
}

/**
 * Insert payload for creating new terminal instance
 * Omits auto-generated fields (id, timestamps, defaults)
 */
export interface TerminalInstanceInsert {
  terminal_type: TerminalType;
  machine_id: string;
  hostname: string;
  process_id: number;
  python_version?: string | null;
  git_commit_hash?: string | null;
  status?: TerminalStatus;
  heartbeat_interval_seconds?: number;
  environment?: EnvironmentType | null;
  log_file_path?: string | null;
  config?: Record<string, unknown>;
}

/**
 * Update payload for modifying terminal instance
 * All fields optional for partial updates
 */
export interface TerminalInstanceUpdate {
  status?: TerminalStatus;
  last_heartbeat?: string;
  stopped_at?: string | null;
  crash_detected_at?: string | null;
  missed_heartbeats?: number;
  commands_processed?: number;
  errors_encountered?: number;
  avg_command_latency_ms?: number | null;
  last_error_message?: string | null;
  last_error_at?: string | null;
  cpu_percent?: number | null;
  memory_mb?: number | null;
  config?: Record<string, unknown>;
}

// ========================================
// AUDIT TABLE: terminal_health_history
// ========================================

/**
 * Terminal health history record from terminal_health_history table
 * Audit trail of terminal status changes for debugging and analysis
 */
export interface TerminalHealthHistory {
  /** UUID primary key */
  id: string;
  /** Foreign key to terminal_instances */
  terminal_instance_id: string;

  // Status change
  /** Status before the change */
  previous_status: TerminalStatus | null;
  /** Status after the change */
  new_status: TerminalStatus;

  // Context
  /** Reason for status change */
  reason: string | null;
  /** Error details if applicable */
  error_details: string | null;

  // Metrics at time of change
  /** Uptime in seconds at time of change */
  uptime_seconds: number | null;
  /** Commands processed at time of change */
  commands_processed: number | null;
  /** Errors encountered at time of change */
  errors_encountered: number | null;

  // Timestamp
  /** When status change occurred (ISO format) */
  created_at: string;
}

/**
 * Insert payload for recording health history
 */
export interface TerminalHealthHistoryInsert {
  terminal_instance_id: string;
  previous_status?: TerminalStatus | null;
  new_status: TerminalStatus;
  reason?: string | null;
  error_details?: string | null;
  uptime_seconds?: number | null;
  commands_processed?: number | null;
  errors_encountered?: number | null;
}

// ========================================
// VIEW: active_terminals
// ========================================

/**
 * Active terminals view with health indicators
 * Convenient view of active terminals with health indicators and metrics
 */
export interface ActiveTerminal {
  /** Terminal instance UUID */
  id: string;
  /** Terminal type */
  terminal_type: TerminalType;
  /** Machine UUID */
  machine_id: string;
  /** Machine serial number (from machines_base join) */
  machine_serial: string | null;
  /** Hostname where terminal is running */
  hostname: string;
  /** Process ID */
  process_id: number;
  /** Current status */
  status: TerminalStatus;
  /** Start timestamp (ISO format) */
  started_at: string;
  /** Last heartbeat timestamp (ISO format) */
  last_heartbeat: string;
  /** Seconds since last heartbeat */
  seconds_since_heartbeat: number;
  /** Uptime in seconds */
  uptime_seconds: number;
  /** Commands processed count */
  commands_processed: number;
  /** Errors encountered count */
  errors_encountered: number;
  /** Average command latency in milliseconds */
  avg_command_latency_ms: number | null;
  /** Deployment environment */
  environment: EnvironmentType | null;
  /** Health indicator with emoji (e.g., "✅ Healthy", "❌ Crashed") */
  health_indicator: string;
}

// ========================================
// VIEW: terminal_health_summary
// ========================================

/**
 * Terminal health summary view
 * Summary statistics of terminal health over last 24 hours
 */
export interface TerminalHealthSummary {
  /** Terminal type */
  terminal_type: TerminalType;
  /** Machine UUID */
  machine_id: string;
  /** Terminal status */
  status: TerminalStatus;
  /** Number of instances with this status */
  instance_count: number;
  /** Average uptime in seconds */
  avg_uptime_seconds: number;
  /** Total commands processed across instances */
  total_commands: number;
  /** Total errors encountered across instances */
  total_errors: number;
  /** Most recent heartbeat timestamp (ISO format) */
  most_recent_heartbeat: string;
}

// ========================================
// FUNCTION RETURN TYPES
// ========================================

/**
 * Return type for detect_dead_terminals() function
 * Identifies terminals that have not sent heartbeat within timeout period
 */
export interface DeadTerminal {
  /** Terminal instance UUID */
  terminal_id: string;
  /** Terminal type */
  terminal_type: TerminalType;
  /** Machine UUID */
  machine_id: string;
  /** Last heartbeat timestamp (ISO format) */
  last_heartbeat: string;
  /** Seconds since last heartbeat */
  seconds_since_heartbeat: number;
  /** Hostname where terminal is running */
  hostname: string;
  /** Process ID */
  process_id: number;
}

// ========================================
// UI HELPER TYPES
// ========================================

/**
 * Terminal status display configuration for UI
 */
export interface TerminalStatusConfig {
  /** Display label */
  label: string;
  /** CSS class for styling */
  className: string;
  /** Emoji indicator */
  emoji: string;
  /** Color code (hex) */
  color: string;
}

/**
 * Terminal status configuration map
 */
export const TERMINAL_STATUS_CONFIG: Record<TerminalStatus, TerminalStatusConfig> = {
  starting: {
    label: 'Starting',
    className: 'status-starting',
    emoji: '🔄',
    color: '#3b82f6', // blue
  },
  healthy: {
    label: 'Healthy',
    className: 'status-healthy',
    emoji: '✅',
    color: '#10b981', // green
  },
  degraded: {
    label: 'Degraded',
    className: 'status-degraded',
    emoji: '⚠️',
    color: '#f59e0b', // yellow
  },
  stopping: {
    label: 'Stopping',
    className: 'status-stopping',
    emoji: '🛑',
    color: '#6b7280', // gray
  },
  stopped: {
    label: 'Stopped',
    className: 'status-stopped',
    emoji: '⏹',
    color: '#6b7280', // gray
  },
  crashed: {
    label: 'Crashed',
    className: 'status-crashed',
    emoji: '❌',
    color: '#ef4444', // red
  },
};

/**
 * Terminal type display names
 */
export const TERMINAL_TYPE_LABELS: Record<TerminalType, string> = {
  terminal1: 'Terminal 1 - PLC Read Service',
  terminal2: 'Terminal 2 - Recipe Execution',
  terminal3: 'Terminal 3 - Parameter Control',
};

/**
 * Terminal type short names
 */
export const TERMINAL_TYPE_SHORT_LABELS: Record<TerminalType, string> = {
  terminal1: 'T1 - PLC Read',
  terminal2: 'T2 - Recipe',
  terminal3: 'T3 - Parameter',
};

// ========================================
// REALTIME SUBSCRIPTION TYPES
// ========================================

/**
 * Realtime insert payload for terminal_instances
 */
export interface TerminalInstanceRealtimeInsert {
  eventType: 'INSERT';
  new: TerminalInstance;
  old: Record<string, never>;
  schema: string;
  table: string;
}

/**
 * Realtime update payload for terminal_instances
 */
export interface TerminalInstanceRealtimeUpdate {
  eventType: 'UPDATE';
  new: TerminalInstance;
  old: TerminalInstance;
  schema: string;
  table: string;
}

/**
 * Realtime delete payload for terminal_instances
 */
export interface TerminalInstanceRealtimeDelete {
  eventType: 'DELETE';
  new: Record<string, never>;
  old: TerminalInstance;
  schema: string;
  table: string;
}

/**
 * Combined realtime payload type for terminal_instances
 */
export type TerminalInstanceRealtimePayload =
  | TerminalInstanceRealtimeInsert
  | TerminalInstanceRealtimeUpdate
  | TerminalInstanceRealtimeDelete;

/**
 * Realtime payload for terminal_health_history
 */
export interface TerminalHealthHistoryRealtimeInsert {
  eventType: 'INSERT';
  new: TerminalHealthHistory;
  old: Record<string, never>;
  schema: string;
  table: string;
}

// ========================================
// UTILITY FUNCTIONS
// ========================================

/**
 * Determine if terminal is active based on status
 */
export function isTerminalActive(status: TerminalStatus): boolean {
  return ['starting', 'healthy', 'degraded', 'stopping'].includes(status);
}

/**
 * Determine if terminal is dead based on last heartbeat
 * @param lastHeartbeat - ISO timestamp of last heartbeat
 * @param timeoutSeconds - Heartbeat timeout threshold (default 30)
 */
export function isTerminalDead(lastHeartbeat: string, timeoutSeconds: number = 30): boolean {
  const lastHeartbeatDate = new Date(lastHeartbeat);
  const now = new Date();
  const secondsSinceHeartbeat = (now.getTime() - lastHeartbeatDate.getTime()) / 1000;
  return secondsSinceHeartbeat > timeoutSeconds;
}

/**
 * Calculate uptime in seconds from start time
 * @param startedAt - ISO timestamp when terminal started
 * @param stoppedAt - ISO timestamp when terminal stopped (optional)
 */
export function calculateUptimeSeconds(startedAt: string, stoppedAt?: string | null): number {
  const start = new Date(startedAt);
  const end = stoppedAt ? new Date(stoppedAt) : new Date();
  return Math.floor((end.getTime() - start.getTime()) / 1000);
}

/**
 * Format uptime as human-readable string
 * @param seconds - Uptime in seconds
 */
export function formatUptime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) {
    return `${hours}h ${remainingMinutes}m`;
  }

  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return `${days}d ${remainingHours}h`;
}

/**
 * Get status configuration for UI display
 */
export function getTerminalStatusConfig(status: TerminalStatus): TerminalStatusConfig {
  return TERMINAL_STATUS_CONFIG[status];
}

/**
 * Get terminal type label
 */
export function getTerminalTypeLabel(type: TerminalType, short: boolean = false): string {
  return short ? TERMINAL_TYPE_SHORT_LABELS[type] : TERMINAL_TYPE_LABELS[type];
}
