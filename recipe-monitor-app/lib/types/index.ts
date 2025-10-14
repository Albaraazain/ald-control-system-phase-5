// Central export point for all TypeScript types
// Recipe Monitor Dashboard - Type Definitions

// ========================================
// DATABASE TYPES
// ========================================
export type {
  // Base table types
  Recipe,
  RecipeInsert,
  RecipeUpdate,
  ProcessExecution,
  ProcessExecutionInsert,
  ProcessExecutionUpdate,
  RecipeStep,
  RecipeStepWithStepOrder,
  RecipeStepInsert,
  RecipeStepUpdate,
  RecipeStepExecution,
  RecipeStepExecutionInsert,
  RecipeStepExecutionUpdate,
  MachineComponent,
  MachineComponentInsert,
  MachineComponentUpdate,
  ComponentParameter,
  ComponentParameterInsert,
  ComponentParameterUpdate,
  RecipeCommand,
  RecipeCommandInsert,
  RecipeCommandUpdate,

  // Enums
  ProcessStatus,
  StepExecutionStatus,
  ComponentType,
  StepType,
  CommandType,
  CommandStatus,

  // Helper types for joins
  ProcessExecutionWithRecipe,
  ComponentParameterWithComponent,
  ComponentWithMeta,

  // Realtime types
  RealtimeInsertPayload,
  RealtimeUpdatePayload,
  RealtimeDeletePayload,
  RealtimePayload,
  ProcessExecutionRealtimePayload,
  ComponentParameterRealtimePayload,
  RecipeStepExecutionRealtimePayload,

  // Database schema
  Database,
} from './database';

// ========================================
// DASHBOARD APPLICATION TYPES
// ========================================
export type {
  // UI Status
  DashboardStatus,
  StatusChipConfig,
  ValveState,
  ValveDisplayConfig,

  // Component display
  ComponentsByType,
  ComponentDisplay,

  // Step execution
  StepWithExecution,
  StepExecution,

  // Progress
  ProgressState,

  // Button state
  ButtonState,

  // Log entries
  LogEntry,

  // Toast notifications
  ToastMessage,

  // Dashboard state
  DashboardState,

  // Recipe commands
  StartRecipeCommand,
  PauseRecipeCommand,
  StopRecipeCommand,
  RecipeCommandPayload,

  // Query results
  ActiveProcessQueryResult,
  RecipeStepsQueryResult,
  ComponentsQueryResult,
  StepHistoryQueryResult,

  // Error types
  DashboardError,

  // Machine config
  MachineConfig,
} from './dashboard';

// ========================================
// UTILITY FUNCTIONS (RE-EXPORTED)
// ========================================
export {
  STATUS_CHIP_MAP,
  STEP_STATUS_ICONS,
  getValveState,
  computeProgress,
  getButtonState,
  formatLogEntry,
} from './dashboard';
