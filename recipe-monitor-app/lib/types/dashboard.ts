// Application-specific types for Recipe Monitor Dashboard
// These types extend and combine database types for UI logic

import type {
  ProcessStatus,
  StepExecutionStatus,
  ComponentType,
  ProcessExecutionWithRecipe,
  RecipeStep,
  RecipeStepExecution,
  ComponentWithMeta,
  Recipe,
} from './database';

// ========================================
// UI STATUS TYPES
// ========================================

// Visual status display for process (matches HTML lines 313-326)
export type DashboardStatus = ProcessStatus;

// Status chip configuration
export interface StatusChipConfig {
  text: string;
  dotClass: string;
  emoji: string;
}

export const STATUS_CHIP_MAP: Record<DashboardStatus, StatusChipConfig> = {
  idle: { text: 'IDLE', dotClass: 'dot-idle', emoji: '⚪' },
  running: { text: 'RUNNING', dotClass: 'dot-running', emoji: '🔵' },
  paused: { text: 'PAUSED', dotClass: 'dot-paused', emoji: '⏸' },
  completed: { text: 'DONE', dotClass: 'dot-completed', emoji: '✅' },
  failed: { text: 'FAILED', dotClass: 'dot-failed', emoji: '❌' },
};

// Step execution status icons (matches HTML lines 103-108)
export const STEP_STATUS_ICONS: Record<StepExecutionStatus, string> = {
  pending: '⏸',
  running: '🔵',
  completed: '✅',
  failed: '❌',
};

// ========================================
// VALVE STATE TYPES (HTML lines 149-154)
// ========================================

export type ValveState = 'OPEN' | 'CLOSED' | 'PARTIAL';

export interface ValveDisplayConfig {
  label: ValveState;
  className: string;
  emoji: string;
}

// Valve state determination logic from current_value
export function getValveState(currentValue: number | null): ValveDisplayConfig {
  const val = Number(currentValue ?? 0);

  if (val >= 0.999) {
    return { label: 'OPEN', className: 'valve-open', emoji: '🟢' };
  } else if (val > 0 && val < 1) {
    return { label: 'PARTIAL', className: 'valve-partial', emoji: '🟡' };
  } else {
    return { label: 'CLOSED', className: 'valve-closed', emoji: '🔴' };
  }
}

// ========================================
// COMPONENT DISPLAY TYPES
// ========================================

// Component filtered by type for rendering
export interface ComponentsByType {
  valves: ComponentWithMeta[];
  mfcs: ComponentWithMeta[];
  chamberHeaters: ComponentWithMeta[];
}

// Component display value (formatted for UI)
export interface ComponentDisplay {
  id: string;
  name: string;
  type: ComponentType;
  displayValue: string;
  className?: string;
  emoji: string;
}

// ========================================
// STEP EXECUTION DISPLAY
// ========================================

// Step with execution state for rendering (HTML lines 354-356)
export interface StepWithExecution {
  step: RecipeStep;
  execution: StepExecution | null;
  displayIcon: string;
  displayStatus: string;
  displayMeta: string;
}

// Step execution state (simplified from HTML lines 262-263)
export interface StepExecution {
  status: StepExecutionStatus;
  started_at: string | null;
  completed_at: string | null;
}

// ========================================
// PROGRESS CALCULATION
// ========================================

// Progress state (HTML lines 335-349)
export interface ProgressState {
  currentStep: number;
  totalSteps: number;
  completedSteps: number;
  runningStep: number | null;
  percentage: number;
}

// Calculate progress from steps and executions
export function computeProgress(
  steps: RecipeStep[],
  stepExecutions: Map<number, StepExecution>
): ProgressState {
  const totalSteps = steps.length;
  if (totalSteps === 0) {
    return {
      currentStep: 0,
      totalSteps: 0,
      completedSteps: 0,
      runningStep: null,
      percentage: 0,
    };
  }

  let completedSteps = 0;
  let runningStep: number | null = null;

  for (const step of steps) {
    const exec = stepExecutions.get(step.sequence_number);
    if (exec?.status === 'completed') {
      completedSteps += 1;
    } else if (exec?.status === 'running') {
      runningStep = step.sequence_number;
    }
  }

  // Add 0.5 for a running step to visualize partial progress
  const partial = runningStep !== null ? 0.5 : 0;
  const percentage = ((completedSteps + partial) / totalSteps) * 100;

  return {
    currentStep: runningStep ?? completedSteps,
    totalSteps,
    completedSteps,
    runningStep,
    percentage: Math.max(0, Math.min(100, Math.round(percentage))),
  };
}

