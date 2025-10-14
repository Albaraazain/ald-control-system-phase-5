// Generated TypeScript types for Supabase tables used in Recipe Monitor Dashboard
// Based on schema analysis from docs/schema/

// ========================================
// TABLE: recipes
// ========================================
export interface Recipe {
  id: string;
  name: string;
  description: string | null;
  version: number;
  is_public: boolean;
  created_by: string;
  machine_type: string | null;
  substrate: string | null;
  chamber_temperature_set_point: number | null;
  pressure_set_point: number | null;
  created_at: string;
  updated_at: string;
}

// Insert type (created_at, updated_at optional)
export type RecipeInsert = Omit<Recipe, 'created_at' | 'updated_at'> & {
  created_at?: string;
  updated_at?: string;
};

// Update type (all fields optional except id)
export type RecipeUpdate = Partial<Omit<Recipe, 'id'>>;

// ========================================
// TABLE: process_executions
// ========================================
export type ProcessStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed';

export interface ProcessExecution {
  id: string;
  machine_id: string;
  operator_id: string | null;
  session_id: string | null;
  recipe_id: string;
  recipe_version: number | null;
  parameters: Record<string, unknown> | null;
  description: string | null;
  status: ProcessStatus;
  started_at: string | null;  // Fixed: was start_time
  completed_at: string | null;  // Fixed: was end_time
  current_step_index: number;  // Added: used by code
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export type ProcessExecutionInsert = Omit<ProcessExecution, 'created_at' | 'updated_at'> & {
  created_at?: string;
  updated_at?: string;
};

export type ProcessExecutionUpdate = Partial<Omit<ProcessExecution, 'id'>>;

// ========================================
// TABLE: recipe_steps
// ========================================
export type StepType = 'valve' | 'purge' | 'loop' | 'parameter';

export interface RecipeStep {
  id: string;
  recipe_id: string;
  step_order: number;  // Fixed: primary field name (was sequence_number)
  sequence_number: number;  // Kept for compatibility
  action: string | null;  // Added: used by code
  duration: number | null;  // Added: used by code
  step_type: string | null;  // Added: used by code (note: lowercase, not StepType enum)
  name: string;
  type: StepType;
  description: string | null;
  parent_step_id: string | null;
  created_at: string;
}

// Note: HTML uses `step_order` which maps to `sequence_number` in the schema
export type RecipeStepWithStepOrder = RecipeStep & {
  step_order: number; // Alias for sequence_number
};

export type RecipeStepInsert = Omit<RecipeStep, 'created_at'> & {
  created_at?: string;
};

export type RecipeStepUpdate = Partial<Omit<RecipeStep, 'id'>>;

// ========================================
// TABLE: recipe_step_executions
// ========================================
export type StepExecutionStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface RecipeStepExecution {
  id: string;
  process_execution_id: string;
  step_order: number;
  status: StepExecutionStatus;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export type RecipeStepExecutionInsert = Omit<RecipeStepExecution, 'id'> & {
  id?: string;
};

export type RecipeStepExecutionUpdate = Partial<Omit<RecipeStepExecution, 'id'>>;

// ========================================
// TABLE: machine_components
// ========================================
export type ComponentType = 'valve' | 'mfc' | 'chamber_heater';

export interface MachineComponent {
  id: string;
  machine_id: string;
  definition_id: string | null;
  name: string;
  type: ComponentType;
  is_activated: boolean;
  is_persistent: boolean;
  created_at: string;
  updated_at: string;
}

export type MachineComponentInsert = Omit<MachineComponent, 'created_at' | 'updated_at'> & {
  created_at?: string;
  updated_at?: string;
};

export type MachineComponentUpdate = Partial<Omit<MachineComponent, 'id'>>;

// ========================================
// TABLE: component_parameters
// ========================================
export interface ComponentParameter {
  id: string;
  component_id: string;
  definition_id: string | null;
  data_type: string | null;
  current_value: number | null;
  set_value: number | null;
  min_value: number | null;
  max_value: number | null;
  is_writable: boolean;
  show_in_ui: boolean;
  show_in_graph: boolean;
  read_modbus_address: number | null;
  read_modbus_type: string | null;
  write_modbus_address: number | null;
  write_modbus_type: string | null;
  created_at: string;
  updated_at: string;
}

export type ComponentParameterInsert = Omit<ComponentParameter, 'created_at' | 'updated_at'> & {
  created_at?: string;
  updated_at?: string;
};

export type ComponentParameterUpdate = Partial<Omit<ComponentParameter, 'id'>>;

// ========================================
// TABLE: recipe_commands
// ========================================
export type CommandType = 'start' | 'pause' | 'stop' | 'resume';
export type CommandStatus = 'pending' | 'executing' | 'completed' | 'failed';

export interface RecipeCommand {
  id: string;
  machine_id: string;
  recipe_id: string;  // Fixed: was recipe_step_id
  command_type: CommandType;  // Fixed: was type
  status: CommandStatus;
  executed_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export type RecipeCommandInsert = Omit<RecipeCommand, 'id' | 'created_at' | 'updated_at' | 'executed_at' | 'error_message'> & {
  id?: string;
  created_at?: string;
  updated_at?: string;
  executed_at?: string | null;
  error_message?: string | null;
};

export type RecipeCommandUpdate = Partial<Omit<RecipeCommand, 'id'>>;

// ========================================
// HELPER TYPES FOR JOINS
// ========================================

// ProcessExecution with nested Recipe (as used in HTML line 182)
export interface ProcessExecutionWithRecipe extends ProcessExecution {
  recipes: {
    name: string;
    total_steps?: number;
  } | null;
}

// ComponentParameter with nested MachineComponent (as used in HTML line 206)
export interface ComponentParameterWithComponent extends ComponentParameter {
  machine_components: {
    name: string;
    type: ComponentType;
  } | null;
}

// Flattened component for easier use in UI (as used in HTML lines 210-217)
export interface ComponentWithMeta {
  id: string;
  current_value: number | null;
  target_value: number | null;
  updated_at: string;
  name: string;
  type: ComponentType;
}

// ========================================
// REALTIME PAYLOAD TYPES
// ========================================

export interface RealtimeInsertPayload<T> {
  eventType: 'INSERT';
  new: T;
  old: Record<string, never>;
  schema: string;
  table: string;
}

export interface RealtimeUpdatePayload<T> {
  eventType: 'UPDATE';
  new: T;
  old: Partial<T>;
  schema: string;
  table: string;
}

export interface RealtimeDeletePayload<T> {
  eventType: 'DELETE';
  new: Record<string, never>;
  old: T;
  schema: string;
  table: string;
}

export type RealtimePayload<T> =
  | RealtimeInsertPayload<T>
  | RealtimeUpdatePayload<T>
  | RealtimeDeletePayload<T>;

// Specific realtime payloads for dashboard subscriptions
export type ProcessExecutionRealtimePayload = RealtimePayload<ProcessExecution>;
export type ComponentParameterRealtimePayload = RealtimePayload<ComponentParameter>;
export type RecipeStepExecutionRealtimePayload = RealtimePayload<RecipeStepExecution>;

// ========================================
// DATABASE TYPE (Supabase pattern)
// ========================================
export interface Database {
  public: {
    Tables: {
      recipes: {
        Row: Recipe;
        Insert: RecipeInsert;
        Update: RecipeUpdate;
      };
      process_executions: {
        Row: ProcessExecution;
        Insert: ProcessExecutionInsert;
        Update: ProcessExecutionUpdate;
      };
      recipe_steps: {
        Row: RecipeStep;
        Insert: RecipeStepInsert;
        Update: RecipeStepUpdate;
      };
      recipe_step_executions: {
        Row: RecipeStepExecution;
        Insert: RecipeStepExecutionInsert;
        Update: RecipeStepExecutionUpdate;
      };
      machine_components: {
        Row: MachineComponent;
        Insert: MachineComponentInsert;
        Update: MachineComponentUpdate;
      };
      component_parameters: {
        Row: ComponentParameter;
        Insert: ComponentParameterInsert;
        Update: ComponentParameterUpdate;
      };
      recipe_commands: {
        Row: RecipeCommand;
        Insert: RecipeCommandInsert;
        Update: RecipeCommandUpdate;
      };
    };
  };
}
