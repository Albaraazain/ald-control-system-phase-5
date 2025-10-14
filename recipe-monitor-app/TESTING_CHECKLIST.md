# Testing Checklist - ALD Recipe Monitor Dashboard

**Version**: 1.0.0
**Last Updated**: 2025-10-14

## Table of Contents

1. [Pre-Testing Setup](#pre-testing-setup)
2. [Initial Load Testing](#initial-load-testing)
3. [Recipe Selection and Commands](#recipe-selection-and-commands)
4. [Realtime Subscription Testing](#realtime-subscription-testing)
5. [Component Parameter Updates](#component-parameter-updates)
6. [Valve State Transitions](#valve-state-transitions)
7. [Step Execution Progress](#step-execution-progress)
8. [Log Panel Functionality](#log-panel-functionality)
9. [Toast Notifications](#toast-notifications)
10. [Responsive Layout Testing](#responsive-layout-testing)
11. [Error Handling Scenarios](#error-handling-scenarios)
12. [Performance Testing](#performance-testing)
13. [Cross-Browser Testing](#cross-browser-testing)

---

## Pre-Testing Setup

### Environment Verification

- [ ] `.env.local` file exists with correct values
- [ ] `NEXT_PUBLIC_SUPABASE_URL` set correctly
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` set correctly
- [ ] `NEXT_PUBLIC_MACHINE_ID` set to `machine_001`
- [ ] Development server running: `npm run dev`
- [ ] Browser DevTools open (Console + Network tabs)

### Database State Preparation

**Required test data**:

```sql
-- Verify test recipes exist
SELECT id, name, total_steps FROM recipes WHERE machine_id = 'machine_001';

-- Expected: At least 2-3 test recipes

-- Verify machine components exist
SELECT id, name, type FROM machine_components LIMIT 10;

-- Expected: Valves, MFCs, Chamber Heaters
```

**Create test recipe if needed**:

```sql
-- Insert test recipe
INSERT INTO recipes (name, machine_id, total_steps, created_at)
VALUES ('Test Recipe - O2 Plasma Clean', 'machine_001', 5, NOW())
RETURNING id;

-- Insert recipe steps (use recipe_id from above)
INSERT INTO recipe_steps (recipe_id, step_order, action, duration, step_type)
VALUES
  (<recipe_id>, 0, 'Open valve V1', 2.0, 'VALVE_CONTROL'),
  (<recipe_id>, 1, 'Set MFC1 to 100 sccm', 3.0, 'MFC_CONTROL'),
  (<recipe_id>, 2, 'Heat chamber to 200C', 60.0, 'TEMPERATURE_CONTROL'),
  (<recipe_id>, 3, 'Hold for 30 seconds', 30.0, 'WAIT'),
  (<recipe_id>, 4, 'Close all valves', 2.0, 'VALVE_CONTROL');
```

### Testing Tools

- [ ] Browser: Chrome/Edge (latest version)
- [ ] Browser DevTools open
- [ ] Supabase Dashboard open (for manual data changes)
- [ ] Network throttling available (for performance tests)
- [ ] Mobile device or responsive design mode available

---

## Initial Load Testing

### Test 1.1: Cold Start - No Active Process

**Precondition**: No active process in database

```sql
-- Ensure no active process
DELETE FROM process_executions WHERE status IN ('RUNNING', 'PAUSED');
```

**Steps**:
1. [ ] Open browser to http://localhost:3000
2. [ ] Observe loading spinner displays
3. [ ] Wait for dashboard to load (< 3 seconds)

**Expected Results**:
- [ ] Loading spinner shows "Loading dashboard..."
- [ ] Dashboard loads successfully
- [ ] Recipe dropdown populated with available recipes
- [ ] Control panel shows status: "IDLE"
- [ ] Steps panel shows: "No recipe selected"
- [ ] Components panel displays current component values
- [ ] Log panel shows: "Execution log will appear here"
- [ ] No console errors

**Console Logs to Verify**:
```
[Dashboard] Initializing data load
[Dashboard] Loaded X recipes
[Dashboard] No active process found
[Dashboard] Loaded X component parameters
[Dashboard] Realtime subscriptions established
```

### Test 1.2: Warm Start - Active Process Running

**Precondition**: Create active process in database

```sql
-- Insert active process
INSERT INTO process_executions (recipe_id, status, current_step_index, started_at, machine_id)
VALUES (1, 'RUNNING', 2, NOW(), 'machine_001')
RETURNING id;

-- Insert step execution history
INSERT INTO recipe_step_executions (process_execution_id, step_order, status, started_at, completed_at)
VALUES
  (<process_id>, 0, 'COMPLETED', NOW() - INTERVAL '5 minutes', NOW() - INTERVAL '4 minutes'),
  (<process_id>, 1, 'COMPLETED', NOW() - INTERVAL '4 minutes', NOW() - INTERVAL '3 minutes'),
  (<process_id>, 2, 'RUNNING', NOW() - INTERVAL '3 minutes', NULL);
```

**Steps**:
1. [ ] Refresh browser (Cmd/Ctrl + R)
2. [ ] Observe loading sequence

**Expected Results**:
- [ ] Dashboard loads with active process displayed
- [ ] Recipe dropdown shows current recipe name
- [ ] Status shows: "RUNNING" with animated green dot
- [ ] Progress bar shows correct percentage (e.g., 40% for step 2 of 5)
- [ ] Current step indicator shows: "Step 3 / 5"
- [ ] Steps panel shows:
  - [ ] Steps 0-1 marked as completed (green)
  - [ ] Step 2 marked as running (blue, pulsing)
  - [ ] Steps 3-4 marked as pending (gray)
- [ ] Log panel shows execution history
- [ ] Components panel displays current values
- [ ] No console errors

### Test 1.3: Error Handling - Invalid Supabase Credentials

**Precondition**: Temporarily break Supabase connection

```bash
# Edit .env.local
NEXT_PUBLIC_SUPABASE_URL=https://invalid-url.supabase.co
```

**Steps**:
1. [ ] Restart dev server
2. [ ] Refresh browser

**Expected Results**:
- [ ] Error state displays with warning icon
- [ ] Error message shown: "Failed to load dashboard data"
- [ ] "Retry" button visible
- [ ] Console shows specific error (network/auth failure)
- [ ] Application doesn't crash

**Cleanup**:
```bash
# Restore correct URL in .env.local
# Restart dev server
```

---

## Recipe Selection and Commands

### Test 2.1: Recipe Selection via Dropdown

**Steps**:
1. [ ] Click recipe dropdown in Control Panel
2. [ ] Observe dropdown opens with recipe list
3. [ ] Hover over each recipe option
4. [ ] Select a recipe from dropdown
5. [ ] Observe selection updates

**Expected Results**:
- [ ] Dropdown shows all available recipes
- [ ] Hover highlights recipe option
- [ ] Selection updates dropdown display
- [ ] Selected recipe name displays in dropdown
- [ ] Steps panel updates with selected recipe's steps
- [ ] Step count updates: "Step 0 / X"
- [ ] All steps show as "PENDING" (gray)
- [ ] No network requests triggered (local state change only)

### Test 2.2: Start Recipe Command

**Precondition**: Recipe selected, no active process running

**Steps**:
1. [ ] Select recipe from dropdown
2. [ ] Click "Start Recipe" button
3. [ ] Observe button state changes
4. [ ] Monitor console and network tabs

**Expected Results**:
- [ ] Button shows loading state briefly
- [ ] Toast notification: "Recipe started successfully" (success, green)
- [ ] Status updates to "RUNNING"
- [ ] Progress bar appears (0-10%)
- [ ] Current step indicator: "Step 1 / X"
- [ ] First step in Steps panel changes to "RUNNING" (blue, pulsing)
- [ ] Log panel adds entry: "[HH:MM:SS] Recipe started: <recipe_name>"
- [ ] Network request to Supabase (INSERT into recipe_commands or process_executions)
- [ ] No console errors

**Database Verification**:
```sql
-- Verify process execution created
SELECT * FROM process_executions
WHERE machine_id = 'machine_001'
ORDER BY started_at DESC LIMIT 1;

-- Expected: New row with status 'RUNNING'
```

### Test 2.3: Pause Recipe Command

**Precondition**: Recipe currently running

**Steps**:
1. [ ] Wait for recipe to be running
2. [ ] Click "Pause" button
3. [ ] Observe state changes

**Expected Results**:
- [ ] Button shows loading state briefly
- [ ] Status updates to "PAUSED"
- [ ] Status indicator shows orange/yellow color
- [ ] Animated dot stops pulsing
- [ ] Toast notification: "Recipe paused" (warning, yellow)
- [ ] Current step remains in "RUNNING" state (frozen)
- [ ] Progress bar stops advancing
- [ ] Log panel adds: "[HH:MM:SS] Recipe paused"
- [ ] "Resume" button appears (if implemented)

### Test 2.4: Stop Recipe Command

**Precondition**: Recipe currently running or paused

**Steps**:
1. [ ] Click "Stop" button
2. [ ] Observe immediate feedback

**Expected Results**:
- [ ] Status updates to "COMPLETED" or "STOPPED"
- [ ] Status indicator changes to gray/neutral color
- [ ] All running steps transition to "COMPLETED" or "CANCELLED"
- [ ] Progress bar completes or disappears
- [ ] Toast notification: "Recipe stopped" (info, blue)
- [ ] Log panel adds: "[HH:MM:SS] Recipe stopped by user"
- [ ] Start button becomes enabled again
- [ ] Recipe remains selected in dropdown

---

## Realtime Subscription Testing

### Test 3.1: Process Execution Updates

**Precondition**: Dashboard open and loaded

**Steps**:
1. [ ] Open Supabase SQL Editor in separate tab
2. [ ] Execute update query:
   ```sql
   UPDATE process_executions
   SET current_step_index = current_step_index + 1
   WHERE machine_id = 'machine_001' AND status = 'RUNNING';
   ```
3. [ ] Observe dashboard updates WITHOUT page refresh

**Expected Results**:
- [ ] Status automatically updates (no refresh needed)
- [ ] Current step indicator increments
- [ ] Progress bar advances
- [ ] Steps panel updates:
  - [ ] Previous step changes to "COMPLETED" (green)
  - [ ] New current step changes to "RUNNING" (blue)
- [ ] Log panel adds step completion entry
- [ ] Update happens within 1-2 seconds
- [ ] No console errors

**Console Verification**:
```
[Realtime] process_executions update received
[Store] Updated current process: {...}
```

### Test 3.2: Component Parameter Updates

**Precondition**: Dashboard open, Components panel visible

**Steps**:
1. [ ] Note current valve state (e.g., V1 CLOSED)
2. [ ] Execute in Supabase:
   ```sql
   UPDATE component_parameters
   SET current_value = 1.0, updated_at = NOW()
   WHERE component_id = (
     SELECT id FROM machine_components WHERE name = 'V1' LIMIT 1
   );
   ```
3. [ ] Observe Components panel without refresh

**Expected Results**:
- [ ] Valve state updates immediately
- [ ] V1 changes from CLOSED (red) to OPEN (green)
- [ ] Update within 1-2 seconds
- [ ] No page refresh required
- [ ] Other components unaffected
- [ ] Smooth visual transition

### Test 3.3: Step Execution Updates

**Precondition**: Active recipe running

**Steps**:
1. [ ] Monitor Steps panel
2. [ ] Execute in Supabase:
   ```sql
   UPDATE recipe_step_executions
   SET status = 'COMPLETED', completed_at = NOW()
   WHERE process_execution_id = <active_process_id>
     AND step_order = <current_step>;
   ```
3. [ ] Observe Steps panel

**Expected Results**:
- [ ] Step status updates from RUNNING → COMPLETED
- [ ] Step card color changes: blue → green
- [ ] Pulse animation stops
- [ ] Checkmark icon appears (if implemented)
- [ ] Update within 1-2 seconds

### Test 3.4: Realtime Connection Loss Recovery

**Steps**:
1. [ ] Dashboard loaded and running
2. [ ] Open browser Network tab
3. [ ] Throttle network to "Offline"
4. [ ] Wait 5 seconds
5. [ ] Restore network to "Online"
6. [ ] Make database change via Supabase

**Expected Results**:
- [ ] Dashboard gracefully handles connection loss
- [ ] No crash or white screen
- [ ] Console may show reconnection messages
- [ ] After reconnect, realtime updates resume
- [ ] Any missed updates are caught up (polling fallback)
- [ ] User sees toast: "Connection restored" (optional)

---

## Component Parameter Updates

### Test 4.1: Valve State Display - All States

**Setup**: Create valves with different states

```sql
-- Set valve states
UPDATE component_parameters cp
SET current_value = 0.0  -- CLOSED
WHERE component_id IN (SELECT id FROM machine_components WHERE name = 'V1');

UPDATE component_parameters cp
SET current_value = 1.0  -- OPEN
WHERE component_id IN (SELECT id FROM machine_components WHERE name = 'V2');

UPDATE component_parameters cp
SET current_value = 0.5  -- PARTIAL
WHERE component_id IN (SELECT id FROM machine_components WHERE name = 'V3');
```

**Expected Display**:
- [ ] V1 shows: CLOSED (red background)
- [ ] V2 shows: OPEN (green background)
- [ ] V3 shows: PARTIAL (yellow background)
- [ ] Each valve card has clear visual distinction
- [ ] Valve names clearly labeled

### Test 4.2: MFC Flow Rate Display

**Setup**: Set MFC values

```sql
UPDATE component_parameters cp
SET current_value = 150.5
WHERE component_id IN (SELECT id FROM machine_components WHERE name = 'MFC1' AND type = 'MFC');
```

**Expected Display**:
- [ ] MFC1 shows: "150.5 sccm"
- [ ] Value formatted to 1 decimal place
- [ ] Units clearly visible
- [ ] Value updates in realtime when changed

### Test 4.3: Temperature Display - Current vs Target

**Setup**: Set heater values with target

```sql
UPDATE component_parameters cp
SET current_value = 195.3, target_value = 200.0
WHERE component_id IN (SELECT id FROM machine_components WHERE name = 'Chamber Heater 1');
```

**Expected Display**:
- [ ] Current temperature: "195.3°C"
- [ ] Target temperature: "200.0°C" (if shown)
- [ ] Visual indicator if below target (optional: yellow/orange)
- [ ] Visual indicator if at target (optional: green)
- [ ] Decimal formatting consistent

### Test 4.4: Rapid Component Updates

**Steps**:
1. [ ] Use script to rapidly update component values
   ```sql
   -- Run this 10 times with 0.5s delay
   UPDATE component_parameters
   SET current_value = current_value + 0.1, updated_at = NOW()
   WHERE component_id = 1;
   ```

**Expected Results**:
- [ ] Dashboard handles rapid updates without lag
- [ ] No visual flickering
- [ ] Values update smoothly
- [ ] No memory leaks (check DevTools Performance)
- [ ] No console errors
- [ ] UI remains responsive

---

## Valve State Transitions

### Test 5.1: Valve Opening Sequence

**Steps**:
1. [ ] Start with all valves closed
2. [ ] Open valves sequentially via database updates
3. [ ] Observe visual transitions

**Expected Transitions**:
- [ ] CLOSED (red) → OPEN (green) transition smooth
- [ ] No intermediate incorrect states
- [ ] Transition completes within 1 second of DB update

### Test 5.2: Valve Partial State Behavior

**Steps**:
1. [ ] Set valve to partial state (0.5)
2. [ ] Verify display
3. [ ] Test edge cases: 0.01, 0.49, 0.51, 0.99

**Expected Results**:
- [ ] 0.0 displays as CLOSED
- [ ] 0.01-0.49 displays as PARTIAL
- [ ] 0.50 displays as PARTIAL
- [ ] 0.51-0.99 displays as PARTIAL
- [ ] 1.0 displays as OPEN
- [ ] Color coding matches state

### Test 5.3: Valve Component Not Found

**Steps**:
1. [ ] Remove a valve from component_parameters
   ```sql
   DELETE FROM component_parameters WHERE component_id = 1;
   ```
2. [ ] Refresh dashboard

**Expected Results**:
- [ ] Dashboard doesn't crash
- [ ] Missing valve shows placeholder or "N/A"
- [ ] Other valves display correctly
- [ ] Console may log warning (acceptable)

---

## Step Execution Progress

### Test 6.1: Linear Step Progression

**Precondition**: Recipe with 5 steps running

**Steps**:
1. [ ] Start recipe execution
2. [ ] Monitor Steps panel as steps complete
3. [ ] Verify each step transitions correctly

**Expected Progression**:
```
Step 0: PENDING → RUNNING → COMPLETED
Step 1: PENDING → RUNNING → COMPLETED
Step 2: PENDING → RUNNING → COMPLETED
Step 3: PENDING → RUNNING → COMPLETED
Step 4: PENDING → RUNNING → COMPLETED
Process: RUNNING → COMPLETED
```

**Visual Verification**:
- [ ] Only one step shows RUNNING at a time
- [ ] Completed steps remain green
- [ ] Running step has pulse animation
- [ ] Pending steps stay gray
- [ ] Progress bar increments linearly

### Test 6.2: Step Failure Scenario

**Steps**:
1. [ ] Recipe running at step 2
2. [ ] Manually set step to FAILED:
   ```sql
   UPDATE recipe_step_executions
   SET status = 'FAILED', completed_at = NOW()
   WHERE process_execution_id = <id> AND step_order = 2;

   UPDATE process_executions
   SET status = 'FAILED' WHERE id = <id>;
   ```
3. [ ] Observe dashboard response

**Expected Results**:
- [ ] Failed step shows red background
- [ ] Status indicator changes to "FAILED" (red)
- [ ] Remaining steps stay PENDING (not executed)
- [ ] Toast notification: "Recipe failed at step X" (error, red)
- [ ] Log panel shows error message
- [ ] Progress bar stops advancing

### Test 6.3: Progress Bar Accuracy

**Test Cases**:

| Steps Completed | Total Steps | Expected Progress |
|-----------------|-------------|-------------------|
| 0               | 5           | 0%                |
| 1               | 5           | 20%               |
| 2               | 5           | 40%               |
| 3               | 5           | 60%               |
| 4               | 5           | 80%               |
| 5               | 5           | 100%              |

**Verification**:
- [ ] Progress bar width matches percentage
- [ ] Percentage label displays correctly
- [ ] Smooth animation between values
- [ ] At 100%, bar fills completely

---

## Log Panel Functionality

### Test 7.1: Log Entry Addition

**Steps**:
1. [ ] Start recipe
2. [ ] Observe log panel
3. [ ] Trigger various events (step completion, pause, etc.)

**Expected Log Entries**:
```
[12:34:56] Dashboard initialized
[12:35:01] Recipe started: Test Recipe
[12:35:03] Step 1 started: Open valve V1
[12:35:05] Step 1 completed
[12:35:05] Step 2 started: Set MFC1 to 100 sccm
[12:35:08] Recipe paused by user
```

**Verification**:
- [ ] Timestamps in [HH:MM:SS] format
- [ ] Messages descriptive and clear
- [ ] Newest entries at bottom (default scroll position)
- [ ] Monospace font for consistency

### Test 7.2: Auto-Scroll Behavior

**Steps**:
1. [ ] Scroll to top of log panel
2. [ ] Add new log entry (via recipe action)
3. [ ] Observe scroll behavior

**Expected Results**:
- [ ] Panel auto-scrolls to bottom
- [ ] New entry immediately visible
- [ ] Smooth scroll animation
- [ ] Works even if user manually scrolled up

### Test 7.3: Log Entry Limit

**Steps**:
1. [ ] Generate > 100 log entries
   ```typescript
   // In console
   for (let i = 0; i < 150; i++) {
     useDashboardStore.getState().addLog(`Test log entry ${i}`)
   }
   ```

**Expected Results**:
- [ ] Panel displays last 100 entries (or configured limit)
- [ ] Older entries removed from display
- [ ] No performance degradation
- [ ] No memory leak

### Test 7.4: Log Persistence Across Page Refresh

**Steps**:
1. [ ] Generate several log entries
2. [ ] Refresh page (Cmd/Ctrl + R)

**Expected Results**:
- [ ] Logs cleared on refresh (expected - in-memory state)
- [ ] Fresh logs generated on initialization
- [ ] No stale data persists

---

## Toast Notifications

### Test 8.1: Success Toast

**Trigger**: Start recipe successfully

**Expected Behavior**:
- [ ] Toast appears bottom-right corner
- [ ] Green background with success icon
- [ ] Message: "Recipe started successfully"
- [ ] Slide-up animation on appear
- [ ] Auto-dismiss after 2.5 seconds
- [ ] Fade-out animation on dismiss

### Test 8.2: Error Toast

**Trigger**: Simulate recipe start failure

**Expected Behavior**:
- [ ] Toast appears bottom-right corner
- [ ] Red background with error icon
- [ ] Message: "Failed to start recipe: <error>"
- [ ] Auto-dismiss after 2.5 seconds

### Test 8.3: Warning Toast

**Trigger**: Pause recipe

**Expected Behavior**:
- [ ] Toast appears bottom-right corner
- [ ] Yellow/orange background with warning icon
- [ ] Message: "Recipe paused"
- [ ] Auto-dismiss after 2.5 seconds

### Test 8.4: Multiple Toasts Stacking

**Steps**:
1. [ ] Trigger 3 actions rapidly:
   - Start recipe
   - Pause recipe
   - Stop recipe

**Expected Results**:
- [ ] All 3 toasts appear
- [ ] Toasts stack vertically (not overlapping)
- [ ] Each dismisses independently after 2.5s
- [ ] Order maintained (oldest dismisses first)
- [ ] No z-index issues

### Test 8.5: Manual Toast Dismissal

**Steps**:
1. [ ] Trigger toast notification
2. [ ] Click X button (if implemented)

**Expected Results**:
- [ ] Toast dismisses immediately
- [ ] Fade-out animation plays
- [ ] No errors in console

---

## Responsive Layout Testing

### Test 9.1: Desktop Layout (≥1024px)

**Steps**:
1. [ ] Set browser width to 1920px
2. [ ] Verify layout

**Expected Layout**:
```
┌────────────────────────────────────────┐
│         Control Panel (full width)     │
├────────────────────────────────────────┤
│         Steps Panel (full width)       │
├──────────────────────┬─────────────────┤
│   Components Panel   │   Log Panel     │
│   (left 50%)         │   (right 50%)   │
└──────────────────────┴─────────────────┘
```

**Verification**:
- [ ] 2-column grid for bottom panels
- [ ] Even spacing between panels
- [ ] All content readable
- [ ] No horizontal scroll

### Test 9.2: Tablet Layout (768px - 1023px)

**Steps**:
1. [ ] Set browser width to 800px
2. [ ] Verify layout

**Expected Layout**:
```
┌──────────────────────┐
│   Control Panel      │
├──────────────────────┤
│   Steps Panel        │
├──────────────────────┤
│   Components Panel   │
├──────────────────────┤
│   Log Panel          │
└──────────────────────┘
```

**Verification**:
- [ ] Single column layout
- [ ] Panels stack vertically
- [ ] Full width panels
- [ ] Touch-friendly spacing

### Test 9.3: Mobile Layout (<768px)

**Steps**:
1. [ ] Set browser width to 375px (iPhone)
2. [ ] Verify layout and interaction

**Verification**:
- [ ] All panels stack vertically
- [ ] Recipe dropdown fully accessible
- [ ] Buttons large enough for touch (min 44x44px)
- [ ] Text readable without zoom
- [ ] No horizontal scroll
- [ ] Status indicators visible
- [ ] Progress bar displays correctly

### Test 9.4: Landscape Mobile

**Steps**:
1. [ ] Rotate mobile to landscape (667x375px)
2. [ ] Verify layout adapts

**Expected Results**:
- [ ] Layout remains usable
- [ ] Controls accessible
- [ ] May use 2-column layout if space allows

### Test 9.5: Extreme Widths

**Test Cases**:
- [ ] 320px width (small phone) - usable
- [ ] 2560px width (large monitor) - centered with max-width
- [ ] Verify no layout breaks at any width

---

## Error Handling Scenarios

### Test 10.1: Network Timeout

**Steps**:
1. [ ] Set Network throttling to "Slow 3G"
2. [ ] Trigger recipe start
3. [ ] Observe timeout handling

**Expected Results**:
- [ ] Loading state shows for operation
- [ ] After timeout (10-15s), error toast appears
- [ ] Error message: "Request timed out. Please try again."
- [ ] UI remains responsive
- [ ] User can retry action

### Test 10.2: Supabase RLS Policy Denial

**Setup**: Temporarily restrict RLS policy

```sql
-- Remove read access
DROP POLICY IF EXISTS "Allow anonymous read" ON recipes;
```

**Expected Results**:
- [ ] Dashboard shows error state
- [ ] Error message indicates permission issue
- [ ] Retry button available
- [ ] No infinite loading state
- [ ] Console logs helpful error details

**Cleanup**:
```sql
-- Restore policy
CREATE POLICY "Allow anonymous read" ON recipes FOR SELECT USING (true);
```

### Test 10.3: Malformed Data Handling

**Steps**:
1. [ ] Insert invalid data:
   ```sql
   INSERT INTO process_executions (recipe_id, status, current_step_index, machine_id)
   VALUES (999999, 'INVALID_STATUS', -1, 'machine_001');
   ```
2. [ ] Refresh dashboard

**Expected Results**:
- [ ] Dashboard doesn't crash
- [ ] Invalid process ignored or shows placeholder
- [ ] Error logged to console
- [ ] Other valid data displays correctly

### Test 10.4: Missing Component Reference

**Steps**:
1. [ ] Delete component but leave parameter:
   ```sql
   DELETE FROM machine_components WHERE id = 1;
   -- component_parameters still references id 1
   ```
2. [ ] Refresh dashboard

**Expected Results**:
- [ ] Dashboard loads successfully
- [ ] Missing component shows "Unknown Component" or hidden
- [ ] Other components display correctly
- [ ] No uncaught exceptions

### Test 10.5: WebSocket Connection Failure

**Steps**:
1. [ ] Block WebSocket connections (browser DevTools → Network → WS filter → Block)
2. [ ] Refresh dashboard
3. [ ] Make database change

**Expected Results**:
- [ ] Dashboard loads successfully (polling fallback)
- [ ] Changes eventually appear (may take 5-10s)
- [ ] Console shows reconnection attempts
- [ ] No application crash
- [ ] User experience degraded but functional

---

## Performance Testing

### Test 11.1: Initial Load Performance

**Metrics to Measure**:

1. [ ] Open DevTools → Performance tab
2. [ ] Start recording
3. [ ] Refresh page (Cmd/Ctrl + R)
4. [ ] Stop recording after full load

**Target Metrics**:
- [ ] First Contentful Paint (FCP) < 1.5s
- [ ] Largest Contentful Paint (LCP) < 2.5s
- [ ] Time to Interactive (TTI) < 3.5s
- [ ] Cumulative Layout Shift (CLS) < 0.1
- [ ] Total Blocking Time (TBT) < 300ms

**Verification**:
- [ ] Page usable within 3 seconds
- [ ] No layout shifts during load
- [ ] Smooth rendering (60fps)

### Test 11.2: Component Update Performance

**Steps**:
1. [ ] Open Performance Monitor (DevTools)
2. [ ] Trigger rapid component updates (see Test 4.4)
3. [ ] Monitor CPU usage and FPS

**Target Metrics**:
- [ ] CPU usage < 50% during updates
- [ ] Frame rate stays at 60fps
- [ ] No dropped frames
- [ ] Heap size stable (no memory leak)

### Test 11.3: Large Dataset Handling

**Setup**: Create recipe with 50 steps

```sql
-- Insert recipe with 50 steps
-- (Use script to generate)
```

**Expected Results**:
- [ ] Dashboard loads without lag
- [ ] Steps panel scrollable
- [ ] Rendering performance maintained
- [ ] No noticeable delay in UI interactions

### Test 11.4: Bundle Size Verification

**Steps**:
1. [ ] Run production build
   ```bash
   npm run build
   ```
2. [ ] Check build output

**Target Metrics**:
- [ ] First Load JS < 200 KB
- [ ] Route bundle < 100 KB
- [ ] No unused dependencies
- [ ] Tree-shaking effective

---

## Cross-Browser Testing

### Test 12.1: Chrome/Edge (Chromium)

**Version**: Latest stable

**Test Checklist**:
- [ ] Dashboard loads correctly
- [ ] All components render
- [ ] Realtime subscriptions work
- [ ] Toasts animate smoothly
- [ ] CSS grid layout correct
- [ ] No console errors

### Test 12.2: Firefox

**Version**: Latest stable

**Test Checklist**:
- [ ] Dashboard loads correctly
- [ ] CSS compatibility (grid, flexbox)
- [ ] Realtime WebSocket connections work
- [ ] Font rendering acceptable
- [ ] No console errors

### Test 12.3: Safari (macOS)

**Version**: Latest stable

**Test Checklist**:
- [ ] Dashboard loads correctly
- [ ] CSS transforms work
- [ ] WebSocket connections stable
- [ ] Date formatting correct
- [ ] Touch events work (trackpad)

### Test 12.4: Safari (iOS)

**Version**: iOS 15+

**Test Checklist**:
- [ ] Dashboard loads on iPhone
- [ ] Touch interactions work
- [ ] Buttons tappable (min 44x44px)
- [ ] Scrolling smooth
- [ ] No viewport scaling issues
- [ ] 100vh height correct

### Test 12.5: Chrome Mobile (Android)

**Version**: Latest stable

**Test Checklist**:
- [ ] Dashboard loads correctly
- [ ] Touch interactions responsive
- [ ] Layout adapts to screen size
- [ ] No performance issues
- [ ] Back button works correctly

---

## Testing Sign-Off

### Pre-Production Checklist

- [ ] All test sections completed
- [ ] Critical bugs resolved
- [ ] Known issues documented
- [ ] Performance targets met
- [ ] Cross-browser compatibility verified
- [ ] Mobile responsiveness confirmed
- [ ] Error handling robust
- [ ] Realtime subscriptions stable

### Test Results Summary

**Total Tests**: ___
**Passed**: ___
**Failed**: ___
**Blocked**: ___

**Critical Issues**: (List any blocking issues)

**Minor Issues**: (List non-blocking issues)

**Tested By**: _______________
**Date**: _______________
**Environment**: Development / Staging / Production
**Build Version**: _______________

---

## Continuous Testing

### Regression Testing

After each code change, run:
- [ ] Initial load tests (1.1, 1.2)
- [ ] Recipe command tests (2.1, 2.2)
- [ ] Realtime subscription test (3.1)
- [ ] Component display test (4.1)
- [ ] Responsive layout test (9.1, 9.3)

### Automated Testing (Future)

**Recommended Tools**:
- **E2E**: Playwright or Cypress
- **Component**: React Testing Library
- **Visual**: Chromatic or Percy
- **Performance**: Lighthouse CI

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-14
**Next Review**: 2025-11-14