// ========================================
// BUTTON STATE MANAGEMENT
// ========================================

// Button enable/disable state (HTML lines 306-310)
export interface ButtonState {
  startEnabled: boolean;
  pauseEnabled: boolean;
  stopEnabled: boolean;
}

export function getButtonState(status: DashboardStatus): ButtonState {
  return {
    startEnabled: true, // Always enabled (command queue handles duplicates)
    pauseEnabled: status === 'running',
    stopEnabled: status === 'running',
  };
}

// ========================================
// LOG ENTRY
// ========================================

// Execution log entry (HTML lines 295-304)
export interface LogEntry {
  id: string;
  timestamp: Date;
  message: string;
}

export function formatLogEntry(entry: LogEntry): string {
  const time = entry.timestamp.toLocaleTimeString([], { hour12: false });
  return `${time} - ${entry.message}`;
}

// ========================================
// TOAST NOTIFICATION
// ========================================

// Toast notification (HTML lines 281-286)
export interface ToastMessage {
  id: string;
  message: string;
  duration?: number; // milliseconds, default 2500
}

// ========================================
// DASHBOARD STATE SHAPE
// ========================================

// Complete dashboard state (matches HTML lines 260-264)
export interface DashboardState {
  // Current process execution
  currentProcess: ProcessExecutionWithRecipe | null;

  // Recipe steps for current process
  steps: RecipeStep[];

  // Step execution states (keyed by step_order/sequence_number)
  stepExecutions: Map<number, StepExecution>;

  // Component parameters (keyed by component_id)
  componentsIndex: Map<string, ComponentWithMeta>;

  // Available recipes for dropdown
  recipes: Recipe[];

  // Derived state
  status: DashboardStatus;
  progress: ProgressState;
  buttonState: ButtonState;

  // Logs (last 20 entries)
  logs: LogEntry[];
}

// ========================================
// RECIPE COMMAND TYPES
// ========================================

// Command payloads for user actions (HTML lines 351-399)
export interface StartRecipeCommand {
  recipe_id: string;
  machine_id: string;
  command_type: 'start';
  status: 'pending';
}

export interface PauseRecipeCommand {
  recipe_id: string;
  machine_id: string;
  command_type: 'pause';
  status: 'pending';
}

export interface StopRecipeCommand {
  recipe_id: string;
  machine_id: string;
  command_type: 'stop';
  status: 'pending';
}

export type RecipeCommandPayload =
  | StartRecipeCommand
  | PauseRecipeCommand
  | StopRecipeCommand;

// ========================================
// QUERY RESULT TYPES
// ========================================

// Result of loadActiveProcess query (HTML lines 179-190)
// Note: Already has all fields from ProcessExecutionWithRecipe
export type ActiveProcessQueryResult = ProcessExecutionWithRecipe;

// Result of loadRecipeSteps query (HTML lines 192-200)
export type RecipeStepsQueryResult = RecipeStep[];

// Result of loadComponents query (HTML lines 202-218)
export type ComponentsQueryResult = ComponentWithMeta[];

// Result of loadStepHistory query (HTML lines 220-229)
export interface StepHistoryQueryResult extends RecipeStepExecution {
  action?: string;
  step_type?: string;
}

// ========================================
// ERROR TYPES
// ========================================

export interface DashboardError {
  code: string;
  message: string;
  timestamp: Date;
  context?: Record<string, unknown>;
}

// ========================================
// MACHINE CONFIGURATION
// ========================================

export interface MachineConfig {
  machineId: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
}
