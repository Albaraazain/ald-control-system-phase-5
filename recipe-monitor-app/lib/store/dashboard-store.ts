import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

// Type definitions (will be replaced by Agent 5's generated types)
export type ProcessStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ComponentType = 'valve' | 'mfc' | 'chamber_heater';

export interface Recipe {
  id: string;
  name: string;
  machine_id: string | null;
}

export interface ProcessExecutionWithRecipe {
  id: string;
  recipe_id: string;
  status: ProcessStatus;
  current_step_index: number;
  started_at: string;
  completed_at: string | null;
  recipes: {
    name: string;
    total_steps: number;
  } | null;
}

export interface RecipeStep {
  id: string;
  recipe_id: string;
  step_order: number;
  action: string | null;
  duration: number | null;
  step_type: string | null;
}

export interface StepExecution {
  status: StepStatus;
  started_at: string | null;
  completed_at: string | null;
}

export interface ComponentParameter {
  id: string;
  name: string;
  type: ComponentType;
  current_value: number | null;
  target_value: number | null;
  updated_at: string;
}

export interface ValveState {
  state: 'OPEN' | 'CLOSED' | 'PARTIAL';
  cssClass: 'valve-open' | 'valve-closed' | 'valve-partial';
  glyph: string;
}

export interface LogEntry {
  id: string;
  timestamp: Date;
  message: string;
}

// Dashboard state interface
interface DashboardState {
  // State
  currentProcess: ProcessExecutionWithRecipe | null;
  steps: RecipeStep[];
  stepExecutions: Map<number, StepExecution>;
  componentsIndex: Map<string, ComponentParameter>;
  recipes: Recipe[];
  logs: LogEntry[];

  // Actions - State setters
  setCurrentProcess: (process: ProcessExecutionWithRecipe | null) => void;
  setSteps: (steps: RecipeStep[]) => void;
  setRecipes: (recipes: Recipe[]) => void;
  updateStepExecution: (stepOrder: number, execution: StepExecution) => void;
  updateComponent: (componentId: string, component: ComponentParameter) => void;
  setComponent: (component: ComponentParameter) => void;
  addLog: (message: string) => void;
  clearLogs: () => void;

  // Actions - Bulk updates
  clearStepExecutions: () => void;
  clearComponents: () => void;
  initializeStepExecutions: (executions: Array<{ step_order: number; execution: StepExecution }>) => void;
  initializeComponents: (components: ComponentParameter[]) => void;

  // Computed values (selectors)
  getProgress: () => number;
  getCurrentStepIndex: () => number;
  getProcessStatus: () => ProcessStatus;
  getValveState: (value: number) => ValveState;
  getComponentsByType: (type: ComponentType) => ComponentParameter[];
}

