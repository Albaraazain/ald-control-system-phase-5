# Architecture Overview - ALD Recipe Monitor Dashboard

**Version**: 1.0.0
**Last Updated**: 2025-10-14

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Patterns](#architecture-patterns)
4. [Data Flow](#data-flow)
5. [Component Architecture](#component-architecture)
6. [State Management](#state-management)
7. [Database Schema](#database-schema)
8. [Realtime Communication](#realtime-communication)
9. [File Structure](#file-structure)
10. [Design Decisions](#design-decisions)
11. [Security Considerations](#security-considerations)
12. [Performance Optimizations](#performance-optimizations)
13. [Future Enhancements](#future-enhancements)

---

## System Overview

The ALD Recipe Monitor Dashboard is a **real-time monitoring interface** for Atomic Layer Deposition (ALD) manufacturing processes. It provides operators with live visibility into recipe execution, component states, and process parameters.

### Key Features

- **Real-time Process Monitoring**: Live updates of recipe execution status
- **Component State Visualization**: Valves, MFCs, and temperature displays
- **Recipe Management**: Selection and control of ALD recipes
- **Step-by-Step Progress**: Visual tracking of recipe step execution
- **Execution Logging**: Historical log of process events
- **Responsive Design**: Works on desktop, tablet, and mobile devices

### System Context

```
┌─────────────────────────────────────────────────────────────┐
│                    ALD Control System                        │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Terminal 1 │      │   Terminal 2 │      │ Terminal 3│ │
│  │  PLC Read    │      │    Recipe    │      │ Parameter │ │
│  │   Service    │      │   Service    │      │  Service  │ │
│  └──────┬───────┘      └──────┬───────┘      └─────┬─────┘ │
│         │                     │                     │        │
│         └─────────────────────┼─────────────────────┘        │
│                               │                              │
│                        ┌──────▼──────┐                       │
│                        │   Supabase  │                       │
│                        │   Database  │                       │
│                        └──────┬──────┘                       │
└───────────────────────────────┼──────────────────────────────┘
                                │
                         ┌──────▼──────┐
                         │   Realtime  │
                         │   Channel   │
                         └──────┬──────┘
                                │
                    ┌───────────▼───────────┐
                    │  Recipe Monitor       │
                    │  Dashboard (Browser)  │
                    └───────────────────────┘
```

**Data Producers**:
- **Terminal 1** (PLC Read Service): Writes component parameter values every 1 second
- **Terminal 2** (Recipe Service): Creates/updates process executions and step executions
- **Terminal 3** (Parameter Service): Handles manual parameter control commands

**Data Consumer**:
- **Recipe Monitor Dashboard**: Reads data, displays real-time updates, sends commands

---

## Technology Stack

### Frontend Framework
- **Next.js 15.5.5**: React framework with App Router, Server Components, and Turbopack
- **React 19.1.0**: UI library with latest concurrent features

### State Management
- **Zustand 5.0.8**: Lightweight state management with devtools
- **Pattern**: Centralized stores with selector hooks

### Database & Backend
- **Supabase**: PostgreSQL database with realtime subscriptions
- **@supabase/supabase-js 2.75.0**: JavaScript client library
- **@supabase/ssr 0.7.0**: Server-side rendering support

### Styling
- **Tailwind CSS 4**: Utility-first CSS framework
- **CSS Variables**: Theme customization and dark mode

### Language
- **TypeScript 5**: Type-safe development with strict mode

### Build Tools
- **Turbopack**: Next.js 15 default bundler (faster than Webpack)
- **Node.js 18+**: Runtime environment

---

## Architecture Patterns

### 1. **Layered Architecture**

```
┌────────────────────────────────────────┐
│         Presentation Layer             │
│  (React Components + Layout)           │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│         Application Layer              │
│  (Custom Hooks + Business Logic)       │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│         State Management Layer         │
│  (Zustand Stores)                      │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│         Data Access Layer              │
│  (Supabase Client + API Calls)         │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│         External Services              │
│  (Supabase Database + Realtime)        │
└────────────────────────────────────────┘
```

### 2. **Component-Based Architecture**

- **Atomic Design Principles**: Build from small, reusable components
- **Smart vs Presentational**: Hooks contain logic, components focus on UI
- **Single Responsibility**: Each component has one clear purpose

### 3. **Event-Driven Architecture**

- **Realtime Subscriptions**: Database changes trigger UI updates
- **State Updates**: Zustand actions emit updates to subscribed components
- **User Events**: Button clicks trigger state changes and API calls

---

## Data Flow

### Initialization Sequence

```
1. User Opens Browser
         │
         ▼
2. Next.js Loads Page (app/page.tsx)
         │
         ▼
3. useDashboardData() Hook Executes
         │
         ├─→ Fetch Recipes
         ├─→ Fetch Active Process (if any)
         ├─→ Fetch Recipe Steps
         ├─→ Fetch Step Executions
         └─→ Fetch Component Parameters
         │
         ▼
4. Data Stored in Zustand Store
         │
         ▼
5. useRealtimeSubscriptions() Hook Executes
         │
         ├─→ Subscribe to process_executions
         ├─→ Subscribe to component_parameters
         └─→ Subscribe to recipe_step_executions
         │
         ▼
6. Components Render with Initial Data
         │
         ▼
7. Realtime Updates Flow In (Continuous)
```

### User Action Flow (Recipe Start)

```
1. User Selects Recipe
         │
         ▼
2. User Clicks "Start Recipe"
         │
         ▼
3. useRecipeActions.startRecipe() Called
         │
         ▼
4. API Call to Supabase
   INSERT INTO recipe_commands (recipe_id, command, machine_id)
         │
         ▼
5. Terminal 2 (Recipe Service) Detects Command
         │
         ▼
6. Recipe Service Creates process_execution Row
         │
         ▼
7. Realtime Subscription Receives Update
         │
         ▼
8. Store Updated: setCurrentProcess(newProcess)
         │
         ▼
9. Components Re-render with New State
         │
         ▼
10. Toast Notification: "Recipe started successfully"
```

### Realtime Update Flow

```
Database Change (e.g., step_execution status update)
         │
         ▼
Supabase Realtime Publishes Event
         │
         ▼
WebSocket Delivers to Browser
         │
         ▼
useRealtimeSubscriptions Hook Receives Event
         │
         ▼
Store Action Called: updateStepExecution()
         │
         ▼
Zustand Notifies Subscribed Components
         │
         ▼
Components Re-render (Only Affected Ones)
         │
         ▼
UI Updates (e.g., step card turns green)
```

---

## Component Architecture

### Component Hierarchy

```
app/layout.tsx (Root Layout)
└── app/page.tsx (Dashboard Page)
    ├── ControlPanel
    │   ├── Recipe Dropdown (select)
    │   ├── Action Buttons (Start/Pause/Stop)
    │   ├── Status Indicator
    │   ├── Progress Bar
    │   └── Step Counter
    ├── StepsPanel
    │   └── StepCard[] (for each recipe step)
    │       ├── Step Icon
    │       ├── Step Number
    │       ├── Step Description
    │       ├── Duration
    │       └── Status Badge
    ├── ComponentsPanel
    │   ├── Valves Section
    │   │   └── ValveCard[]
    │   ├── MFCs Section
    │   │   └── MFCCard[]
    │   └── Temperature Section
    │       └── HeaterCard[]
    ├── LogPanel
    │   └── LogEntry[]
    └── Toast (global notification)
```

### Component Responsibilities

#### **ControlPanel**
- **Purpose**: Recipe control and status display
- **State**: Uses `recipes`, `currentProcess`, `steps`, computed `progress`
- **Actions**: Trigger recipe start/pause/stop
- **File**: `components/ControlPanel.tsx`

#### **StepsPanel**
- **Purpose**: Display recipe steps with execution status
- **State**: Uses `steps`, `stepExecutions` Map
- **Logic**: Matches steps with execution history for status display
- **File**: `components/StepsPanel.tsx`

#### **ComponentsPanel**
- **Purpose**: Display hardware component states
- **State**: Uses `componentsIndex` Map
- **Sections**: Valves (OPEN/CLOSED/PARTIAL), MFCs (flow rate), Heaters (temperature)
- **File**: `components/ComponentsPanel.tsx`

#### **LogPanel**
- **Purpose**: Display execution log entries
- **State**: Uses `logs` array
- **Features**: Auto-scroll to bottom, timestamp formatting
- **File**: `components/LogPanel.tsx`

#### **Toast**
- **Purpose**: Temporary notifications
- **State**: Uses separate `toastStore`
- **Types**: Success (green), Error (red), Warning (yellow), Info (blue)
- **File**: `components/Toast.tsx`

---

## State Management

### Store Architecture

#### **dashboard-store.ts**

```typescript
interface DashboardState {
  // Core Data
  currentProcess: ProcessExecutionWithRecipe | null
  steps: RecipeStep[]
  stepExecutions: Map<number, StepExecution>
  componentsIndex: Map<string, ComponentParameter>
  recipes: Recipe[]
  logs: LogEntry[]

  // Setters
  setCurrentProcess: (process) => void
  setSteps: (steps) => void
  setRecipes: (recipes) => void
  updateStepExecution: (stepOrder, execution) => void
  updateComponent: (componentId, updates) => void
  addLog: (message) => void

  // Computed Properties (Derived State)
  getProgress: () => number
  getCurrentStepIndex: () => number
  getProcessStatus: () => Status
  getValveState: (componentId) => ValveState
  getComponentsByType: (type) => ComponentParameter[]
}
```

**Key Design Decisions**:
1. **Map for Fast Lookups**: `stepExecutions` and `componentsIndex` use Map for O(1) access
2. **Computed Properties**: Derived state calculated on-demand, not stored
3. **Granular Updates**: Update only changed parts, not entire state
4. **Selector Hooks**: Export custom hooks for common selectors

#### **toast-store.ts**

```typescript
interface ToastState {
  toasts: Toast[]
  showToast: (message, type, duration) => void
  removeToast: (id) => void
  clearAll: () => void
}
```

**Separation Rationale**: Toast state is independent and short-lived, no need to mix with dashboard state

### Store Update Patterns

#### **Initialization**
```typescript
// In useDashboardData hook
useEffect(() => {
  async function loadData() {
    const recipes = await fetchRecipes()
    const process = await fetchActiveProcess()
    const components = await fetchComponents()

    // Batch updates to store
    useDashboardStore.getState().setRecipes(recipes)
    useDashboardStore.getState().setCurrentProcess(process)
    useDashboardStore.getState().initializeComponents(components)
  }
  loadData()
}, [])
```

#### **Realtime Updates**
```typescript
// In useRealtimeSubscriptions hook
supabase
  .channel('process-updates')
  .on('postgres_changes', { table: 'process_executions' }, (payload) => {
    // Update only changed process
    useDashboardStore.getState().setCurrentProcess(payload.new)
  })
  .subscribe()
```

#### **User Actions**
```typescript
// In useRecipeActions hook
async function startRecipe(recipeId: number) {
  try {
    await supabase.from('recipe_commands').insert({
      recipe_id: recipeId,
      command: 'START',
      machine_id: MACHINE_ID
    })

    showToast('Recipe started successfully', 'success')
    useDashboardStore.getState().addLog('Recipe started')
  } catch (error) {
    showToast('Failed to start recipe', 'error')
  }
}
```

---

## Database Schema

### Core Tables

#### **recipes**
```sql
CREATE TABLE recipes (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  total_steps INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### **recipe_steps**
```sql
CREATE TABLE recipe_steps (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  recipe_id BIGINT REFERENCES recipes(id),
  step_order INTEGER NOT NULL,
  action TEXT NOT NULL,
  duration NUMERIC NOT NULL,
  step_type TEXT NOT NULL,
  UNIQUE(recipe_id, step_order)
);
```

#### **process_executions**
```sql
CREATE TABLE process_executions (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  recipe_id BIGINT REFERENCES recipes(id),
  status TEXT NOT NULL,
  current_step_index INTEGER DEFAULT 0,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  machine_id TEXT NOT NULL
);
```

#### **recipe_step_executions**
```sql
CREATE TABLE recipe_step_executions (
  process_execution_id BIGINT REFERENCES process_executions(id),
  step_order INTEGER NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  PRIMARY KEY (process_execution_id, step_order)
);
```

#### **machine_components**
```sql
CREATE TABLE machine_components (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,  -- 'VALVE', 'MFC', 'CHAMBER_HEATER'
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### **component_parameters**
```sql
CREATE TABLE component_parameters (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  machine_id TEXT NOT NULL,
  component_id BIGINT REFERENCES machine_components(id),
  current_value NUMERIC NOT NULL,
  target_value NUMERIC,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Indices for Performance

```sql
-- Speed up machine-specific queries
CREATE INDEX idx_recipes_machine_id ON recipes(machine_id);
CREATE INDEX idx_process_executions_machine_id ON process_executions(machine_id);
CREATE INDEX idx_component_parameters_machine_id ON component_parameters(machine_id);

-- Speed up status queries
CREATE INDEX idx_process_executions_status ON process_executions(status);

-- Speed up component lookups
CREATE INDEX idx_component_parameters_component_id ON component_parameters(component_id);
```

---

## Realtime Communication

### Supabase Realtime Architecture

```
┌─────────────────────────────────────────────────┐
│              Supabase Server                     │
│                                                  │
│  ┌──────────────┐         ┌──────────────┐     │
│  │  PostgreSQL  │────────▶│   Realtime   │     │
│  │   Database   │  WAL    │    Server    │     │
│  └──────────────┘         └──────┬───────┘     │
│                                   │              │
└───────────────────────────────────┼──────────────┘
                                    │ WebSocket
                                    ▼
                        ┌───────────────────────┐
                        │   Browser Client      │
                        │  (Dashboard)          │
                        └───────────────────────┘
```

### Subscription Setup

#### **Channel Configuration**
```typescript
// hooks/use-realtime-subscriptions.ts
const processChannel = supabase
  .channel('process-updates')
  .on(
    'postgres_changes',
    {
      event: '*',                    // Listen to all events (INSERT, UPDATE, DELETE)
      schema: 'public',
      table: 'process_executions',
      filter: `machine_id=eq.${MACHINE_ID}`  // Only this machine's data
    },
    handleProcessUpdate
  )
  .subscribe()
```

#### **Event Handlers**
```typescript
function handleProcessUpdate(payload: RealtimePayload) {
  const { eventType, new: newRecord, old: oldRecord } = payload

  switch (eventType) {
    case 'INSERT':
      useDashboardStore.getState().setCurrentProcess(newRecord)
      showToast('New process started', 'info')
      break

    case 'UPDATE':
      useDashboardStore.getState().setCurrentProcess(newRecord)
      break

    case 'DELETE':
      useDashboardStore.getState().setCurrentProcess(null)
      break
  }
}
```

### Connection Management

#### **Cleanup on Unmount**
```typescript
useEffect(() => {
  // Subscribe to channels
  const channels = [processChannel, componentChannel, stepChannel]

  // Cleanup on unmount
  return () => {
    channels.forEach(channel => {
      supabase.removeChannel(channel)
    })
  }
}, [])
```

#### **Reconnection Handling**
- Supabase client automatically reconnects on connection loss
- Missed updates are not replayed (limitation of PostgreSQL logical replication)
- Consider polling fallback for critical applications

---

## File Structure

```
recipe-monitor-app/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout with metadata, fonts, theme
│   ├── page.tsx                  # Main dashboard page
│   ├── globals.css               # Global styles, CSS variables, Tailwind
│   └── favicon.ico
│
├── components/                   # React components
│   ├── ControlPanel.tsx          # Recipe control and status
│   ├── StepsPanel.tsx            # Recipe steps display
│   ├── ComponentsPanel.tsx       # Hardware component states
│   ├── LogPanel.tsx              # Execution log
│   └── Toast.tsx                 # Toast notifications
│
├── hooks/                        # Custom React hooks
│   ├── use-dashboard-data.ts     # Initial data loading
│   ├── use-realtime-subscriptions.ts  # Realtime DB subscriptions
│   ├── use-toast.ts              # Toast helper hook
│   └── use-recipe-actions.ts     # Recipe command actions
│
├── lib/                          # Libraries and utilities
│   ├── store/
│   │   ├── dashboard-store.ts    # Main Zustand store
│   │   └── toast-store.ts        # Toast notifications store
│   ├── supabase/
│   │   ├── client.ts             # Browser Supabase client
│   │   └── server.ts             # Server Supabase client
│   ├── types/
│   │   ├── database.ts           # Supabase generated types
│   │   ├── dashboard.ts          # Custom dashboard types
│   │   └── index.ts              # Type exports
│   └── utils/                    # Utility functions (if needed)
│
├── public/                       # Static assets
│
├── .env.local                    # Environment variables (not in Git)
├── .gitignore
├── next.config.ts                # Next.js configuration
├── tailwind.config.ts            # Tailwind CSS configuration
├── tsconfig.json                 # TypeScript configuration
├── package.json
│
└── docs/                         # Documentation
    ├── DEPLOYMENT_GUIDE.md
    ├── TESTING_CHECKLIST.md
    ├── TROUBLESHOOTING.md
    ├── ARCHITECTURE_OVERVIEW.md  # This file
    └── DASHBOARD_INTEGRATION.md
```

### File Naming Conventions

- **Components**: PascalCase with `.tsx` extension (e.g., `ControlPanel.tsx`)
- **Hooks**: kebab-case with `use-` prefix (e.g., `use-dashboard-data.ts`)
- **Stores**: kebab-case with `-store` suffix (e.g., `dashboard-store.ts`)
- **Types**: kebab-case (e.g., `database.ts`)
- **Utilities**: kebab-case (e.g., `format-date.ts`)

---

## Design Decisions

### 1. **Why Next.js over Create React App?**

**Reasons**:
- **Server Components**: Better initial load performance
- **Built-in Routing**: App Router for page structure
- **Turbopack**: Faster builds and hot reload
- **Deployment**: Optimized for Vercel with zero config
- **SEO Ready**: SSR support (if needed in future)

### 2. **Why Zustand over Redux?**

**Reasons**:
- **Simplicity**: Less boilerplate, easier to learn
- **Performance**: Only subscribed components re-render
- **Bundle Size**: ~1KB vs Redux ~12KB
- **DevTools**: Built-in devtools support
- **TypeScript**: Excellent type inference

### 3. **Why Supabase over Custom Backend?**

**Reasons**:
- **Realtime Built-in**: WebSocket subscriptions without custom server
- **PostgreSQL**: Powerful relational database
- **Row Level Security**: Database-level authorization
- **Instant API**: REST API auto-generated from schema
- **Hosted**: No server management required

### 4. **Why Map for stepExecutions and componentsIndex?**

**Reasons**:
- **Performance**: O(1) lookups vs O(n) for array find
- **Updates**: Easy to update single item without recreating array
- **Memory**: Efficient for frequent updates

**Trade-off**: Slightly more complex syntax, but worth it for performance

### 5. **Why Separate toast-store?**

**Reasons**:
- **Separation of Concerns**: Toasts are UI-only, not domain data
- **Lifecycle**: Toasts are temporary, dashboard state is persistent
- **Reusability**: Toast system can be reused in other apps

### 6. **Why Client Components for Everything?**

**Current State**: Most components marked with `'use client'`

**Reasons**:
- **Interactivity**: Need hooks (useState, useEffect)
- **Realtime**: WebSocket subscriptions require client-side
- **State Management**: Zustand requires client components

**Future Optimization**: Could move some layouts to Server Components for better initial load

---

## Security Considerations

### 1. **Row Level Security (RLS)**

**Current Implementation**:
```sql
-- Allow anonymous read access to all tables
CREATE POLICY "Allow anonymous read" ON recipes FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read" ON process_executions FOR SELECT USING (true);
-- ... etc
```

**Production Recommendation**:
```sql
-- Restrict to machine-specific data
CREATE POLICY "Machine specific read" ON process_executions
  FOR SELECT USING (machine_id = current_setting('app.machine_id'));

-- Implement authenticated writes
CREATE POLICY "Authenticated write" ON recipe_commands
  FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);
```

### 2. **API Key Security**

**Current**: Using anon key (public, read-only access)

**Best Practices**:
- ✅ Anon key in environment variables (not hardcoded)
- ✅ Never commit `.env.local` to Git
- ❌ Not using service_role key in client (would be severe security risk)

### 3. **Input Validation**

**Client-Side**: TypeScript types enforce correct data shapes

**Recommendation**: Add server-side validation for recipe commands:
```sql
-- Database constraint
ALTER TABLE recipe_commands
  ADD CONSTRAINT valid_command
  CHECK (command IN ('START', 'PAUSE', 'STOP', 'RESUME'));
```

### 4. **CORS Configuration**

**Supabase CORS**: Configured in Supabase Dashboard
- Development: Allow `http://localhost:3000`
- Production: Allow only production domain

---

## Performance Optimizations

### 1. **Implemented Optimizations**

#### **Zustand Selectors**
```typescript
// ❌ Bad - re-renders on any store change
const store = useDashboardStore()

// ✅ Good - only re-renders when steps change
const steps = useDashboardStore(state => state.steps)
```

#### **Map Data Structures**
- O(1) lookups for components and step executions
- Avoids O(n) array.find() in render loops

#### **Realtime Filtering**
```typescript
filter: `machine_id=eq.${MACHINE_ID}`
```
- Reduces network traffic
- Only receives relevant updates

#### **Parallel Data Loading**
```typescript
const [recipes, components, process] = await Promise.all([
  fetchRecipes(),
  fetchComponents(),
  fetchActiveProcess()
])
```

### 2. **Potential Future Optimizations**

#### **React.memo for Expensive Components**
```typescript
export const StepCard = React.memo(({ step, execution }) => {
  // Only re-renders if step or execution changes
})
```

#### **useMemo for Derived Data**
```typescript
const sortedComponents = useMemo(() => {
  return components.sort((a, b) => a.name.localeCompare(b.name))
}, [components])
```

#### **Virtual Scrolling for Large Lists**
- Use `react-window` for 100+ steps or components
- Only render visible items

#### **Code Splitting**
```typescript
const HeavyComponent = dynamic(() => import('./HeavyComponent'), {
  loading: () => <Spinner />
})
```

---

## Future Enhancements

### Planned Features

1. **Historical Data Visualization**
   - Charts for temperature trends
   - Process execution history
   - Component performance metrics

2. **Advanced Recipe Actions**
   - Pause/Resume functionality
   - Step-by-step manual execution
   - Recipe scheduling

3. **User Authentication**
   - Role-based access control
   - Operator vs Administrator views
   - Audit logging of user actions

4. **Alerts and Notifications**
   - Email/SMS alerts for failures
   - Threshold-based warnings
   - Predictive maintenance alerts

5. **Multi-Machine Dashboard**
   - View multiple machines on one screen
   - Switch between machines
   - Cross-machine comparison

6. **Offline Support**
   - Service worker for offline access
   - Queue actions when offline
   - Sync when connection restored

7. **Automated Testing**
   - E2E tests with Playwright
   - Component tests with React Testing Library
   - Visual regression tests

8. **Performance Monitoring**
   - Real User Monitoring (RUM)
   - Error tracking with Sentry
   - Performance budgets

---

## Integration Points

### Backend Services Integration

**Terminal 2 (Recipe Service)**:
- Dashboard inserts into `recipe_commands` table
- Recipe Service polls `recipe_commands` for new commands
- Recipe Service creates/updates `process_executions`
- Dashboard receives updates via Realtime

**Terminal 1 (PLC Read Service)**:
- Continuously updates `component_parameters`
- Dashboard displays real-time component states
- No direct interaction between Dashboard and Terminal 1

**Terminal 3 (Parameter Service)**:
- Dashboard can insert manual commands (future feature)
- Parameter Service processes `parameter_control_commands`
- Updates reflected in `component_parameters`

### External Systems

**Potential Integrations**:
- Manufacturing Execution System (MES)
- Laboratory Information Management System (LIMS)
- Maintenance Management System
- Quality Management System

---

## Maintenance Guidelines

### Code Maintenance

1. **Keep Dependencies Updated**
   ```bash
   npm outdated
   npm update
   ```

2. **Monitor for Security Vulnerabilities**
   ```bash
   npm audit
   npm audit fix
   ```

3. **Type Safety**
   ```bash
   npx tsc --noEmit
   ```

4. **Code Review Checklist**
   - All components have proper TypeScript types
   - Hooks follow React best practices (dependency arrays)
   - Store updates are granular (not replacing entire state)
   - New features include error handling

### Database Maintenance

1. **Schema Changes**
   - Always migrate via Supabase migrations
   - Update TypeScript types after schema changes
   - Test locally before deploying

2. **Performance Monitoring**
   - Monitor query performance in Supabase Dashboard
   - Add indices for slow queries
   - Consider partitioning large tables

3. **Data Retention**
   - Archive old `process_executions` (> 6 months)
   - Archive old `recipe_step_executions`
   - Keep `component_parameters` recent only (rolling window)

---

## Related Documentation

- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- **Testing Checklist**: [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- **Integration Details**: [DASHBOARD_INTEGRATION.md](./DASHBOARD_INTEGRATION.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-14
**Maintained By**: Development Team
**Next Review**: 2025-11-14