export const useDashboardStore = create<DashboardState>()(
  devtools(
    (set, get) => ({
      // Initial state
      currentProcess: null,
      steps: [],
      stepExecutions: new Map(),
      componentsIndex: new Map(),
      recipes: [],
      logs: [],

      // State setters
      setCurrentProcess: (process) => set({ currentProcess: process }, false, 'setCurrentProcess'),

      setSteps: (steps) => set({ steps }, false, 'setSteps'),

      setRecipes: (recipes) => set({ recipes }, false, 'setRecipes'),

      addLog: (message) => set(
        (state) => {
          const timestamp = new Date();
          const newLog: LogEntry = {
            id: `log-${timestamp.getTime()}-${Math.random().toString(36).substring(2, 9)}`,
            timestamp,
            message,
          };
          const newLogs = [...state.logs, newLog];
          // Keep only last 20 entries (HTML line 237)
          return { logs: newLogs.slice(-20) };
        },
        false,
        'addLog'
      ),

      clearLogs: () => set({ logs: [] }, false, 'clearLogs'),

      updateStepExecution: (stepOrder, execution) => set(
        (state) => {
          const newExecutions = new Map(state.stepExecutions);
          newExecutions.set(stepOrder, execution);
          return { stepExecutions: newExecutions };
        },
        false,
        'updateStepExecution'
      ),

      updateComponent: (componentId, component) => set(
        (state) => {
          const existing = state.componentsIndex.get(componentId) || { id: componentId };
          const merged = { ...existing, ...component };
          const newIndex = new Map(state.componentsIndex);
          newIndex.set(componentId, merged as ComponentParameter);
          return { componentsIndex: newIndex };
        },
        false,
        'updateComponent'
      ),

      setComponent: (component) => set(
        (state) => {
          const newIndex = new Map(state.componentsIndex);
          newIndex.set(component.id, component);
          return { componentsIndex: newIndex };
        },
        false,
        'setComponent'
      ),

      // Bulk updates
      clearStepExecutions: () => set({ stepExecutions: new Map() }, false, 'clearStepExecutions'),

      clearComponents: () => set({ componentsIndex: new Map() }, false, 'clearComponents'),

      initializeStepExecutions: (executions) => set(
        () => {
          const newExecutions = new Map<number, StepExecution>();
          executions.forEach(({ step_order, execution }) => {
            newExecutions.set(step_order, execution);
          });
          return { stepExecutions: newExecutions };
        },
        false,
        'initializeStepExecutions'
      ),

      initializeComponents: (components) => set(
        () => {
          const newIndex = new Map<string, ComponentParameter>();
          components.forEach((comp) => {
            newIndex.set(comp.id, comp);
          });
          return { componentsIndex: newIndex };
        },
        false,
        'initializeComponents'
      ),

      // Computed values - Progress calculation (from HTML lines 335-349)
      getProgress: () => {
        const { steps, stepExecutions } = get();
        const total = steps.length || 0;
        if (total === 0) return 0;

        let completed = 0;
        for (const s of steps) {
          const exec = stepExecutions.get(s.step_order);
          if (exec && exec.status === 'completed') {
            completed += 1;
          }
        }

        // Add 0.5 for a running step to visualize partial progress (HTML line 343-347)
        const runningStep = steps.find((s) => {
          const ex = stepExecutions.get(s.step_order);
          return ex && ex.status === 'running';
        });
        const partial = runningStep ? 0.5 : 0;

        return ((completed + partial) / total) * 100;
      },

      // Get current step index
      getCurrentStepIndex: () => {
        const { currentProcess, steps } = get();
        const idx = currentProcess?.current_step_index ?? 0;
        return Math.min(Math.max(idx, 0), steps.length);
      },

      // Get process status (HTML lines 312-326)
      getProcessStatus: () => {
        const { currentProcess } = get();
        return currentProcess?.status || 'idle';
      },

      // Get valve state from current_value (HTML lines 159-164)
      getValveState: (value: number): ValveState => {
        if (value >= 0.999) {
          return { state: 'OPEN', cssClass: 'valve-open', glyph: '🟢' };
        } else if (value > 0 && value < 1) {
          return { state: 'PARTIAL', cssClass: 'valve-partial', glyph: '🟡' };
        } else {
          return { state: 'CLOSED', cssClass: 'valve-closed', glyph: '🔴' };
        }
      },

      // Get components by type
      getComponentsByType: (type: ComponentType) => {
        const { componentsIndex } = get();
        return Array.from(componentsIndex.values())
          .filter((comp) => comp.type === type)
          .sort((a, b) => (a.name || '').localeCompare(b.name || ''));
      },
    }),
    {
      name: 'dashboard-store',
      enabled: process.env.NODE_ENV === 'development',
    }
  )
);

// Selector hooks for better performance
export const useCurrentProcess = () => useDashboardStore((state) => state.currentProcess);
export const useSteps = () => useDashboardStore((state) => state.steps);
export const useStepExecutions = () => useDashboardStore((state) => state.stepExecutions);
export const useComponents = () => useDashboardStore((state) => state.componentsIndex);
export const useRecipes = () => useDashboardStore((state) => state.recipes);
export const useLogs = () => useDashboardStore((state) => state.logs);
export const useAddLog = () => useDashboardStore((state) => state.addLog);
export const useProgress = () => useDashboardStore((state) => state.getProgress());
export const useProcessStatus = () => useDashboardStore((state) => state.getProcessStatus());
export const useCurrentStepIndex = () => useDashboardStore((state) => state.getCurrentStepIndex());
